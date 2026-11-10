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

type h11Sender struct{}

func (h11Sender) Send(context.Context, webhook.Delivery) (int, error) { return http.StatusOK, nil }

func h11Server() http.Handler {
	clk := clock.NewFake(time.Date(2026, 4, 1, 9, 0, 0, 0, time.UTC))
	hooks := webhook.NewDispatcher(h11Sender{}, webhook.StaticEndpoints{}, clk, webhook.DefaultPolicy())
	svc := payment.NewService(store.NewMemory(), clk, payment.NewSeqIDs(), hooks, payment.Config{FeeBps: 290})
	return api.NewServer(svc, idempotency.NewMemory(clk, 24*time.Hour), hooks)
}

func h11Do(t *testing.T, h http.Handler, method, path, body string, hdr ...string) (int, map[string]any, http.Header) {
	t.Helper()
	req := httptest.NewRequest(method, path, strings.NewReader(body))
	for i := 0; i+1 < len(hdr); i += 2 {
		req.Header.Set(hdr[i], hdr[i+1])
	}
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	var m map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &m); err != nil {
		t.Fatalf("%s %s: decode %q: %v", method, path, rec.Body.String(), err)
	}
	return rec.Code, m, rec.Header()
}

func h11Num(t *testing.T, m map[string]any, k string) int64 {
	t.Helper()
	v, ok := m[k].(float64)
	if !ok {
		t.Fatalf("field %s missing or not a number in %v", k, m)
	}
	return int64(v)
}

func TestHiddenCreateAcceptsBothFormats(t *testing.T) {
	tests := []struct {
		name, body                 string
		wantAmount, wantCurrency   string
		wantMinor, wantFeeMinor    int64
	}{
		{"legacy", `{"merchant_id":"m","amount":"10.50","currency":"USD"}`, "10.50", "USD", 1050, 30},
		{"minor", `{"merchant_id":"m","amount_minor":1050,"currency":"USD"}`, "10.50", "USD", 1050, 30},
		{"both agree", `{"merchant_id":"m","amount":"10.5","amount_minor":1050,"currency":"USD"}`, "10.50", "USD", 1050, 30},
		{"minor CLP", `{"merchant_id":"m","amount_minor":15000,"currency":"CLP"}`, "15000", "CLP", 15000, 435},
		{"minor KWD", `{"merchant_id":"m","amount_minor":1234,"currency":"kwd"}`, "1.234", "KWD", 1234, 36},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			code, p, _ := h11Do(t, h11Server(), "POST", "/payments", tt.body)
			if code != http.StatusCreated {
				t.Fatalf("status %d: %v", code, p)
			}
			if p["amount"] != tt.wantAmount || p["currency"] != tt.wantCurrency {
				t.Fatalf("legacy fields changed: %v", p)
			}
			if h11Num(t, p, "amount_minor") != tt.wantMinor || h11Num(t, p, "fee_minor") != tt.wantFeeMinor ||
				h11Num(t, p, "refunded_minor") != 0 || h11Num(t, p, "remaining_minor") != tt.wantMinor {
				t.Fatalf("minor fields wrong: %v", p)
			}
		})
	}
}

func TestHiddenCreateRejectsInvalid(t *testing.T) {
	for _, body := range []string{
		`{"merchant_id":"m","currency":"USD"}`,
		`{"merchant_id":"m","amount":"10.50","amount_minor":1051,"currency":"USD"}`,
		`{"merchant_id":"m","amount":"10.505","amount_minor":1050,"currency":"USD"}`,
		`{"merchant_id":"m","amount_minor":0,"currency":"USD"}`,
		`{"merchant_id":"m","amount_minor":-5,"currency":"USD"}`,
		`{"merchant_id":"m","amount_minor":10.5,"currency":"USD"}`,
		`{"merchant_id":"m","amount_minor":"1050","currency":"USD"}`,
		`{"merchant_id":"m","amount_minor":100,"currency":"ZZZ"}`,
		`{"merchant_id":"m","amount_minor":100,"currency":"USD","amount_major":1}`,
	} {
		code, p, _ := h11Do(t, h11Server(), "POST", "/payments", body)
		if code != http.StatusBadRequest {
			t.Errorf("%s: status %d %v", body, code, p)
			continue
		}
		if e, _ := p["error"].(map[string]any); e == nil || e["code"] != "invalid_request" {
			t.Errorf("%s: body %v", body, p)
		}
	}
}

