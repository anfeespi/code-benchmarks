package idempotency

import (
	"context"
	"errors"
	"testing"
	"time"

	"example.com/gopayments/clock"
)

func newStore() (*Memory, *clock.Fake) {
	clk := clock.NewFake(time.Date(2026, 5, 1, 0, 0, 0, 0, time.UTC))
	return NewMemory(clk, 24*time.Hour), clk
}

func TestBeginCompleteReplay(t *testing.T) {
	ctx := context.Background()
	s, _ := newStore()
	_, started, err := s.Begin(ctx, "k1", "fp")
	if err != nil || !started {
		t.Fatalf("first Begin: started=%v err=%v", started, err)
	}
	if err := s.Complete(ctx, "k1", Response{Status: 201, Body: []byte(`{"id":"x"}`)}); err != nil {
		t.Fatal(err)
	}
	rec, started, err := s.Begin(ctx, "k1", "fp")
	if err != nil || started {
		t.Fatalf("replay Begin: started=%v err=%v", started, err)
	}
	if rec.Response.Status != 201 || string(rec.Response.Body) != `{"id":"x"}` {
		t.Fatalf("replayed %+v", rec.Response)
	}
}

func TestBeginErrors(t *testing.T) {
	ctx := context.Background()
	tests := []struct {
		name    string
		prep    func(s *Memory)
		fp      string
		wantErr error
	}{
		{"in progress", func(s *Memory) { _, _, _ = s.Begin(ctx, "k", "fp") }, "fp", ErrInProgress},
		{"different request", func(s *Memory) {
			_, _, _ = s.Begin(ctx, "k", "fp")
			_ = s.Complete(ctx, "k", Response{Status: 200})
		}, "other", ErrKeyReuse},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			s, _ := newStore()
			tt.prep(s)
			if _, _, err := s.Begin(ctx, "k", tt.fp); !errors.Is(err, tt.wantErr) {
				t.Fatalf("err = %v, want %v", err, tt.wantErr)
			}
		})
	}
	s, _ := newStore()
	if _, _, err := s.Begin(ctx, "", "fp"); !errors.Is(err, ErrEmptyKey) {
		t.Fatalf("empty key: %v", err)
	}
}

func TestReleaseAllowsRetry(t *testing.T) {
	ctx := context.Background()
	s, _ := newStore()
	_, _, _ = s.Begin(ctx, "k", "fp")
	if err := s.Release(ctx, "k"); err != nil {
		t.Fatal(err)
	}
	if _, started, err := s.Begin(ctx, "k", "fp"); err != nil || !started {
		t.Fatalf("after release: started=%v err=%v", started, err)
	}
	if err := s.Release(ctx, "zzz"); !errors.Is(err, ErrUnknownKey) {
		t.Fatalf("unknown release: %v", err)
	}
}

func TestReplayBodyIsCopied(t *testing.T) {
	ctx := context.Background()
	s, _ := newStore()
	_, _, _ = s.Begin(ctx, "k", "fp")
	body := []byte("abc")
	_ = s.Complete(ctx, "k", Response{Status: 200, Body: body})
	body[0] = 'X'
	rec, _, _ := s.Begin(ctx, "k", "fp")
	if string(rec.Response.Body) != "abc" {
		t.Fatalf("stored body aliased caller slice: %q", rec.Response.Body)
	}
}
