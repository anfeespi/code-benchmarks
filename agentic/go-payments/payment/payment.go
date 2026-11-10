// Package payment holds the payment domain: statuses, the payment aggregate,
// the repository contract and the service that drives the lifecycle.
package payment

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"example.com/gopayments/money"
)

// Status is the lifecycle state of a payment.
type Status string

// Payment statuses.
const (
	StatusCreated   Status = "CREATED"
	StatusPending   Status = "PENDING"
	StatusSucceeded Status = "SUCCEEDED"
	StatusDeclined  Status = "DECLINED"
	StatusRefunded  Status = "REFUNDED"
)

var allStatuses = []Status{StatusCreated, StatusPending, StatusSucceeded, StatusDeclined, StatusRefunded}

// ParseStatus parses a status name, case-insensitively.
func ParseStatus(s string) (Status, error) {
	up := Status(strings.ToUpper(strings.TrimSpace(s)))
	for _, st := range allStatuses {
		if st == up {
			return st, nil
		}
	}
	return "", fmt.Errorf("%w: unknown status %q", ErrInvalidInput, s)
}

// Final reports whether no further transitions are possible from s.
func (s Status) Final() bool { return s == StatusDeclined || s == StatusRefunded }

// Domain errors. Callers must match them with errors.Is: they are always wrapped.
var (
	ErrNotFound               = errors.New("payment not found")
	ErrInvalidInput           = errors.New("invalid input")
	ErrInvalidTransition      = errors.New("invalid status transition")
	ErrRefundExceedsRemaining = errors.New("refund exceeds remaining amount")
	ErrVersionConflict        = errors.New("version conflict")
	ErrInvalidCursor          = errors.New("invalid cursor")
	ErrDuplicate              = errors.New("duplicate payment")
)

// Refund is a (possibly partial) refund of a succeeded payment.
type Refund struct {
	ID        string
	Amount    money.Amount
	CreatedAt time.Time
}

// Payment is the payment aggregate. Refunded is the sum of Refunds in minor
// units of Amount.Currency.
type Payment struct {
	ID            string
	MerchantID    string
	Amount        money.Amount
	Fee           money.Amount
	Refunded      int64
	Status        Status
	DeclineReason string
	Refunds       []Refund
	Version       int
	CreatedAt     time.Time
	UpdatedAt     time.Time
}

// Remaining is the amount that can still be refunded.
func (p Payment) Remaining() money.Amount {
	return money.Amount{Minor: p.Amount.Minor - p.Refunded, Currency: p.Amount.Currency}
}

// RefundedAmount is Refunded as a money.Amount.
func (p Payment) RefundedAmount() money.Amount {
	return money.Amount{Minor: p.Refunded, Currency: p.Amount.Currency}
}

// Clone returns a deep copy that shares no mutable state with p.
func (p Payment) Clone() Payment {
	c := p
	c.Refunds = append([]Refund(nil), p.Refunds...)
	return c
}

// Page selects a window of a listing.
type Page struct {
	Cursor string
	Limit  int
}

// Repository persists payments. Implementations must be safe for concurrent use.
type Repository interface {
	Create(ctx context.Context, p Payment) error
	Get(ctx context.Context, id string) (Payment, error)
	// Update stores p if p.Version equals the stored version (optimistic
	// locking) and increments the stored version; otherwise ErrVersionConflict.
	Update(ctx context.Context, p Payment) error
	// ListByMerchant returns payments in creation order and the cursor of the
	// next page ("" when there are no more).
	ListByMerchant(ctx context.Context, merchantID string, page Page) ([]Payment, string, error)
}

// Event is emitted after every successful state change.
type Event struct {
	Type    string
	Payment Payment
	Refund  *Refund
}

// Publisher receives domain events (the webhook dispatcher in production).
type Publisher interface {
	Publish(ctx context.Context, ev Event) error
}
