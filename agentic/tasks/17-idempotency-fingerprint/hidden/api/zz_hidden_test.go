package api_test

import (
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

type h17Sender struct{}

func (h17Sender) Send(context.Context, webhook.Delivery) (int, error) { return http.StatusOK, nil }

func h17Server() http.Handler {
	clk := clock.NewFake(time.Date(2026, 4, 1, 9, 0, 0, 0, time.UTC))
	hooks := webhook.NewDispatcher(h17Sender{}, webhook.StaticEndpoints{}, clk, webhook.DefaultPolicy())
	svc := payment.NewService(store.NewMemory(), clk, payment.NewSeqIDs(), hooks, payment.Config{FeeBps: 290})
	return api.NewServer(svc, idempotency.NewMemory(clk, 24*time.Hour), hooks)
}

type h17Resp struct {
	code     int
	body     map[string]any
	raw      string
	replayed bool
}

func h17Post(t *testing.T, h http.Handler, path, body, key string) h17Resp {
	t.Helper()
	req := httptest.NewRequest("POST", path, strings.NewReader(body))
	if key != "" {
		req.Header.Set("Idempotency-Key", key)
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	var m map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &m)
	return h17Resp{rec.Code, m, rec.Body.String(), rec.Header().Get("Idempotent-Replayed") == "true"}
}

func h17Count(t *testing.T, h http.Handler, merchant string) int {
	t.Helper()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest("GET", "/merchants/"+merchant+"/payments?limit=100", nil))
	var page struct {
		Data []any `json:"data"`
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &page)
	return len(page.Data)
}

func TestHiddenSemanticallyEqualRetriesReplay(t *testing.T) {
	first := `{"merchant_id":"m_310","amount":"10.50","currency":"USD"}`
	for _, retry := range []string{
		`{"currency": "usd", "amount": "10.5", "merchant_id": "m_310"}`,
		"{\n  \"merchant_id\": \"m_310\",\n  \"currency\": \"USD\",\n  \"amount\": \"10.50\"\n}",
		`{"amount":"10.500","merchant_id":"m_310","currency":"Usd"}`,
		first,
	} {
		h := h17Server()
		a := h17Post(t, h, "/payments", first, "key-1")
		b := h17Post(t, h, "/payments", retry, "key-1")
		if a.code != http.StatusCreated || b.code != http.StatusCreated || !b.replayed || a.raw != b.raw {
			if strings.Contains(retry, "10.500") && b.code == http.StatusBadRequest {
				continue // 10.500 has too many decimals for USD; rejecting it as invalid is also correct
			}
			t.Fatalf("retry %s: first %d, retry %d replayed=%v\n%s\n%s", retry, a.code, b.code, b.replayed, a.raw, b.raw)
		}
		if n := h17Count(t, h, "m_310"); n != 1 {
			t.Fatalf("retry %s created %d payments", retry, n)
		}
	}
}

func TestHiddenDifferentRequestSameKeyRejected(t *testing.T) {
	first := `{"merchant_id":"m_310","amount":"10.50","currency":"USD"}`
	for _, other := range []string{
		`{"merchant_id":"m_310","amount":"10.51","currency":"USD"}`,
		`{"merchant_id":"m_311","amount":"10.50","currency":"USD"}`,
		`{"merchant_id":"m_310","amount":"10.50","currency":"EUR"}`,
		`{"merchant_id":"m_310","amount":"1050","currency":"CLP"}`,
	} {
		h := h17Server()
		h17Post(t, h, "/payments", first, "key-1")
		b := h17Post(t, h, "/payments", other, "key-1")
		if b.code != http.StatusUnprocessableEntity || b.replayed {
			t.Fatalf("different request %s with reused key: %d replayed=%v %s", other, b.code, b.replayed, b.raw)
		}
		if e, _ := b.body["error"].(map[string]any); e == nil || e["code"] != "idempotency_key_reused" {
			t.Fatalf("body %s", b.raw)
		}
	}
}

func TestHiddenRefundRetries(t *testing.T) {
	h := h17Server()
	p := h17Post(t, h, "/payments", `{"merchant_id":"m_1","amount":"50.00","currency":"USD"}`, "")
	id := p.body["id"].(string)
	h17Post(t, h, "/payments/"+id+"/authorize", "", "")
	h17Post(t, h, "/payments/"+id+"/capture", "", "")

	a := h17Post(t, h, "/payments/"+id+"/refunds", `{"amount":"5.00"}`, "r-1")
	b := h17Post(t, h, "/payments/"+id+"/refunds", `{ "amount": "5" }`, "r-1")
	if a.code != http.StatusCreated || b.code != http.StatusCreated || !b.replayed {
		t.Fatalf("refund retry: %d %d replayed=%v %s", a.code, b.code, b.replayed, b.raw)
	}
	c := h17Post(t, h, "/payments/"+id+"/refunds", `{"amount":"6.00"}`, "r-1")
	if c.code != http.StatusUnprocessableEntity {
		t.Fatalf("different refund amount with same key: %d %s", c.code, c.raw)
	}
	d := h17Post(t, h, "/payments/"+id+"/refunds", `{"amount":"5.00"}`, "r-2")
	if d.code != http.StatusCreated || d.replayed || d.body["refunded_amount"] != "10.00" {
		t.Fatalf("new key must create a new refund: %d %s", d.code, d.raw)
	}
}
