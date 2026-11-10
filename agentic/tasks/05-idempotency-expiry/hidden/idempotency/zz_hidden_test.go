package idempotency_test

import (
	"context"
	"errors"
	"fmt"
	"testing"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/idempotency"
)

const h05TTL = 24 * time.Hour

func h05Store() (*idempotency.Memory, *clock.Fake) {
	clk := clock.NewFake(time.Date(2026, 5, 1, 0, 0, 0, 0, time.UTC))
	return idempotency.NewMemory(clk, h05TTL), clk
}

func h05Completed(t *testing.T, s *idempotency.Memory, key string) {
	t.Helper()
	if _, started, err := s.Begin(context.Background(), key, "fp-1"); err != nil || !started {
		t.Fatalf("Begin: %v %v", started, err)
	}
	if err := s.Complete(context.Background(), key, idempotency.Response{Status: 201, Body: []byte("old")}); err != nil {
		t.Fatal(err)
	}
}

func TestHiddenExpiryBoundary(t *testing.T) {
	tests := []struct {
		after       time.Duration
		fingerprint string
		wantStarted bool
		wantErr     error
	}{
		{h05TTL - time.Second, "fp-1", false, nil},
		{h05TTL - time.Second, "fp-2", false, idempotency.ErrKeyReuse},
		{h05TTL, "fp-1", true, nil},
		{h05TTL, "fp-2", true, nil},
		{40 * time.Hour, "fp-2", true, nil},
		{40 * time.Hour, "fp-1", true, nil},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%s/%s", tt.after, tt.fingerprint), func(t *testing.T) {
			s, clk := h05Store()
			h05Completed(t, s, "k")
			clk.Advance(tt.after)
			rec, started, err := s.Begin(context.Background(), "k", tt.fingerprint)
			if !errors.Is(err, tt.wantErr) || started != tt.wantStarted {
				t.Fatalf("started=%v err=%v, want started=%v err=%v", started, err, tt.wantStarted, tt.wantErr)
			}
			if started && (rec.Completed || len(rec.Response.Body) != 0) {
				t.Fatalf("expired key returned stale record %+v", rec)
			}
			if !started && tt.wantErr == nil && string(rec.Response.Body) != "old" {
				t.Fatalf("replay body = %q", rec.Response.Body)
			}
		})
	}
}

func TestHiddenExpiredInProgressKeyCanRestart(t *testing.T) {
	s, clk := h05Store()
	if _, started, err := s.Begin(context.Background(), "k", "fp"); err != nil || !started {
		t.Fatal(started, err)
	}
	clk.Advance(h05TTL + time.Minute)
	if _, started, err := s.Begin(context.Background(), "k", "fp"); err != nil || !started {
		t.Fatalf("expired in-progress key: started=%v err=%v", started, err)
	}
}

func TestHiddenNewRecordAfterExpiryHasFreshTTL(t *testing.T) {
	s, clk := h05Store()
	h05Completed(t, s, "k")
	clk.Advance(30 * time.Hour)
	if _, started, _ := s.Begin(context.Background(), "k", "fp-2"); !started {
		t.Fatal("expected restart")
	}
	_ = s.Complete(context.Background(), "k", idempotency.Response{Status: 200, Body: []byte("new")})
	clk.Advance(23 * time.Hour)
	rec, started, err := s.Begin(context.Background(), "k", "fp-2")
	if err != nil || started || string(rec.Response.Body) != "new" {
		t.Fatalf("started=%v err=%v body=%q", started, err, rec.Response.Body)
	}
}

func TestHiddenExpiredRecordsAreEvicted(t *testing.T) {
	s, clk := h05Store()
	for i := 0; i < 50; i++ {
		h05Completed(t, s, fmt.Sprintf("k%d", i))
	}
	clk.Advance(h05TTL + 2*time.Minute)
	if _, _, err := s.Begin(context.Background(), "fresh", "fp"); err != nil {
		t.Fatal(err)
	}
	clk.Advance(2 * time.Minute)
	if _, _, err := s.Begin(context.Background(), "fresh2", "fp"); err != nil {
		t.Fatal(err)
	}
	if n := s.Len(); n != 2 {
		t.Fatalf("Len = %d after expiry, want 2", n)
	}
}
