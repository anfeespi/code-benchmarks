package webhook_test

import (
	"context"
	"errors"
	"net/http"
	"sync"
	"testing"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/money"
	"example.com/gopayments/payment"
	"example.com/gopayments/webhook"
)

type h10Sender struct {
	mu     sync.Mutex
	status int
	got    []webhook.Delivery
}

func (s *h10Sender) set(st int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.status = st
}

func (s *h10Sender) Send(_ context.Context, d webhook.Delivery) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.got = append(s.got, d)
	return s.status, nil
}

func h10Setup(t *testing.T, n int) (*webhook.Dispatcher, *h10Sender, *clock.Fake) {
	t.Helper()
	clk := clock.NewFake(time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC))
	s := &h10Sender{status: http.StatusGone}
	d := webhook.NewDispatcher(s, webhook.StaticEndpoints{"m": {URL: "https://m.example/hook", Secret: "sec"}}, clk,
		webhook.Policy{MaxAttempts: 3, BaseDelay: time.Second, MaxDelay: time.Minute})
	for i := 0; i < n; i++ {
		p := payment.Payment{ID: "pay_" + string(rune('a'+i)), MerchantID: "m", Amount: money.MustNew(100, "USD"), Status: payment.StatusSucceeded}
		if err := d.Publish(context.Background(), payment.Event{Type: "payment.succeeded", Payment: p}); err != nil {
			t.Fatal(err)
		}
	}
	if err := d.Flush(context.Background()); err != nil {
		t.Fatal(err)
	}
	if len(d.DeadLetters()) != n {
		t.Fatalf("setup: %d dead letters", len(d.DeadLetters()))
	}
	return d, s, clk
}

func TestHiddenReplayDelivers(t *testing.T) {
	d, s, clk := h10Setup(t, 3)
	target := d.DeadLetters()[1]
	firstBody := string(s.got[1].Body)
	s.set(http.StatusOK)
	clk.Advance(time.Hour)
	delivered, err := d.Replay(context.Background(), target.Event.ID)
	if err != nil || !delivered {
		t.Fatalf("Replay = %v, %v", delivered, err)
	}
	last := s.got[len(s.got)-1]
	if last.EventID != target.Event.ID || last.Headers["Webhook-Id"] != target.Event.ID || string(last.Body) != firstBody {
		t.Fatalf("replayed a different event: id %s body %s", last.EventID, last.Body)
	}
	if err := webhook.Verify("sec", last.Headers[webhook.SignatureHeader], last.Body, clk.Now(), time.Minute); err != nil {
		t.Fatalf("replay signature must be fresh: %v", err)
	}
	dead := d.DeadLetters()
	if len(dead) != 2 {
		t.Fatalf("dead letters = %d, want 2", len(dead))
	}
	for _, dl := range dead {
		if dl.Event.ID == target.Event.ID {
			t.Fatal("delivered event still dead-lettered")
		}
	}
	if d.Delivered() != 1 {
		t.Fatalf("Delivered = %d", d.Delivered())
	}
}

func TestHiddenReplayFailsAgain(t *testing.T) {
	d, s, _ := h10Setup(t, 2)
	target := d.DeadLetters()[0]
	s.set(http.StatusServiceUnavailable)
	delivered, err := d.Replay(context.Background(), target.Event.ID)
	if err != nil || delivered {
		t.Fatalf("Replay = %v, %v", delivered, err)
	}
	dead := d.DeadLetters()
	count := 0
	for _, dl := range dead {
		if dl.Event.ID == target.Event.ID {
			count++
			if dl.Attempts != 3 || dl.LastStatus != http.StatusServiceUnavailable {
				t.Fatalf("dead letter not updated: attempts %d status %d", dl.Attempts, dl.LastStatus)
			}
		}
	}
	if count != 1 || len(dead) != 2 {
		t.Fatalf("event appears %d times, %d dead letters total", count, len(dead))
	}
}

func TestHiddenReplayUnknown(t *testing.T) {
	d, _, _ := h10Setup(t, 1)
	_, err := d.Replay(context.Background(), "evt_nope")
	if !errors.Is(err, webhook.ErrDeadLetterNotFound) {
		t.Fatalf("err = %v", err)
	}
	if len(d.DeadLetters()) != 1 {
		t.Fatal("unknown replay changed the dead-letter list")
	}
}
