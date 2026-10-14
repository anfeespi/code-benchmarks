package payment_test

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/money"
	"example.com/gopayments/payment"
	"example.com/gopayments/store"
)

type h08Events struct {
	mu    sync.Mutex
	types []string
	last  payment.Event
}

func (e *h08Events) Publish(_ context.Context, ev payment.Event) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.types = append(e.types, ev.Type)
	e.last = ev
	return nil
}

func h08Service() (*payment.Service, *h08Events) {
	ev := &h08Events{}
	return payment.NewService(store.NewMemory(), clock.NewFake(time.Unix(1_800_000_000, 0)), payment.NewSeqIDs(), ev, payment.Config{FeeBps: 290}), ev
}

func h08InStatus(t *testing.T, s *payment.Service, st payment.Status) string {
	t.Helper()
	ctx := context.Background()
	p, err := s.Create(ctx, payment.CreateInput{MerchantID: "m", Amount: money.MustNew(500, "USD")})
	if err != nil {
		t.Fatal(err)
	}
	steps := map[payment.Status][]func() error{
		payment.StatusCreated:   nil,
		payment.StatusPending:   {func() error { _, err := s.Authorize(ctx, p.ID); return err }},
		payment.StatusDeclined:  {func() error { _, err := s.Decline(ctx, p.ID, "x"); return err }},
		payment.StatusSucceeded: {func() error { _, err := s.Authorize(ctx, p.ID); return err }, func() error { _, err := s.Capture(ctx, p.ID); return err }},
		payment.StatusRefunded: {func() error { _, err := s.Authorize(ctx, p.ID); return err }, func() error { _, err := s.Capture(ctx, p.ID); return err },
			func() error { _, _, err := s.Refund(ctx, p.ID, money.MustNew(500, "USD")); return err }},
		payment.StatusCanceled: {func() error { _, err := s.Cancel(ctx, p.ID); return err }},
	}
	for _, f := range steps[st] {
		if err := f(); err != nil {
			t.Fatal(err)
		}
	}
	return p.ID
}

func TestHiddenCancelAllowed(t *testing.T) {
	for _, from := range []payment.Status{payment.StatusCreated, payment.StatusPending} {
		t.Run(string(from), func(t *testing.T) {
			s, ev := h08Service()
			id := h08InStatus(t, s, from)
			p, err := s.Cancel(context.Background(), id)
			if err != nil {
				t.Fatal(err)
			}
			if p.Status != payment.StatusCanceled || string(payment.StatusCanceled) != "CANCELED" {
				t.Fatalf("status = %s", p.Status)
			}
			got, _ := s.Get(context.Background(), id)
			if got.Status != payment.StatusCanceled {
				t.Fatalf("stored status = %s", got.Status)
			}
			if ev.types[len(ev.types)-1] != "payment.canceled" || ev.last.Payment.Status != payment.StatusCanceled {
				t.Fatalf("events = %v", ev.types)
			}
		})
	}
}

func TestHiddenCancelRejected(t *testing.T) {
	for _, from := range []payment.Status{payment.StatusSucceeded, payment.StatusDeclined, payment.StatusRefunded, payment.StatusCanceled} {
		t.Run(string(from), func(t *testing.T) {
			s, _ := h08Service()
			id := h08InStatus(t, s, from)
			if _, err := s.Cancel(context.Background(), id); !errors.Is(err, payment.ErrInvalidTransition) {
				t.Fatalf("err = %v", err)
			}
		})
	}
	s, _ := h08Service()
	if _, err := s.Cancel(context.Background(), "pay_nope"); !errors.Is(err, payment.ErrNotFound) {
		t.Fatalf("unknown: %v", err)
	}
}

func TestHiddenCanceledIsTerminal(t *testing.T) {
	ctx := context.Background()
	s, _ := h08Service()
	id := h08InStatus(t, s, payment.StatusCanceled)
	ops := map[string]func() error{
		"authorize": func() error { _, err := s.Authorize(ctx, id); return err },
		"capture":   func() error { _, err := s.Capture(ctx, id); return err },
		"decline":   func() error { _, err := s.Decline(ctx, id, "x"); return err },
		"refund":    func() error { _, _, err := s.Refund(ctx, id, money.MustNew(1, "USD")); return err },
	}
	for name, op := range ops {
		if err := op(); !errors.Is(err, payment.ErrInvalidTransition) {
			t.Errorf("%s after cancel: %v", name, err)
		}
	}
	if !payment.StatusCanceled.Final() {
		t.Error("CANCELED must be final")
	}
	for _, in := range []string{"canceled", "CANCELED", " Canceled "} {
		if st, err := payment.ParseStatus(in); err != nil || st != payment.StatusCanceled {
			t.Errorf("ParseStatus(%q) = %s, %v", in, st, err)
		}
	}
}
