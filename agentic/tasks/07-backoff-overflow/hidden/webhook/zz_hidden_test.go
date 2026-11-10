package webhook_test

import (
	"context"
	"net/http"
	"testing"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/money"
	"example.com/gopayments/payment"
	"example.com/gopayments/webhook"
)

func TestHiddenBackoffMonotoneAndCapped(t *testing.T) {
	policies := []webhook.Policy{
		{MaxAttempts: 48, BaseDelay: time.Second, MaxDelay: time.Hour},
		{MaxAttempts: 300, BaseDelay: 250 * time.Millisecond, MaxDelay: 10 * time.Minute},
		{MaxAttempts: 300, BaseDelay: 3 * time.Second, MaxDelay: 24 * time.Hour},
		webhook.DefaultPolicy(),
	}
	for _, p := range policies {
		prev := time.Duration(0)
		for n := 1; n <= 300; n++ {
			d := p.Backoff(n)
			if d <= 0 || d > p.MaxDelay || d < prev {
				t.Fatalf("policy %+v: Backoff(%d) = %s (prev %s)", p, n, d, prev)
			}
			prev = d
		}
		if p.Backoff(300) != p.MaxDelay {
			t.Fatalf("policy %+v: Backoff(300) = %s, want cap", p, p.Backoff(300))
		}
	}
}

func TestHiddenBackoffExactSchedule(t *testing.T) {
	p := webhook.Policy{MaxAttempts: 48, BaseDelay: time.Second, MaxDelay: time.Hour}
	want := map[int]time.Duration{1: time.Second, 2: 2 * time.Second, 5: 16 * time.Second, 12: 2048 * time.Second, 13: time.Hour, 40: time.Hour, 64: time.Hour, 65: time.Hour}
	for n, w := range want {
		if got := p.Backoff(n); got != w {
			t.Errorf("Backoff(%d) = %s, want %s", n, got, w)
		}
	}
}

type h07Down struct{ calls int }

func (s *h07Down) Send(context.Context, webhook.Delivery) (int, error) {
	s.calls++
	return http.StatusServiceUnavailable, nil
}

func TestHiddenDispatcherWaitsBetweenAllAttempts(t *testing.T) {
	clk := clock.NewFake(time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC))
	s := &h07Down{}
	pol := webhook.Policy{MaxAttempts: 48, BaseDelay: time.Second, MaxDelay: time.Hour}
	d := webhook.NewDispatcher(s, webhook.StaticEndpoints{"m": {URL: "https://m.example", Secret: "k"}}, clk, pol)
	_ = d.Publish(context.Background(), payment.Event{Type: "payment.succeeded", Payment: payment.Payment{ID: "p", MerchantID: "m", Amount: money.MustNew(1, "USD")}})
	if err := d.Flush(context.Background()); err != nil {
		t.Fatal(err)
	}
	sleeps := clk.Sleeps()
	if s.calls != 48 || len(sleeps) != 47 {
		t.Fatalf("calls %d sleeps %d", s.calls, len(sleeps))
	}
	var total time.Duration
	for i, d := range sleeps {
		if d <= 0 {
			t.Fatalf("sleep #%d = %s", i+1, d)
		}
		total += d
	}
	want := (1+2+4+8+16+32+64+128+256+512+1024+2048)*time.Second + 35*time.Hour
	if total != want {
		t.Fatalf("total wait %s, want %s", total, want)
	}
}
