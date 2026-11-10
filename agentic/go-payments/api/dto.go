package api

import (
	"time"

	"example.com/gopayments/payment"
	"example.com/gopayments/webhook"
)

type createPaymentRequest struct {
	MerchantID string `json:"merchant_id"`
	Amount     string `json:"amount"`
	Currency   string `json:"currency"`
}

type refundRequest struct {
	Amount string `json:"amount"`
}

type declineRequest struct {
	Reason string `json:"reason"`
}

type refundResponse struct {
	ID        string    `json:"id"`
	Amount    string    `json:"amount"`
	CreatedAt time.Time `json:"created_at"`
}

type paymentResponse struct {
	ID              string           `json:"id"`
	MerchantID      string           `json:"merchant_id"`
	Status          string           `json:"status"`
	Amount          string           `json:"amount"`
	Currency        string           `json:"currency"`
	Fee             string           `json:"fee"`
	RefundedAmount  string           `json:"refunded_amount"`
	RemainingAmount string           `json:"remaining_amount"`
	DeclineReason   string           `json:"decline_reason,omitempty"`
	Refunds         []refundResponse `json:"refunds"`
	CreatedAt       time.Time        `json:"created_at"`
	UpdatedAt       time.Time        `json:"updated_at"`
}

type listResponse struct {
	Data       []paymentResponse `json:"data"`
	NextCursor string            `json:"next_cursor,omitempty"`
}

type deadLetterResponse struct {
	EventID    string    `json:"event_id"`
	Type       string    `json:"type"`
	MerchantID string    `json:"merchant_id"`
	Attempts   int       `json:"attempts"`
	LastStatus int       `json:"last_status,omitempty"`
	LastError  string    `json:"last_error,omitempty"`
	FailedAt   time.Time `json:"failed_at"`
}

type errorBody struct {
	Error errorDetail `json:"error"`
}

type errorDetail struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

func toPaymentResponse(p payment.Payment) paymentResponse {
	out := paymentResponse{
		ID:              p.ID,
		MerchantID:      p.MerchantID,
		Status:          string(p.Status),
		Amount:          p.Amount.Decimal(),
		Currency:        p.Amount.Currency.Code,
		Fee:             p.Fee.Decimal(),
		RefundedAmount:  p.RefundedAmount().Decimal(),
		RemainingAmount: p.Remaining().Decimal(),
		DeclineReason:   p.DeclineReason,
		Refunds:         make([]refundResponse, 0, len(p.Refunds)),
		CreatedAt:       p.CreatedAt.UTC(),
		UpdatedAt:       p.UpdatedAt.UTC(),
	}
	for _, r := range p.Refunds {
		out.Refunds = append(out.Refunds, refundResponse{ID: r.ID, Amount: r.Amount.Decimal(), CreatedAt: r.CreatedAt.UTC()})
	}
	return out
}

func toDeadLetterResponse(d webhook.DeadLetter) deadLetterResponse {
	return deadLetterResponse{
		EventID:    d.Event.ID,
		Type:       d.Event.Type,
		MerchantID: d.Event.MerchantID,
		Attempts:   d.Attempts,
		LastStatus: d.LastStatus,
		LastError:  d.LastError,
		FailedAt:   d.FailedAt.UTC(),
	}
}
