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

type h02Sender struct{}

func (h02Sender) Send(context.Context, webhook.Delivery) (int, error) { return http.StatusOK, nil }

func h02Do(t *testing.T, h http.Handler, method, path, body string) (int, map[string]any) {
	t.Helper()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(method, path, bytes.NewBufferString(body)))
	var m map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &m); err != nil {
		t.Fatalf("decode %q: %v", rec.Body.String(), err)
	}
	return rec.Code, m
}

func TestHiddenAPIOverRefundRejected(t *testing.T) {
	clk := clock.NewFake(time.Date(2026, 4, 1, 9, 0, 0, 0, time.UTC))
	hooks := webhook.NewDispatcher(h02Sender{}, webhook.StaticEndpoints{}, clk, webhook.DefaultPolicy())
	svc := payment.NewService(store.NewMemory(), clk, payment.NewSeqIDs(), hooks, payment.Config{FeeBps: 290})
	h := api.NewServer(svc, idempotency.NewMemory(clk, 24*time.Hour), hooks)

	_, p := h02Do(t, h, "POST", "/payments", `{"merchant_id":"m_8812","amount":"1000.00","currency":"USD"}`)
	id := p["id"].(string)
	h02Do(t, h, "POST", "/payments/"+id+"/authorize", "")
	h02Do(t, h, "POST", "/payments/"+id+"/capture", "")

	if code, _ := h02Do(t, h, "POST", "/payments/"+id+"/refunds", `{"amount":"600.00"}`); code != http.StatusCreated {
		t.Fatalf("first refund: %d", code)
	}
	code, body := h02Do(t, h, "POST", "/payments/"+id+"/refunds", `{"amount":"600.00"}`)
	if code != http.StatusUnprocessableEntity {
		t.Fatalf("second refund: %d %v", code, body)
	}
	if e, _ := body["error"].(map[string]any); e == nil || e["code"] != "refund_exceeds_remaining" {
		t.Fatalf("error body %v", body)
	}
	_, got := h02Do(t, h, "GET", "/payments/"+id, "")
	if got["refunded_amount"] != "600.00" || got["remaining_amount"] != "400.00" || got["status"] != "SUCCEEDED" {
		t.Fatalf("payment after rejected refund: %v", got)
	}
	if code, got := h02Do(t, h, "POST", "/payments/"+id+"/refunds", `{"amount":"400.00"}`); code != http.StatusCreated || got["status"] != "REFUNDED" {
		t.Fatalf("final refund: %d %v", code, got)
	}
}
