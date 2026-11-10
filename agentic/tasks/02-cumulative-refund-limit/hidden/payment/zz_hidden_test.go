package payment_test

import (
	"context"
	"errors"
	"testing"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/money"
	"example.com/gopayments/payment"
	"example.com/gopayments/store"
)

func h02Succeeded(t *testing.T, minor int64) (*payment.Service, payment.Payment) {
	t.Helper()
	ctx := context.Background()
	s := payment.NewService(store.NewMemory(), clock.NewFake(time.Unix(1_800_000_000, 0)), payment.NewSeqIDs(), nil, payment.Config{FeeBps: 290})
	p, err := s.Create(ctx, payment.CreateInput{MerchantID: "m_8812", Amount: money.MustNew(minor, "USD")})
	if err != nil {
		t.Fatal(err)
	}
	if _, err := s.Authorize(ctx, p.ID); err != nil {
		t.Fatal(err)
	}
	if p, err = s.Capture(ctx, p.ID); err != nil {
		t.Fatal(err)
	}
	return s, p
}

func TestHiddenCumulativeRefundsCannotExceedAmount(t *testing.T) {
	tests := []struct {
		name     string
		refunds  []int64
		wantErrs []bool
		refunded int64
		status   payment.Status
	}{
		{"second partial too large", []int64{600, 600}, []bool{false, true}, 600, payment.StatusSucceeded},
		{"exact remainder", []int64{600, 400}, []bool{false, false}, 1000, payment.StatusRefunded},
		{"one cent over", []int64{999, 2}, []bool{false, true}, 999, payment.StatusSucceeded},
		{"many smalls then over", []int64{300, 300, 300, 101, 100}, []bool{false, false, false, true, false}, 1000, payment.StatusRefunded},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			s, p := h02Succeeded(t, 1000)
			for i, amt := range tt.refunds {
				_, _, err := s.Refund(context.Background(), p.ID, money.MustNew(amt, "USD"))
				if tt.wantErrs[i] {
					if !errors.Is(err, payment.ErrRefundExceedsRemaining) {
						t.Fatalf("refund #%d (%d): err = %v, want ErrRefundExceedsRemaining", i, amt, err)
					}
				} else if err != nil {
					t.Fatalf("refund #%d (%d): %v", i, amt, err)
				}
			}
			got, err := s.Get(context.Background(), p.ID)
			if err != nil {
				t.Fatal(err)
			}
			if got.Refunded != tt.refunded || got.Status != tt.status || got.Remaining().Minor != 1000-tt.refunded {
				t.Fatalf("refunded %d status %s remaining %d", got.Refunded, got.Status, got.Remaining().Minor)
			}
		})
	}
}

func TestHiddenRejectedRefundLeavesPaymentUntouched(t *testing.T) {
	s, p := h02Succeeded(t, 1000)
	ctx := context.Background()
	if _, _, err := s.Refund(ctx, p.ID, money.MustNew(700, "USD")); err != nil {
		t.Fatal(err)
	}
	before, _ := s.Get(ctx, p.ID)
	if _, _, err := s.Refund(ctx, p.ID, money.MustNew(301, "USD")); !errors.Is(err, payment.ErrRefundExceedsRemaining) {
		t.Fatalf("err = %v", err)
	}
	after, _ := s.Get(ctx, p.ID)
	if after.Version != before.Version || len(after.Refunds) != 1 || after.Refunded != 700 {
		t.Fatalf("payment changed by rejected refund: %+v", after)
	}
}
