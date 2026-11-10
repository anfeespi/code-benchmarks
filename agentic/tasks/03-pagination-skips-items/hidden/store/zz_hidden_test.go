package store_test

import (
	"context"
	"fmt"
	"testing"

	"example.com/gopayments/money"
	"example.com/gopayments/payment"
	"example.com/gopayments/store"
)

func h03Seed(t *testing.T, m *store.Memory, merchant string, n int) []string {
	t.Helper()
	var ids []string
	for i := 0; i < n; i++ {
		id := fmt.Sprintf("%s_%04d", merchant, i)
		if err := m.Create(context.Background(), payment.Payment{ID: id, MerchantID: merchant, Amount: money.MustNew(100, "USD"), Status: payment.StatusCreated, Version: 1}); err != nil {
			t.Fatal(err)
		}
		ids = append(ids, id)
	}
	return ids
}

func h03Walk(t *testing.T, m *store.Memory, merchant string, limit int) ([]string, int) {
	t.Helper()
	var seen []string
	cursor, pages := "", 0
	pageSize := limit
	if pageSize == 0 {
		pageSize = 20
	}
	for pages < 10000 {
		got, next, err := m.ListByMerchant(context.Background(), merchant, payment.Page{Cursor: cursor, Limit: limit})
		if err != nil {
			t.Fatal(err)
		}
		pages++
		if next != "" && len(got) != pageSize {
			t.Fatalf("non-final page %d has %d items, want %d", pages, len(got), pageSize)
		}
		for _, p := range got {
			seen = append(seen, p.ID)
		}
		if next == "" {
			break
		}
		cursor = next
	}
	return seen, pages
}

func TestHiddenWalkReturnsEverythingOnce(t *testing.T) {
	tests := []struct {
		n, limit, wantPages int
	}{
		{7, 3, 3},
		{6, 3, 2},
		{10, 1, 10},
		{1000, 50, 20},
		{1001, 50, 21},
		{5, 100, 1},
		{0, 10, 1},
		{45, 0, 3}, // default limit 20
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("n=%d/limit=%d", tt.n, tt.limit), func(t *testing.T) {
			m := store.NewMemory()
			h03Seed(t, m, "other", 3)
			want := h03Seed(t, m, "m_204", tt.n)
			got, pages := h03Walk(t, m, "m_204", tt.limit)
			if fmt.Sprint(got) != fmt.Sprint(want) {
				t.Fatalf("walked %d items, want %d (first diff hidden in %v)", len(got), len(want), got[:min(len(got), 5)])
			}
			if pages != tt.wantPages {
				t.Fatalf("pages = %d, want %d", pages, tt.wantPages)
			}
		})
	}
}

func TestHiddenSecondPageStartsAfterFirst(t *testing.T) {
	m := store.NewMemory()
	ids := h03Seed(t, m, "m", 5)
	_, next, err := m.ListByMerchant(context.Background(), "m", payment.Page{Limit: 2})
	if err != nil {
		t.Fatal(err)
	}
	got, _, err := m.ListByMerchant(context.Background(), "m", payment.Page{Cursor: next, Limit: 2})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 || got[0].ID != ids[2] || got[1].ID != ids[3] {
		t.Fatalf("second page = %v", got)
	}
}
