package api

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"

	"example.com/gopayments/money"
	"example.com/gopayments/payment"
)

const maxBodyBytes = 1 << 20

func (s *Server) createPayment(w http.ResponseWriter, r *http.Request) {
	var req createPaymentRequest
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, err)
		return
	}
	amount, err := money.Parse(req.Amount, req.Currency)
	if err != nil {
		writeError(w, fmt.Errorf("amount: %w", err))
		return
	}
	in := payment.CreateInput{MerchantID: req.MerchantID, Amount: amount}
	s.idempotent(w, r, createFingerprint(in), func() (int, any) {
		p, err := s.svc.Create(r.Context(), in)
		if err != nil {
			return errorResponse(err)
		}
		return http.StatusCreated, toPaymentResponse(p)
	})
}

func (s *Server) getPayment(w http.ResponseWriter, r *http.Request) {
	p, err := s.svc.Get(r.Context(), r.PathValue("id"))
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, toPaymentResponse(p))
}

func (s *Server) authorizePayment(w http.ResponseWriter, r *http.Request) {
	s.respondPayment(w, func() (payment.Payment, error) { return s.svc.Authorize(r.Context(), r.PathValue("id")) })
}

func (s *Server) capturePayment(w http.ResponseWriter, r *http.Request) {
	s.respondPayment(w, func() (payment.Payment, error) { return s.svc.Capture(r.Context(), r.PathValue("id")) })
}

func (s *Server) declinePayment(w http.ResponseWriter, r *http.Request) {
	var req declineRequest
	if r.ContentLength != 0 {
		if err := decodeJSON(r, &req); err != nil {
			writeError(w, err)
			return
		}
	}
	s.respondPayment(w, func() (payment.Payment, error) {
		return s.svc.Decline(r.Context(), r.PathValue("id"), req.Reason)
	})
}

func (s *Server) refundPayment(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	var req refundRequest
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, err)
		return
	}
	p, err := s.svc.Get(r.Context(), id)
	if err != nil {
		writeError(w, err)
		return
	}
	amount, err := money.Parse(req.Amount, p.Amount.Currency.Code)
	if err != nil {
		writeError(w, fmt.Errorf("amount: %w", err))
		return
	}
	s.idempotent(w, r, refundFingerprint(id, amount), func() (int, any) {
		p, _, err := s.svc.Refund(r.Context(), id, amount)
		if err != nil {
			return errorResponse(err)
		}
		return http.StatusCreated, toPaymentResponse(p)
	})
}

func (s *Server) listPayments(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	page := payment.Page{Cursor: q.Get("cursor")}
	if v := q.Get("limit"); v != "" {
		n, err := strconv.Atoi(v)
		if err != nil {
			writeError(w, fmt.Errorf("%w: limit %q is not a number", payment.ErrInvalidInput, v))
			return
		}
		page.Limit = n
	}
	ps, next, err := s.svc.List(r.Context(), r.PathValue("merchantID"), page)
	if err != nil {
		writeError(w, err)
		return
	}
	out := listResponse{Data: make([]paymentResponse, 0, len(ps)), NextCursor: next}
	for _, p := range ps {
		out.Data = append(out.Data, toPaymentResponse(p))
	}
	writeJSON(w, http.StatusOK, out)
}

func (s *Server) listDeadLetters(w http.ResponseWriter, _ *http.Request) {
	dead := s.hooks.DeadLetters()
	out := make([]deadLetterResponse, 0, len(dead))
	for _, d := range dead {
		out = append(out, toDeadLetterResponse(d))
	}
	writeJSON(w, http.StatusOK, map[string]any{"data": out})
}

func (s *Server) respondPayment(w http.ResponseWriter, op func() (payment.Payment, error)) {
	p, err := op()
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, toPaymentResponse(p))
}

func decodeJSON(r *http.Request, dst any) error {
	dec := json.NewDecoder(io.LimitReader(r.Body, maxBodyBytes))
	dec.DisallowUnknownFields()
	if err := dec.Decode(dst); err != nil {
		return fmt.Errorf("%w: malformed JSON body: %v", payment.ErrInvalidInput, err)
	}
	return nil
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}
