package payment_test

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/money"
	"example.com/gopayments/payment"
	"example.com/gopayments/store"
)

func TestHiddenConcurrentRefundsStayConsistent(t *testing.T) {
	for round := 0; round < 10; round++ {
		ctx := context.Background()
		repo := store.NewMemory()
		s := payment.NewService(repo, clock.NewFake(time.Unix(1_800_000_000, 0)), payment.NewSeqIDs(), nil, payment.Config{FeeBps: 290})
		p, _ := s.Create(ctx, payment.CreateInput{MerchantID: "m", Amount: money.MustNew(100000, "USD")})
		_, _ = s.Authorize(ctx, p.ID)
		_, _ = s.Capture(ctx, p.ID)
		for i := 0; i < 3; i++ {
			if _, _, err := s.Refund(ctx, p.ID, money.MustNew(10, "USD")); err != nil {
				t.Fatal(err)
			}
		}
		var wg sync.WaitGroup
		var mu sync.Mutex
		okIDs := map[string]int64{}
		gate := make(chan struct{})
		for g := 0; g < 24; g++ {
			wg.Add(1)
			go func(g int) {
				defer wg.Done()
				<-gate
				amt := int64(g + 1)
				_, r, err := s.Refund(ctx, p.ID, money.MustNew(amt, "USD"))
				if err == nil {
					mu.Lock()
					okIDs[r.ID] = amt
					mu.Unlock()
				} else if !errors.Is(err, payment.ErrVersionConflict) {
					t.Errorf("refund: %v", err)
				}
			}(g)
		}
		close(gate)
		wg.Wait()

		got, err := s.Get(ctx, p.ID)
		if err != nil {
			t.Fatal(err)
		}
		var sum int64
		for _, r := range got.Refunds {
			sum += r.Amount.Minor
		}
		if sum != got.Refunded || len(got.Refunds) != 3+len(okIDs) {
			t.Fatalf("round %d: refunds sum %d, Refunded %d, %d refunds, %d successful calls", round, sum, got.Refunded, len(got.Refunds), len(okIDs))
		}
		for _, r := range got.Refunds[3:] {
			if amt, ok := okIDs[r.ID]; !ok || amt != r.Amount.Minor {
				t.Fatalf("round %d: stored refund %s (%d) was never returned to a caller", round, r.ID, r.Amount.Minor)
			}
		}
	}
}

func TestHiddenRepositoryDoesNotAliasCallers(t *testing.T) {
	ctx := context.Background()
	repo := store.NewMemory()
	refunds := make([]payment.Refund, 1, 8)
	refunds[0] = payment.Refund{ID: "ref_1", Amount: money.MustNew(5, "USD")}
	p := payment.Payment{ID: "pay_1", MerchantID: "m", Amount: money.MustNew(100, "USD"), Refunded: 5, Status: payment.StatusSucceeded, Refunds: refunds, Version: 1}
	if err := repo.Create(ctx, p); err != nil {
		t.Fatal(err)
	}
	refunds[0].ID = "mutated-after-create"

	got, _ := repo.Get(ctx, "pay_1")
	if got.Refunds[0].ID != "ref_1" {
		t.Fatalf("Create kept the caller's slice: %s", got.Refunds[0].ID)
	}
	got.Refunds[0].ID = "mutated-after-get"
	_ = append(got.Refunds, payment.Refund{ID: "appended"})
	again, _ := repo.Get(ctx, "pay_1")
	if again.Refunds[0].ID != "ref_1" {
		t.Fatalf("Get returned shared state: %s", again.Refunds[0].ID)
	}

	upd := again
	upd.Refunds = append(upd.Refunds, payment.Refund{ID: "ref_2", Amount: money.MustNew(5, "USD")})
	upd.Refunded = 10
	if err := repo.Update(ctx, upd); err != nil {
		t.Fatal(err)
	}
	upd.Refunds[1].ID = "mutated-after-update"
	stored, _ := repo.Get(ctx, "pay_1")
	if len(stored.Refunds) != 2 || stored.Refunds[1].ID != "ref_2" || stored.Version != 2 {
		t.Fatalf("Update kept the caller's slice: %+v", stored.Refunds)
	}
	list, _, _ := repo.ListByMerchant(ctx, "m", payment.Page{})
	list[0].Refunds[0].ID = "mutated-after-list"
	if final, _ := repo.Get(ctx, "pay_1"); final.Refunds[0].ID != "ref_1" {
		t.Fatalf("ListByMerchant returned shared state: %s", final.Refunds[0].ID)
	}
	stale := again
	stale.Refunds = append(stale.Refunds, payment.Refund{ID: "ghost"})
	if err := repo.Update(ctx, stale); !errors.Is(err, payment.ErrVersionConflict) {
		t.Fatalf("stale update: %v", err)
	}
	if final, _ := repo.Get(ctx, "pay_1"); len(final.Refunds) != 2 || final.Refunds[1].ID != "ref_2" {
		t.Fatalf("failed update leaked into storage: %+v", final.Refunds)
	}
}
