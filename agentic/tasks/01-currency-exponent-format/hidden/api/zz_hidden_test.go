package api_test

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"example.com/gopayments/api"
	"example.com/gopayments/clock"
	"example.com/gopayments/idempotency"
	"example.com/gopayments/payment"
	"example.com/gopayments/store"
	"example.com/gopayments/webhook"
)

type h01Sender struct{}

func (h01Sender) Send(context.Context, webhook.Delivery) (int, error) { return http.StatusOK, nil }

func h01Server() http.Handler {
	clk := clock.NewFake(time.Date(2026, 4, 1, 9, 0, 0, 0, time.UTC))
	hooks := webhook.NewDispatcher(h01Sender{}, webhook.StaticEndpoints{}, clk, webhook.DefaultPolicy())
	svc := payment.NewService(store.NewMemory(), clk, payment.NewSeqIDs(), hooks, payment.Config{FeeBps: 290})
	return api.NewServer(svc, idempotency.NewMemory(clk, 24*time.Hour), hooks)
}

func h01Do(t *testing.T, h http.Handler, method, path, body string) (int, map[string]any) {
	t.Helper()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(method, path, bytes.NewBufferString(body)))
	var m map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &m); err != nil {
		t.Fatalf("decode %q: %v", rec.Body.String(), err)
	}
	return rec.Code, m
}

func TestHiddenAPIRendersCurrencyExponent(t *testing.T) {
	tests := []struct {
		amount, currency       string
		wantAmount, wantFee    string
		wantRemaining          string
	}{
		{"15000", "CLP", "15000", "435", "15000"},
		{"1500", "JPY", "1500", "44", "1500"},
		{"1.234", "KWD", "1.234", "0.036", "1.234"},
		{"100.00", "USD", "100.00", "2.90", "100.00"},
	}
	for _, tt := range tests {
		t.Run(tt.currency, func(t *testing.T) {
			h := h01Server()
			code, p := h01Do(t, h, "POST", "/payments", `{"merchant_id":"m_1","amount":"`+tt.amount+`","currency":"`+tt.currency+`"}`)
			if code != http.StatusCreated {
				t.Fatalf("create: %d %v", code, p)
			}
			if p["amount"] != tt.wantAmount || p["fee"] != tt.wantFee || p["remaining_amount"] != tt.wantRemaining {
				t.Fatalf("got amount=%v fee=%v remaining=%v", p["amount"], p["fee"], p["remaining_amount"])
			}
			_, got := h01Do(t, h, "GET", "/payments/"+p["id"].(string), "")
			if got["amount"] != tt.wantAmount {
				t.Fatalf("GET amount = %v", got["amount"])
			}
		})
	}
}
