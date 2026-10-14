package payment

import (
	"context"
	"fmt"
	"sync"

	"example.com/gopayments/clock"
	"example.com/gopayments/money"
)

// IDGenerator creates unique identifiers with a type prefix.
type IDGenerator interface {
	NewID(prefix string) string
}

// SeqIDs is a deterministic IDGenerator ("pay_000001", "ref_000002", ...).
type SeqIDs struct {
	mu sync.Mutex
	n  int
}

// NewSeqIDs returns a sequential generator starting at 1.
func NewSeqIDs() *SeqIDs { return &SeqIDs{} }

// NewID returns the next identifier.
func (g *SeqIDs) NewID(prefix string) string {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.n++
	return fmt.Sprintf("%s_%06d", prefix, g.n)
}

// Config tunes the service.
type Config struct {
	// FeeBps is the processing fee in basis points charged on every payment.
	FeeBps int64
}

// Service drives the payment lifecycle.
type Service struct {
	repo   Repository
	clock  clock.Clock
	ids    IDGenerator
	events Publisher
	cfg    Config
}

// NewService wires a Service. events may be nil.
func NewService(repo Repository, clk clock.Clock, ids IDGenerator, events Publisher, cfg Config) *Service {
	return &Service{repo: repo, clock: clk, ids: ids, events: events, cfg: cfg}
}

// CreateInput is the input of Create.
type CreateInput struct {
	MerchantID string
	Amount     money.Amount
}

// Create registers a new payment in status CREATED.
func (s *Service) Create(ctx context.Context, in CreateInput) (Payment, error) {
	if in.MerchantID == "" {
		return Payment{}, fmt.Errorf("%w: merchant id is required", ErrInvalidInput)
	}
	if !in.Amount.IsPositive() {
		return Payment{}, fmt.Errorf("%w: amount must be positive, got %s", ErrInvalidInput, in.Amount)
	}
	fee, err := money.Fee(in.Amount, s.cfg.FeeBps)
	if err != nil {
		return Payment{}, fmt.Errorf("compute fee: %w", err)
	}
	now := s.clock.Now()
	p := Payment{
		ID:         s.ids.NewID("pay"),
		MerchantID: in.MerchantID,
		Amount:     in.Amount,
		Fee:        fee,
		Status:     StatusCreated,
		Version:    1,
		CreatedAt:  now,
		UpdatedAt:  now,
	}
	if err := s.repo.Create(ctx, p); err != nil {
		return Payment{}, fmt.Errorf("create payment: %w", err)
	}
	s.publish(ctx, Event{Type: "payment.created", Payment: p})
	return p, nil
}

// Get loads a payment.
func (s *Service) Get(ctx context.Context, id string) (Payment, error) {
	p, err := s.repo.Get(ctx, id)
	if err != nil {
		return Payment{}, fmt.Errorf("get payment %s: %w", id, err)
	}
	return p, nil
}

// List returns one page of a merchant's payments.
func (s *Service) List(ctx context.Context, merchantID string, page Page) ([]Payment, string, error) {
	if merchantID == "" {
		return nil, "", fmt.Errorf("%w: merchant id is required", ErrInvalidInput)
	}
	ps, next, err := s.repo.ListByMerchant(ctx, merchantID, page)
	if err != nil {
		return nil, "", fmt.Errorf("list payments of %s: %w", merchantID, err)
	}
	return ps, next, nil
}

// Authorize moves a CREATED payment to PENDING (sent to the provider).
func (s *Service) Authorize(ctx context.Context, id string) (Payment, error) {
	return s.mutate(ctx, id, func(p *Payment) (Event, error) {
		switch p.Status {
		case StatusCreated:
			p.Status = StatusPending
			return Event{Type: "payment.pending"}, nil
		default:
			return Event{}, fmt.Errorf("%w: cannot authorize a %s payment", ErrInvalidTransition, p.Status)
		}
	})
}

// Capture moves a PENDING payment to SUCCEEDED.
func (s *Service) Capture(ctx context.Context, id string) (Payment, error) {
	return s.mutate(ctx, id, func(p *Payment) (Event, error) {
		switch p.Status {
		case StatusPending:
			p.Status = StatusSucceeded
			return Event{Type: "payment.succeeded"}, nil
		default:
			return Event{}, fmt.Errorf("%w: cannot capture a %s payment", ErrInvalidTransition, p.Status)
		}
	})
}

// Decline moves a CREATED or PENDING payment to DECLINED.
func (s *Service) Decline(ctx context.Context, id, reason string) (Payment, error) {
	return s.mutate(ctx, id, func(p *Payment) (Event, error) {
		switch p.Status {
		case StatusCreated, StatusPending:
			p.Status = StatusDeclined
			p.DeclineReason = reason
			return Event{Type: "payment.declined"}, nil
		default:
			return Event{}, fmt.Errorf("%w: cannot decline a %s payment", ErrInvalidTransition, p.Status)
		}
	})
}

// Refund refunds amount of a SUCCEEDED payment. Partial refunds keep the
// payment SUCCEEDED; once the whole amount is refunded it becomes REFUNDED.
func (s *Service) Refund(ctx context.Context, id string, amount money.Amount) (Payment, Refund, error) {
	if !amount.IsPositive() {
		return Payment{}, Refund{}, fmt.Errorf("%w: refund amount must be positive, got %s", ErrInvalidInput, amount)
	}
	var refund Refund
	p, err := s.mutate(ctx, id, func(p *Payment) (Event, error) {
		switch p.Status {
		case StatusSucceeded:
		default:
			return Event{}, fmt.Errorf("%w: cannot refund a %s payment", ErrInvalidTransition, p.Status)
		}
		if amount.Currency != p.Amount.Currency {
			return Event{}, fmt.Errorf("%w: refund in %s for a %s payment", money.ErrCurrencyMismatch, amount.Currency.Code, p.Amount.Currency.Code)
		}
		if amount.Minor > p.Remaining().Minor {
			return Event{}, fmt.Errorf("%w: requested %s, remaining %s", ErrRefundExceedsRemaining, amount, p.Remaining())
		}
		refund = Refund{ID: s.ids.NewID("ref"), Amount: amount, CreatedAt: s.clock.Now()}
		p.Refunded += amount.Minor
		p.Refunds = append(p.Refunds, refund)
		evType := "payment.partially_refunded"
		if p.Refunded == p.Amount.Minor {
			p.Status = StatusRefunded
			evType = "payment.refunded"
		}
		return Event{Type: evType, Refund: &refund}, nil
	})
	if err != nil {
		return Payment{}, Refund{}, err
	}
	return p, refund, nil
}

// mutate loads a payment, applies change and saves it with optimistic locking.
func (s *Service) mutate(ctx context.Context, id string, change func(p *Payment) (Event, error)) (Payment, error) {
	p, err := s.repo.Get(ctx, id)
	if err != nil {
		return Payment{}, fmt.Errorf("load payment %s: %w", id, err)
	}
	ev, err := change(&p)
	if err != nil {
		return Payment{}, fmt.Errorf("payment %s: %w", id, err)
	}
	p.UpdatedAt = s.clock.Now()
	if err := s.repo.Update(ctx, p); err != nil {
		return Payment{}, fmt.Errorf("save payment %s: %w", id, err)
	}
	p.Version++
	ev.Payment = p
	s.publish(ctx, ev)
	return p, nil
}

func (s *Service) publish(ctx context.Context, ev Event) {
	if s.events == nil {
		return
	}
	// Delivery is asynchronous and retried by the dispatcher; a failure to
	// enqueue must not fail the payment operation.
	_ = s.events.Publish(ctx, ev)
}
