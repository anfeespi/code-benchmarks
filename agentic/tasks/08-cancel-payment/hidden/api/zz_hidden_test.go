package api_test

import (
	"bytes"
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

type h08Sender struct {
	mu     sync.Mutex
	bodies []string
}

func (s *h08Sender) Send(_ context.Context, d webhook.Delivery) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.bodies = append(s.bodies, string(d.Body))
	return http.StatusOK, nil
}

func h08Do(t *testing.T, h http.Handler, method, path string) (int, map[string]any) {
	t.Helper()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(method, path, bytes.NewBufferString("")))
	var m map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &m); err != nil {
		t.Fatalf("%s %s: decode %q: %v", method, path, rec.Body.String(), err)
	}
	return rec.Code, m
}

func TestHiddenCancelEndpoint(t *testing.T) {
	clk := clock.NewFake(time.Date(2026, 4, 1, 9, 0, 0, 0, time.UTC))
	sender := &h08Sender{}
	hooks := webhook.NewDispatcher(sender, webhook.StaticEndpoints{"m_1": {URL: "https://m1.example", Secret: "s"}}, clk, webhook.DefaultPolicy())
	svc := payment.NewService(store.NewMemory(), clk, payment.NewSeqIDs(), hooks, payment.Config{FeeBps: 290})
	h := api.NewServer(svc, idempotency.NewMemory(clk, 24*time.Hour), hooks)

	create := func() string {
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, httptest.NewRequest("POST", "/payments", strings.NewReader(`{"merchant_id":"m_1","amount":"5.00","currency":"USD"}`)))
		var m map[string]any
		_ = json.Unmarshal(rec.Body.Bytes(), &m)
		return m["id"].(string)
	}

	a := create()
	code, body := h08Do(t, h, "POST", "/payments/"+a+"/cancel")
	if code != http.StatusOK || body["status"] != "CANCELED" || body["id"] != a {
		t.Fatalf("cancel created: %d %v", code, body)
	}
	if code, body = h08Do(t, h, "POST", "/payments/"+a+"/cancel"); code != http.StatusConflict {
		t.Fatalf("cancel twice: %d %v", code, body)
	}
	if e, _ := body["error"].(map[string]any); e == nil || e["code"] != "invalid_transition" {
		t.Fatalf("error body %v", body)
	}
	if code, _ = h08Do(t, h, "POST", "/payments/"+a+"/authorize"); code != http.StatusConflict {
		t.Fatalf("authorize after cancel: %d", code)
	}

	b := create()
	h08Do(t, h, "POST", "/payments/"+b+"/authorize")
	if code, body = h08Do(t, h, "POST", "/payments/"+b+"/cancel"); code != http.StatusOK || body["status"] != "CANCELED" {
		t.Fatalf("cancel pending: %d %v", code, body)
	}

	c := create()
	h08Do(t, h, "POST", "/payments/"+c+"/authorize")
	h08Do(t, h, "POST", "/payments/"+c+"/capture")
	if code, _ = h08Do(t, h, "POST", "/payments/"+c+"/cancel"); code != http.StatusConflict {
		t.Fatalf("cancel succeeded: %d", code)
	}
	if code, body = h08Do(t, h, "POST", "/payments/pay_nope/cancel"); code != http.StatusNotFound {
		t.Fatalf("cancel unknown: %d %v", code, body)
	}
	if code, body = h08Do(t, h, "GET", "/payments/"+a); body["status"] != "CANCELED" {
		t.Fatalf("GET after cancel: %d %v", code, body)
	}

	if err := hooks.Flush(context.Background()); err != nil {
		t.Fatal(err)
	}
	canceled := 0
	for _, b := range sender.bodies {
		if strings.Contains(b, `"type":"payment.canceled"`) {
			canceled++
		}
	}
	if canceled != 2 {
		t.Fatalf("payment.canceled webhooks = %d, want 2", canceled)
	}
}
