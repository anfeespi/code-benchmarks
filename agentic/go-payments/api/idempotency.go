package api

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"

	"example.com/gopayments/idempotency"
	"example.com/gopayments/money"
	"example.com/gopayments/payment"
)

// IdempotencyKeyHeader is the request header clients use to make POSTs safe to retry.
const IdempotencyKeyHeader = "Idempotency-Key"

// ReplayedHeader is set on responses replayed from the idempotency store.
const ReplayedHeader = "Idempotent-Replayed"

// idempotent runs op at most once per Idempotency-Key. fingerprint identifies
// the semantic request: a retry carrying the same key and fingerprint gets the
// stored response; the same key with another fingerprint is rejected.
// Responses with status >= 500 are not stored so the client can retry.
func (s *Server) idempotent(w http.ResponseWriter, r *http.Request, fingerprint string, op func() (int, any)) {
	key := r.Header.Get(IdempotencyKeyHeader)
	if key == "" {
		status, body := op()
		writeJSON(w, status, body)
		return
	}
	scoped := r.Method + " " + r.URL.Path + " " + key
	rec, started, err := s.idem.Begin(r.Context(), scoped, fingerprint)
	switch {
	case errors.Is(err, idempotency.ErrKeyReuse):
		writeJSON(w, http.StatusUnprocessableEntity, errorBody{Error: errorDetail{Code: "idempotency_key_reused", Message: err.Error()}})
		return
	case errors.Is(err, idempotency.ErrInProgress):
		writeJSON(w, http.StatusConflict, errorBody{Error: errorDetail{Code: "request_in_progress", Message: err.Error()}})
		return
	case err != nil:
		writeError(w, fmt.Errorf("idempotency: %w", err))
		return
	case !started:
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set(ReplayedHeader, "true")
		w.WriteHeader(rec.Response.Status)
		_, _ = w.Write(rec.Response.Body)
		return
	}

	status, body := op()
	raw, err := json.Marshal(body)
	if err != nil {
		_ = s.idem.Release(r.Context(), scoped)
		writeError(w, fmt.Errorf("encode response: %w", err))
		return
	}
	raw = append(raw, '\n')
	if status >= 500 {
		_ = s.idem.Release(r.Context(), scoped)
	} else {
		_ = s.idem.Complete(r.Context(), scoped, idempotency.Response{Status: status, Body: raw})
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(raw)
}

// createFingerprint hashes the decoded request, not the raw body, so
// semantically identical retries match regardless of JSON formatting.
func createFingerprint(in payment.CreateInput) string {
	return hash(fmt.Sprintf("create|%s|%d|%s", in.MerchantID, in.Amount.Minor, in.Amount.Currency.Code))
}

func refundFingerprint(paymentID string, amount money.Amount) string {
	return hash(fmt.Sprintf("refund|%s|%d|%s", paymentID, amount.Minor, amount.Currency.Code))
}

func hash(s string) string {
	sum := sha256.Sum256([]byte(s))
	return hex.EncodeToString(sum[:])
}
