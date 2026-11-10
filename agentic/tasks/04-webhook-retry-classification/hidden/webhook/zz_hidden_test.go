package webhook_test

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"sync"
	"testing"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/money"
	"example.com/gopayments/payment"
	"example.com/gopayments/webhook"
)

type h04Sender struct {
	mu     sync.Mutex
	status int
	err    error
	calls  int
}

func (s *h04Sender) Send(context.Context, webhook.Delivery) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.calls++
	return s.status, s.err
}

func h04Run(t *testing.T, s *h04Sender) (*webhook.Dispatcher, *clock.Fake) {
	t.Helper()
	clk := clock.NewFake(time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC))
	d := webhook.NewDispatcher(s, webhook.StaticEndpoints{"m_77": {URL: "https://m77.example/hook", Secret: "x"}}, clk,
		webhook.Policy{MaxAttempts: 6, BaseDelay: time.Second, MaxDelay: time.Minute})
	p := payment.Payment{ID: "pay_1", MerchantID: "m_77", Amount: money.MustNew(100, "USD"), Status: payment.StatusSucceeded}
	if err := d.Publish(context.Background(), payment.Event{Type: "payment.succeeded", Payment: p}); err != nil {
		t.Fatal(err)
	}
	if err := d.Flush(context.Background()); err != nil {
		t.Fatal(err)
	}
	return d, clk
}

func TestHiddenRetryClassification(t *testing.T) {
	tests := []struct {
		status       int
		err          error
		wantAttempts int
	}{
		{http.StatusBadRequest, nil, 1},
		{http.StatusUnauthorized, nil, 1},
		{http.StatusForbidden, nil, 1},
		{http.StatusNotFound, nil, 1},
		{http.StatusGone, nil, 1},
		{http.StatusUnprocessableEntity, nil, 1},
		{http.StatusMovedPermanently, nil, 1},
		{http.StatusRequestTimeout, nil, 6},
		{http.StatusTooManyRequests, nil, 6},
		{http.StatusInternalServerError, nil, 6},
		{http.StatusBadGateway, nil, 6},
		{http.StatusServiceUnavailable, nil, 6},
		{http.StatusGatewayTimeout, nil, 6},
		{0, errors.New("dial tcp: connection refused"), 6},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%d", tt.status), func(t *testing.T) {
			s := &h04Sender{status: tt.status, err: tt.err}
			d, clk := h04Run(t, s)
			if s.calls != tt.wantAttempts {
				t.Fatalf("attempts = %d, want %d", s.calls, tt.wantAttempts)
			}
			dead := d.DeadLetters()
			if len(dead) != 1 {
				t.Fatalf("dead letters = %d, want 1", len(dead))
			}
			if dead[0].Attempts != tt.wantAttempts || dead[0].LastStatus != tt.status {
				t.Fatalf("dead letter attempts=%d status=%d", dead[0].Attempts, dead[0].LastStatus)
			}
			if got := len(clk.Sleeps()); got != tt.wantAttempts-1 {
				t.Fatalf("sleeps = %d, want %d", got, tt.wantAttempts-1)
			}
		})
	}
}

func TestHiddenSuccessStatuses(t *testing.T) {
	for _, st := range []int{200, 201, 202, 204} {
		s := &h04Sender{status: st}
		d, _ := h04Run(t, s)
		if s.calls != 1 || d.Delivered() != 1 || len(d.DeadLetters()) != 0 {
			t.Fatalf("status %d: calls %d delivered %d dead %d", st, s.calls, d.Delivered(), len(d.DeadLetters()))
		}
	}
}
