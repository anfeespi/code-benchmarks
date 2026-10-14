package api

import (
	"errors"
	"net/http"

	"example.com/gopayments/money"
	"example.com/gopayments/payment"
)

// errorResponse maps a domain error to an HTTP status and error body. The
// service wraps every error with context, so matching uses errors.Is.
func errorResponse(err error) (int, any) {
	status, code := http.StatusInternalServerError, "internal_error"
	switch {
	case errors.Is(err, payment.ErrNotFound):
		status, code = http.StatusNotFound, "not_found"
	case errors.Is(err, payment.ErrInvalidTransition):
		status, code = http.StatusConflict, "invalid_transition"
	case errors.Is(err, payment.ErrVersionConflict):
		status, code = http.StatusConflict, "conflict"
	case errors.Is(err, payment.ErrRefundExceedsRemaining):
		status, code = http.StatusUnprocessableEntity, "refund_exceeds_remaining"
	case errors.Is(err, payment.ErrInvalidInput),
		errors.Is(err, payment.ErrInvalidCursor),
		errors.Is(err, money.ErrInvalidAmount),
		errors.Is(err, money.ErrPrecision),
		errors.Is(err, money.ErrUnknownCurrency),
		errors.Is(err, money.ErrCurrencyMismatch):
		status, code = http.StatusBadRequest, "invalid_request"
	}
	msg := err.Error()
	if status == http.StatusInternalServerError {
		msg = "internal error"
	}
	return status, errorBody{Error: errorDetail{Code: code, Message: msg}}
}

func writeError(w http.ResponseWriter, err error) {
	status, body := errorResponse(err)
	writeJSON(w, status, body)
}
