package api_test

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"example.com/gopayments/api"
	"example.com/gopayments/clock"
	"example.com/gopayments/idempotency"
	"example.com/gopayments/payment"
	"example.com/gopayments/store"
	"example.com/gopayments/webhook"
)

type h06Sender struct{}

func (h06Sender) Send(context.Context, webhook.Delivery) (int, error) { return http.StatusOK, nil }

func h06Server() http.Handler {
	clk := clock.NewFake(time.Date(2026, 4, 1, 9, 0, 0, 0, time.UTC))
	hooks := webhook.NewDispatcher(h06Sender{}, webhook.StaticEndpoints{}, clk, webhook.DefaultPolicy())
	svc := payment.NewService(store.NewMemory(), clk, payment.NewSeqIDs(), hooks, payment.Config{FeeBps: 290})
	return api.NewServer(svc, idempotency.NewMemory(clk, 24*time.Hour), hooks)
}

func h06Do(t *testing.T, h http.Handler, method, path, body string) (int, map[string]any) {
	t.Helper()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(method, path, bytes.NewBufferString(body)))
	var m map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &m); err != nil {
		t.Fatalf("decode %q: %v", rec.Body.String(), err)
	}
	return rec.Code, m
}

func TestHiddenErrorStatusMapping(t *testing.T) {
	h := h06Server()
	_, p := h06Do(t, h, "POST", "/payments", `{"merchant_id":"m_1","amount":"10.00","currency":"USD"}`)
	succeeded := p["id"].(string)
	h06Do(t, h, "POST", "/payments/"+succeeded+"/authorize", "")
	h06Do(t, h, "POST", "/payments/"+succeeded+"/capture", "")
	_, p = h06Do(t, h, "POST", "/payments", `{"merchant_id":"m_1","amount":"10.00","currency":"USD"}`)
	declined := p["id"].(string)
	h06Do(t, h, "POST", "/payments/"+declined+"/decline", `{"reason":"fraud"}`)

	tests := []struct {
		name, method, path, body string
		wantStatus               int
		wantCode                 string
	}{
		{"get unknown", "GET", "/payments/pay_nope", "", 404, "not_found"},
		{"capture unknown", "POST", "/payments/pay_nope/capture", "", 404, "not_found"},
		{"refund unknown", "POST", "/payments/pay_nope/refunds", `{"amount":"1.00"}`, 404, "not_found"},
		{"capture twice", "POST", "/payments/" + succeeded + "/capture", "", 409, "invalid_transition"},
		{"authorize declined", "POST", "/payments/" + declined + "/authorize", "", 409, "invalid_transition"},
		{"refund declined", "POST", "/payments/" + declined + "/refunds", `{"amount":"1.00"}`, 409, "invalid_transition"},
		{"over refund", "POST", "/payments/" + succeeded + "/refunds", `{"amount":"10.01"}`, 422, "refund_exceeds_remaining"},
		{"refund precision", "POST", "/payments/" + succeeded + "/refunds", `{"amount":"1.001"}`, 400, "invalid_request"},
		{"refund zero", "POST", "/payments/" + succeeded + "/refunds", `{"amount":"0"}`, 400, "invalid_request"},
		{"malformed", "POST", "/payments", `{`, 400, "invalid_request"},
		{"unknown field", "POST", "/payments", `{"merchant_id":"m","amount":"1","currency":"USD","x":1}`, 400, "invalid_request"},
		{"bad amount", "POST", "/payments", `{"merchant_id":"m","amount":"1.234","currency":"USD"}`, 400, "invalid_request"},
		{"bad currency", "POST", "/payments", `{"merchant_id":"m","amount":"1","currency":"ZZZ"}`, 400, "invalid_request"},
		{"missing merchant", "POST", "/payments", `{"amount":"1","currency":"USD"}`, 400, "invalid_request"},
		{"bad limit", "GET", "/merchants/m_1/payments?limit=x", "", 400, "invalid_request"},
		{"negative limit", "GET", "/merchants/m_1/payments?limit=-1", "", 400, "invalid_request"},
		{"bad cursor", "GET", "/merchants/m_1/payments?cursor=%21%21", "", 400, "invalid_request"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			code, body := h06Do(t, h, tt.method, tt.path, tt.body)
			if code != tt.wantStatus {
				t.Fatalf("status %d, want %d: %v", code, tt.wantStatus, body)
			}
			e, _ := body["error"].(map[string]any)
			if e == nil || e["code"] != tt.wantCode {
				t.Fatalf("error body %v, want code %s", body, tt.wantCode)
			}
			if msg, _ := e["message"].(string); msg == "" || msg == "internal error" {
				t.Fatalf("client errors must carry the descriptive message, got %q", msg)
			}
		})
	}
}

func TestHiddenNotFoundMessageHasContext(t *testing.T) {
	_, body := h06Do(t, h06Server(), "GET", "/payments/pay_nope", "")
	e := body["error"].(map[string]any)
	if !strings.Contains(e["message"].(string), "pay_nope") {
		t.Fatalf("message %q should mention the id", e["message"])
	}
}
