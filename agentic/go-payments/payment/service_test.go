package payment

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"sync"
	"testing"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/money"
)

// fakeRepo is a minimal Repository so the service can be tested without the store package.
type fakeRepo struct {
	mu sync.Mutex
	m  map[string]Payment
}

func newFakeRepo() *fakeRepo { return &fakeRepo{m: map[string]Payment{}} }

func (r *fakeRepo) Create(_ context.Context, p Payment) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.m[p.ID] = p.Clone()
	return nil
}

func (r *fakeRepo) Get(_ context.Context, id string) (Payment, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	p, ok := r.m[id]
	if !ok {
		return Payment{}, fmt.Errorf("%w: %s", ErrNotFound, id)
	}
	return p.Clone(), nil
}

func (r *fakeRepo) Update(_ context.Context, p Payment) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	cur, ok := r.m[p.ID]
	if !ok {
		return fmt.Errorf("%w: %s", ErrNotFound, p.ID)
	}
	if cur.Version != p.Version {
		return ErrVersionConflict
	}
	p = p.Clone()
	p.Version++
	r.m[p.ID] = p
	return nil
}

func (r *fakeRepo) ListByMerchant(context.Context, string, Page) ([]Payment, string, error) {
	return nil, "", nil
}

type recorder struct {
	mu     sync.Mutex
	events []string
}

func (r *recorder) Publish(_ context.Context, ev Event) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.events = append(r.events, ev.Type)
	return nil
}

func newTestService() (*Service, *recorder) {
	rec := &recorder{}
	clk := clock.NewFake(time.Date(2026, 3, 1, 12, 0, 0, 0, time.UTC))
	return NewService(newFakeRepo(), clk, NewSeqIDs(), rec, Config{FeeBps: 290}), rec
}

func succeeded(t *testing.T, s *Service, minor int64) Payment {
	t.Helper()
	ctx := context.Background()
	p, err := s.Create(ctx, CreateInput{MerchantID: "m_1", Amount: money.MustNew(minor, "USD")})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := s.Authorize(ctx, p.ID); err != nil {
		t.Fatal(err)
	}
	p, err = s.Capture(ctx, p.ID)
	if err != nil {
		t.Fatal(err)
	}
	return p
}

func TestCreateValidation(t *testing.T) {
	s, _ := newTestService()
	tests := []struct {
		name string
		in   CreateInput
	}{
		{"missing merchant", CreateInput{Amount: money.MustNew(100, "USD")}},
		{"zero amount", CreateInput{MerchantID: "m", Amount: money.MustNew(0, "USD")}},
		{"negative amount", CreateInput{MerchantID: "m", Amount: money.MustNew(-1, "USD")}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if _, err := s.Create(context.Background(), tt.in); !errors.Is(err, ErrInvalidInput) {
				t.Fatalf("error = %v, want ErrInvalidInput", err)
			}
		})
	}
}

func TestCreateComputesFee(t *testing.T) {
	s, _ := newTestService()
	p, err := s.Create(context.Background(), CreateInput{MerchantID: "m", Amount: money.MustNew(10000, "USD")})
	if err != nil {
		t.Fatal(err)
	}
	if p.Fee.Minor != 290 || p.Status != StatusCreated || p.Version != 1 {
		t.Fatalf("got fee %d status %s version %d", p.Fee.Minor, p.Status, p.Version)
	}
}

func TestLifecycleHappyPath(t *testing.T) {
	s, rec := newTestService()
	p := succeeded(t, s, 1000)
	if p.Status != StatusSucceeded {
		t.Fatalf("status = %s", p.Status)
	}
	want := "payment.created,payment.pending,payment.succeeded"
	if got := strings.Join(rec.events, ","); got != want {
		t.Fatalf("events = %s, want %s", got, want)
	}
}

func TestInvalidTransitions(t *testing.T) {
	ctx := context.Background()
	tests := []struct {
		name string
		op   func(s *Service, id string) error
		prep func(t *testing.T, s *Service) string
	}{
		{
			name: "capture created",
			prep: func(t *testing.T, s *Service) string {
				p, _ := s.Create(ctx, CreateInput{MerchantID: "m", Amount: money.MustNew(100, "USD")})
				return p.ID
			},
			op: func(s *Service, id string) error { _, err := s.Capture(ctx, id); return err },
		},
		{
			name: "authorize succeeded",
			prep: func(t *testing.T, s *Service) string { return succeeded(t, s, 100).ID },
			op:   func(s *Service, id string) error { _, err := s.Authorize(ctx, id); return err },
		},
		{
			name: "decline succeeded",
			prep: func(t *testing.T, s *Service) string { return succeeded(t, s, 100).ID },
			op:   func(s *Service, id string) error { _, err := s.Decline(ctx, id, "late"); return err },
		},
		{
			name: "refund pending",
			prep: func(t *testing.T, s *Service) string {
				p, _ := s.Create(ctx, CreateInput{MerchantID: "m", Amount: money.MustNew(100, "USD")})
				_, _ = s.Authorize(ctx, p.ID)
				return p.ID
			},
			op: func(s *Service, id string) error {
				_, _, err := s.Refund(ctx, id, money.MustNew(10, "USD"))
				return err
			},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			s, _ := newTestService()
			id := tt.prep(t, s)
			if err := tt.op(s, id); !errors.Is(err, ErrInvalidTransition) {
				t.Fatalf("error = %v, want ErrInvalidTransition", err)
			}
		})
	}
}

