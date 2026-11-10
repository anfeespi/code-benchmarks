package store

import (
	"context"
	"errors"
	"fmt"
	"testing"

	"example.com/gopayments/money"
	"example.com/gopayments/payment"
)

func seed(t *testing.T, m *Memory, merchant string, n int) []string {
	t.Helper()
	ids := make([]string, 0, n)
	for i := 0; i < n; i++ {
		id := fmt.Sprintf("%s_pay_%03d", merchant, i)
		p := payment.Payment{ID: id, MerchantID: merchant, Amount: money.MustNew(100, "USD"), Status: payment.StatusCreated, Version: 1}
		if err := m.Create(context.Background(), p); err != nil {
			t.Fatal(err)
		}
		ids = append(ids, id)
	}
	return ids
}

func TestCreateGet(t *testing.T) {
	m := NewMemory()
	seed(t, m, "m1", 1)
	p, err := m.Get(context.Background(), "m1_pay_000")
	if err != nil || p.MerchantID != "m1" {
		t.Fatalf("Get = %+v, %v", p, err)
	}
	if _, err := m.Get(context.Background(), "nope"); !errors.Is(err, payment.ErrNotFound) {
		t.Fatalf("missing: %v", err)
	}
	if err := m.Create(context.Background(), p); !errors.Is(err, payment.ErrDuplicate) {
		t.Fatalf("duplicate: %v", err)
	}
}

func TestUpdateOptimisticLocking(t *testing.T) {
	ctx := context.Background()
	m := NewMemory()
	seed(t, m, "m1", 1)
	p, _ := m.Get(ctx, "m1_pay_000")
	stale := p
	p.Status = payment.StatusPending
	if err := m.Update(ctx, p); err != nil {
		t.Fatal(err)
	}
	got, _ := m.Get(ctx, p.ID)
	if got.Version != 2 || got.Status != payment.StatusPending {
		t.Fatalf("after update: %+v", got)
	}
	stale.Status = payment.StatusDeclined
	if err := m.Update(ctx, stale); !errors.Is(err, payment.ErrVersionConflict) {
		t.Fatalf("stale update: %v", err)
	}
}

func TestListFirstPage(t *testing.T) {
	m := NewMemory()
	ids := seed(t, m, "m1", 5)
	seed(t, m, "m2", 3)
	got, next, err := m.ListByMerchant(context.Background(), "m1", payment.Page{Limit: 2})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 || got[0].ID != ids[0] || got[1].ID != ids[1] || next == "" {
		t.Fatalf("page = %v next %q", got, next)
	}
}

func TestListWalksAllPages(t *testing.T) {
	m := NewMemory()
	ids := seed(t, m, "m1", 7)
	var seen []string
	cursor := ""
	for i := 0; i < 10; i++ {
		got, next, err := m.ListByMerchant(context.Background(), "m1", payment.Page{Cursor: cursor, Limit: 3})
		if err != nil {
			t.Fatal(err)
		}
		for _, p := range got {
			seen = append(seen, p.ID)
		}
		if next == "" {
			break
		}
		cursor = next
	}
	if fmt.Sprint(seen) != fmt.Sprint(ids) {
		t.Fatalf("walked %v, want %v", seen, ids)
	}
}

func TestListLimits(t *testing.T) {
	m := NewMemory()
	seed(t, m, "m1", 150)
	tests := []struct {
		limit, want int
	}{
		{0, 20},
		{5, 5},
		{500, 100},
	}
	for _, tt := range tests {
		got, _, err := m.ListByMerchant(context.Background(), "m1", payment.Page{Limit: tt.limit})
		if err != nil || len(got) != tt.want {
			t.Errorf("limit %d: got %d items, err %v", tt.limit, len(got), err)
		}
	}
	if _, _, err := m.ListByMerchant(context.Background(), "m1", payment.Page{Limit: -1}); !errors.Is(err, payment.ErrInvalidInput) {
		t.Errorf("negative limit: %v", err)
	}
	if _, _, err := m.ListByMerchant(context.Background(), "m1", payment.Page{Cursor: "!!"}); !errors.Is(err, payment.ErrInvalidCursor) {
		t.Errorf("bad cursor: %v", err)
	}
}