func TestHiddenRefundAcceptsMinor(t *testing.T) {
	h := h11Server()
	_, p, _ := h11Do(t, h, "POST", "/payments", `{"merchant_id":"m","amount_minor":10000,"currency":"USD"}`)
	id := p["id"].(string)
	h11Do(t, h, "POST", "/payments/"+id+"/authorize", "")
	h11Do(t, h, "POST", "/payments/"+id+"/capture", "")

	code, p, _ := h11Do(t, h, "POST", "/payments/"+id+"/refunds", `{"amount_minor":2550}`)
	if code != http.StatusCreated || p["refunded_amount"] != "25.50" || h11Num(t, p, "refunded_minor") != 2550 || h11Num(t, p, "remaining_minor") != 7450 {
		t.Fatalf("minor refund: %d %v", code, p)
	}
	refunds := p["refunds"].([]any)
	if r := refunds[0].(map[string]any); r["amount"] != "25.50" || h11Num(t, r, "amount_minor") != 2550 {
		t.Fatalf("refund item %v", r)
	}
	if code, p, _ = h11Do(t, h, "POST", "/payments/"+id+"/refunds", `{"amount":"1.00"}`); code != http.StatusCreated || h11Num(t, p, "refunded_minor") != 2650 {
		t.Fatalf("legacy refund: %d %v", code, p)
	}
	for _, body := range []string{`{}`, `{"amount":"1.00","amount_minor":101}`, `{"amount_minor":0}`} {
		if code, p, _ = h11Do(t, h, "POST", "/payments/"+id+"/refunds", body); code != http.StatusBadRequest {
			t.Errorf("refund %s: %d %v", body, code, p)
		}
	}
	if code, _, _ = h11Do(t, h, "POST", "/payments/"+id+"/refunds", `{"amount_minor":7351}`); code != http.StatusUnprocessableEntity {
		t.Errorf("over refund status %d", code)
	}
	_, list, _ := h11Do(t, h, "GET", "/merchants/m/payments", "")
	item := list["data"].([]any)[0].(map[string]any)
	if h11Num(t, item, "amount_minor") != 10000 || h11Num(t, item, "refunded_minor") != 2650 {
		t.Fatalf("list item %v", item)
	}
}

func TestHiddenIdempotencyAcrossFormats(t *testing.T) {
	h := h11Server()
	code1, p1, _ := h11Do(t, h, "POST", "/payments", `{"merchant_id":"m","amount":"10.50","currency":"USD"}`, "Idempotency-Key", "k1")
	code2, p2, hdr := h11Do(t, h, "POST", "/payments", `{"merchant_id":"m","amount_minor":1050,"currency":"USD"}`, "Idempotency-Key", "k1")
	if code1 != http.StatusCreated || code2 != http.StatusCreated || p1["id"] != p2["id"] || hdr.Get("Idempotent-Replayed") != "true" {
		t.Fatalf("cross-format retry not replayed: %d %v / %d %v", code1, p1, code2, p2)
	}
	code3, p3, _ := h11Do(t, h, "POST", "/payments", `{"merchant_id":"m","amount_minor":1051,"currency":"USD"}`, "Idempotency-Key", "k1")
	if code3 != http.StatusUnprocessableEntity {
		t.Fatalf("different amount with same key: %d %v", code3, p3)
	}
}