func TestDeclineKeepsReason(t *testing.T) {
	s, _ := newTestService()
	ctx := context.Background()
	p, _ := s.Create(ctx, CreateInput{MerchantID: "m", Amount: money.MustNew(100, "USD")})
	p, err := s.Decline(ctx, p.ID, "insufficient_funds")
	if err != nil {
		t.Fatal(err)
	}
	if p.Status != StatusDeclined || p.DeclineReason != "insufficient_funds" {
		t.Fatalf("got %s %q", p.Status, p.DeclineReason)
	}
}

func TestPartialThenFullRefund(t *testing.T) {
	s, rec := newTestService()
	ctx := context.Background()
	p := succeeded(t, s, 1000)

	p, r1, err := s.Refund(ctx, p.ID, money.MustNew(300, "USD"))
	if err != nil {
		t.Fatal(err)
	}
	if p.Status != StatusSucceeded || p.Refunded != 300 || r1.Amount.Minor != 300 {
		t.Fatalf("after partial: status %s refunded %d", p.Status, p.Refunded)
	}
	p, _, err = s.Refund(ctx, p.ID, money.MustNew(700, "USD"))
	if err != nil {
		t.Fatal(err)
	}
	if p.Status != StatusRefunded || p.Refunded != 1000 || len(p.Refunds) != 2 {
		t.Fatalf("after full: status %s refunded %d refunds %d", p.Status, p.Refunded, len(p.Refunds))
	}
	if last := rec.events[len(rec.events)-1]; last != "payment.refunded" {
		t.Fatalf("last event = %s", last)
	}
}

func TestRefundValidation(t *testing.T) {
	s, _ := newTestService()
	ctx := context.Background()
	p := succeeded(t, s, 1000)
	if _, _, err := s.Refund(ctx, p.ID, money.MustNew(0, "USD")); !errors.Is(err, ErrInvalidInput) {
		t.Errorf("zero refund: %v", err)
	}
	if _, _, err := s.Refund(ctx, p.ID, money.MustNew(10, "EUR")); !errors.Is(err, money.ErrCurrencyMismatch) {
		t.Errorf("currency mismatch: %v", err)
	}
	if _, _, err := s.Refund(ctx, p.ID, money.MustNew(1001, "USD")); !errors.Is(err, ErrRefundExceedsRemaining) {
		t.Errorf("over refund: %v", err)
	}
}

func TestRefundExceedsRemainingAfterPartial(t *testing.T) {
	s, _ := newTestService()
	ctx := context.Background()
	p := succeeded(t, s, 1000)
	if _, _, err := s.Refund(ctx, p.ID, money.MustNew(600, "USD")); err != nil {
		t.Fatal(err)
	}
	if _, _, err := s.Refund(ctx, p.ID, money.MustNew(600, "USD")); !errors.Is(err, ErrRefundExceedsRemaining) {
		t.Fatalf("second refund error = %v, want ErrRefundExceedsRemaining", err)
	}
}

func TestGetNotFoundIsWrapped(t *testing.T) {
	s, _ := newTestService()
	_, err := s.Get(context.Background(), "pay_missing")
	if !errors.Is(err, ErrNotFound) {
		t.Fatalf("error = %v", err)
	}
	if !strings.Contains(err.Error(), "pay_missing") {
		t.Fatalf("error %q lacks the id", err)
	}
}

func TestParseStatus(t *testing.T) {
	for _, in := range []string{"created", "PENDING", " succeeded ", "Declined", "REFUNDED"} {
		if _, err := ParseStatus(in); err != nil {
			t.Errorf("ParseStatus(%q) = %v", in, err)
		}
	}
	if _, err := ParseStatus("VOIDED"); !errors.Is(err, ErrInvalidInput) {
		t.Errorf("ParseStatus(VOIDED) = %v", err)
	}
}
