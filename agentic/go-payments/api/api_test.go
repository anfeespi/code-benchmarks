package api

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/idempotency"
	"example.com/gopayments/payment"
	"example.com/gopayments/store"
	"example.com/gopayments/webhook"
)

type testAPI struct {
	t     *testing.T
	srv   *Server
	clk   *clock.Fake
	hooks *webhook.Dispatcher
}

type okSender struct{}

func (okSender) Send(_ context.Context, _ webhook.Delivery) (int, error) { return http.StatusOK, nil }

func newTestAPI(t *testing.T) *testAPI {
	clk := clock.NewFake(time.Date(2026, 4, 1, 9, 0, 0, 0, time.UTC))
	hooks := webhook.NewDispatcher(okSender{}, webhook.StaticEndpoints{}, clk, webhook.DefaultPolicy())
	svc := payment.NewService(store.NewMemory(), clk, payment.NewSeqIDs(), hooks, payment.Config{FeeBps: 290})
	return &testAPI{t: t, srv: NewServer(svc, idempotency.NewMemory(clk, 24*time.Hour), hooks), clk: clk, hooks: hooks}
}

func (a *testAPI) do(method, path, body string, headers ...string) *httptest.ResponseRecorder {
	a.t.Helper()
	req := httptest.NewRequest(method, path, bytes.NewBufferString(body))
	for i := 0; i+1 < len(headers); i += 2 {
		req.Header.Set(headers[i], headers[i+1])
	}
	rec := httptest.NewRecorder()
	a.srv.ServeHTTP(rec, req)
	return rec
}

func decode[T any](t *testing.T, rec *httptest.ResponseRecorder) T {
	t.Helper()
	var v T
	if err := json.Unmarshal(rec.Body.Bytes(), &v); err != nil {
		t.Fatalf("decode %q: %v", rec.Body.String(), err)
	}
	return v
}

func (a *testAPI) createSucceeded(amount, currency string) paymentResponse {
	a.t.Helper()
	rec := a.do("POST", "/payments", `{"merchant_id":"m_1","amount":"`+amount+`","currency":"`+currency+`"}`)
	if rec.Code != http.StatusCreated {
		a.t.Fatalf("create: %d %s", rec.Code, rec.Body)
	}
	p := decode[paymentResponse](a.t, rec)
	for _, step := range []string{"authorize", "capture"} {
		if rec := a.do("POST", "/payments/"+p.ID+"/"+step, ""); rec.Code != http.StatusOK {
			a.t.Fatalf("%s: %d %s", step, rec.Code, rec.Body)
		}
	}
	return decode[paymentResponse](a.t, a.do("GET", "/payments/"+p.ID, ""))
}

func TestCreatePayment(t *testing.T) {
	a := newTestAPI(t)
	rec := a.do("POST", "/payments", `{"merchant_id":"m_1","amount":"100.00","currency":"USD"}`)
	if rec.Code != http.StatusCreated {
		t.Fatalf("status %d: %s", rec.Code, rec.Body)
	}
	p := decode[paymentResponse](t, rec)
	if p.Status != "CREATED" || p.Amount != "100.00" || p.Currency != "USD" || p.Fee != "2.90" || p.RemainingAmount != "100.00" {
		t.Fatalf("unexpected payment %+v", p)
	}
}

func TestCreatePaymentValidation(t *testing.T) {
	tests := []struct {
		name, body string
	}{
		{"malformed", `{`},
		{"unknown field", `{"merchant_id":"m","amount":"1","currency":"USD","x":1}`},
		{"bad amount", `{"merchant_id":"m","amount":"1.234","currency":"USD"}`},
		{"bad currency", `{"merchant_id":"m","amount":"1","currency":"ZZZ"}`},
		{"missing merchant", `{"amount":"1","currency":"USD"}`},
		{"zero", `{"merchant_id":"m","amount":"0","currency":"USD"}`},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			a := newTestAPI(t)
			rec := a.do("POST", "/payments", tt.body)
			if rec.Code != http.StatusBadRequest {
				t.Fatalf("status %d: %s", rec.Code, rec.Body)
			}
			if e := decode[errorBody](t, rec); e.Error.Code != "invalid_request" {
				t.Fatalf("code %q", e.Error.Code)
			}
		})
	}
}

