package api_test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"example.com/gopayments/api"
	"example.com/gopayments/clock"
	"example.com/gopayments/idempotency"
	"example.com/gopayments/payment"
	"example.com/gopayments/store"
	"example.com/gopayments/webhook"
)

type h10Switch struct {
	mu     sync.Mutex
	status int
}

func (s *h10Switch) Send(context.Context, webhook.Delivery) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.status, nil
}

func h10Req(t *testing.T, h http.Handler, method, path, body string) (int, map[string]any) {
	t.Helper()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(method, path, strings.NewReader(body)))
	var m map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &m); err != nil {
		t.Fatalf("%s %s: decode %q: %v", method, path, rec.Body.String(), err)
	}
	return rec.Code, m
}

func TestHiddenReplayEndpoint(t *testing.T) {
	clk := clock.NewFake(time.Date(2026, 4, 1, 9, 0, 0, 0, time.UTC))
	sw := &h10Switch{status: http.StatusNotFound}
	hooks := webhook.NewDispatcher(sw, webhook.StaticEndpoints{"m_1": {URL: "https://m1.example", Secret: "s"}}, clk, webhook.DefaultPolicy())
	svc := payment.NewService(store.NewMemory(), clk, payment.NewSeqIDs(), hooks, payment.Config{FeeBps: 290})
	h := api.NewServer(svc, idempotency.NewMemory(clk, 24*time.Hour), hooks)

	h10Req(t, h, "POST", "/payments", `{"merchant_id":"m_1","amount":"5.00","currency":"USD"}`)
	h10Req(t, h, "POST", "/payments", `{"merchant_id":"m_1","amount":"6.00","currency":"USD"}`)
	if err := hooks.Flush(context.Background()); err != nil {
		t.Fatal(err)
	}
	_, list := h10Req(t, h, "GET", "/webhooks/dead-letters", "")
	data := list["data"].([]any)
	if len(data) != 2 {
		t.Fatalf("dead letters %v", list)
	}
	first := data[0].(map[string]any)["event_id"].(string)
	second := data[1].(map[string]any)["event_id"].(string)

	code, body := h10Req(t, h, "POST", "/webhooks/dead-letters/"+first+"/replay", "")
	if code != http.StatusOK || body["event_id"] != first || body["delivered"] != false {
		t.Fatalf("replay while still failing: %d %v", code, body)
	}

	sw.mu.Lock()
	sw.status = http.StatusOK
	sw.mu.Unlock()
	code, body = h10Req(t, h, "POST", "/webhooks/dead-letters/"+second+"/replay", "")
	if code != http.StatusOK || body["event_id"] != second || body["delivered"] != true {
		t.Fatalf("replay after fix: %d %v", code, body)
	}
	_, list = h10Req(t, h, "GET", "/webhooks/dead-letters", "")
	if data = list["data"].([]any); len(data) != 1 || data[0].(map[string]any)["event_id"] != first {
		t.Fatalf("dead letters after replay: %v", list)
	}

	code, body = h10Req(t, h, "POST", "/webhooks/dead-letters/evt_nope/replay", "")
	if code != http.StatusNotFound {
		t.Fatalf("unknown: %d %v", code, body)
	}
	if e, _ := body["error"].(map[string]any); e == nil || e["code"] != "not_found" {
		t.Fatalf("unknown body %v", body)
	}
}
