package api_test

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"example.com/gopayments/api"
	"example.com/gopayments/clock"
	"example.com/gopayments/idempotency"
	"example.com/gopayments/money"
	"example.com/gopayments/payment"
	"example.com/gopayments/store"
	"example.com/gopayments/webhook"
)

type h09Sender struct{}

func (h09Sender) Send(context.Context, webhook.Delivery) (int, error) { return http.StatusOK, nil }

type h09Page struct {
	Data []struct {
		ID     string `json:"id"`
		Status string `json:"status"`
	} `json:"data"`
	NextCursor string `json:"next_cursor"`
}

// h09Fixture creates 37 payments for m_1 cycling through statuses, plus noise for m_2.
func h09Fixture(t *testing.T) (http.Handler, map[string][]string) {
	t.Helper()
	clk := clock.NewFake(time.Date(2026, 4, 1, 9, 0, 0, 0, time.UTC))
	hooks := webhook.NewDispatcher(h09Sender{}, webhook.StaticEndpoints{}, clk, webhook.DefaultPolicy())
	svc := payment.NewService(store.NewMemory(), clk, payment.NewSeqIDs(), hooks, payment.Config{FeeBps: 290})
	h := api.NewServer(svc, idempotency.NewMemory(clk, 24*time.Hour), hooks)
	ctx := context.Background()
	byStatus := map[string][]string{}
	for i := 0; i < 45; i++ {
		merchant := "m_1"
		if i%5 == 4 {
			merchant = "m_2"
		}
		p, err := svc.Create(ctx, payment.CreateInput{MerchantID: merchant, Amount: money.MustNew(1000, "USD")})
		if err != nil {
			t.Fatal(err)
		}
		switch i % 3 {
		case 1:
			_, _ = svc.Authorize(ctx, p.ID)
			p, _ = svc.Capture(ctx, p.ID)
		case 2:
			p, _ = svc.Decline(ctx, p.ID, "nsf")
		}
		if i%7 == 0 && p.Status == payment.StatusSucceeded {
			p, _, _ = svc.Refund(ctx, p.ID, money.MustNew(1000, "USD"))
		}
		if merchant == "m_1" {
			byStatus[string(p.Status)] = append(byStatus[string(p.Status)], p.ID)
			byStatus[""] = append(byStatus[""], p.ID)
		}
	}
	return h, byStatus
}

func h09Get(t *testing.T, h http.Handler, url string) (int, h09Page, string) {
	t.Helper()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest("GET", url, nil))
	var p h09Page
	if rec.Code == http.StatusOK {
		if err := json.Unmarshal(rec.Body.Bytes(), &p); err != nil {
			t.Fatalf("decode: %v", err)
		}
	}
	return rec.Code, p, rec.Body.String()
}

func TestHiddenStatusFilterPaginates(t *testing.T) {
	h, byStatus := h09Fixture(t)
	for _, tc := range []struct {
		query, key string
		limit      int
	}{
		{"SUCCEEDED", "SUCCEEDED", 3},
		{"succeeded", "SUCCEEDED", 4},
		{"Declined", "DECLINED", 5},
		{"CREATED", "CREATED", 2},
		{"REFUNDED", "REFUNDED", 1},
		{"PENDING", "PENDING", 10},
		{"", "", 7},
	} {
		t.Run(fmt.Sprintf("%s/%d", tc.query, tc.limit), func(t *testing.T) {
			want := byStatus[tc.key]
			var got []string
			cursor := ""
			for pages := 0; pages < 100; pages++ {
				url := fmt.Sprintf("/merchants/m_1/payments?limit=%d", tc.limit)
				if tc.query != "" {
					url += "&status=" + tc.query
				}
				if cursor != "" {
					url += "&cursor=" + cursor
				}
				code, page, raw := h09Get(t, h, url)
				if code != http.StatusOK {
					t.Fatalf("status %d: %s", code, raw)
				}
				if page.NextCursor != "" && len(page.Data) != tc.limit {
					t.Fatalf("non-final page has %d items, want %d", len(page.Data), tc.limit)
				}
				for _, p := range page.Data {
					if tc.key != "" && p.Status != tc.key {
						t.Fatalf("got %s payment in %s listing", p.Status, tc.key)
					}
					got = append(got, p.ID)
				}
				if page.NextCursor == "" {
					break
				}
				cursor = page.NextCursor
			}
			if strings.Join(got, ",") != strings.Join(want, ",") {
				t.Fatalf("got %v\nwant %v", got, want)
			}
		})
	}
}

func TestHiddenStatusFilterInvalid(t *testing.T) {
	h, _ := h09Fixture(t)
	for _, q := range []string{"VOIDED", "succeed", "1"} {
		code, _, raw := h09Get(t, h, "/merchants/m_1/payments?status="+q)
		if code != http.StatusBadRequest || !strings.Contains(raw, `"invalid_request"`) {
			t.Fatalf("status=%s: %d %s", q, code, raw)
		}
	}
}