func TestLifecycleAndRefund(t *testing.T) {
	a := newTestAPI(t)
	p := a.createSucceeded("50.00", "USD")
	if p.Status != "SUCCEEDED" {
		t.Fatalf("status %s", p.Status)
	}
	rec := a.do("POST", "/payments/"+p.ID+"/refunds", `{"amount":"20.00"}`)
	if rec.Code != http.StatusCreated {
		t.Fatalf("refund: %d %s", rec.Code, rec.Body)
	}
	got := decode[paymentResponse](t, rec)
	if got.RefundedAmount != "20.00" || got.RemainingAmount != "30.00" || len(got.Refunds) != 1 || got.Status != "SUCCEEDED" {
		t.Fatalf("after refund %+v", got)
	}
}

func TestErrorMapping(t *testing.T) {
	a := newTestAPI(t)
	p := a.createSucceeded("10.00", "USD")
	tests := []struct {
		name, method, path, body string
		wantStatus               int
		wantCode                 string
	}{
		{"unknown payment", "GET", "/payments/pay_nope", "", http.StatusNotFound, "not_found"},
		{"capture twice", "POST", "/payments/" + p.ID + "/capture", "", http.StatusConflict, "invalid_transition"},
		{"refund too much", "POST", "/payments/" + p.ID + "/refunds", `{"amount":"10.01"}`, http.StatusUnprocessableEntity, "refund_exceeds_remaining"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			rec := a.do(tt.method, tt.path, tt.body)
			if rec.Code != tt.wantStatus {
				t.Fatalf("status %d, want %d: %s", rec.Code, tt.wantStatus, rec.Body)
			}
			if e := decode[errorBody](t, rec); e.Error.Code != tt.wantCode {
				t.Fatalf("code %q, want %q", e.Error.Code, tt.wantCode)
			}
		})
	}
}

func TestIdempotentCreateReplays(t *testing.T) {
	a := newTestAPI(t)
	body := `{"merchant_id":"m_1","amount":"10.00","currency":"USD"}`
	first := a.do("POST", "/payments", body, IdempotencyKeyHeader, "abc")
	second := a.do("POST", "/payments", body, IdempotencyKeyHeader, "abc")
	if first.Code != http.StatusCreated || second.Code != http.StatusCreated {
		t.Fatalf("codes %d %d", first.Code, second.Code)
	}
	if second.Header().Get(ReplayedHeader) != "true" || first.Body.String() != second.Body.String() {
		t.Fatalf("not replayed: %s vs %s", first.Body, second.Body)
	}
	other := a.do("POST", "/payments", `{"merchant_id":"m_1","amount":"11.00","currency":"USD"}`, IdempotencyKeyHeader, "abc")
	if other.Code != http.StatusUnprocessableEntity {
		t.Fatalf("reuse with other body: %d %s", other.Code, other.Body)
	}
}

func TestListPayments(t *testing.T) {
	a := newTestAPI(t)
	for i := 0; i < 3; i++ {
		a.do("POST", "/payments", `{"merchant_id":"m_1","amount":"1.00","currency":"USD"}`)
	}
	rec := a.do("GET", "/merchants/m_1/payments?limit=2", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	page := decode[listResponse](t, rec)
	if len(page.Data) != 2 || page.NextCursor == "" {
		t.Fatalf("page %+v", page)
	}
	if rec := a.do("GET", "/merchants/m_1/payments?limit=x", ""); rec.Code != http.StatusBadRequest {
		t.Fatalf("bad limit status %d", rec.Code)
	}
}

func TestDeadLettersEmpty(t *testing.T) {
	a := newTestAPI(t)
	rec := a.do("GET", "/webhooks/dead-letters", "")
	if rec.Code != http.StatusOK || rec.Body.String() != "{\"data\":[]}\n" {
		t.Fatalf("got %d %q", rec.Code, rec.Body)
	}
}
