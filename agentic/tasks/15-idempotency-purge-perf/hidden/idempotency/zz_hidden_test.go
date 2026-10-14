package idempotency_test

import (
	"context"
	"fmt"
	"testing"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/idempotency"
)

func TestHiddenBeginScalesWithManyKeys(t *testing.T) {
	clk := clock.NewFake(time.Date(2026, 5, 1, 0, 0, 0, 0, time.UTC))
	s := idempotency.NewMemory(clk, 24*time.Hour)
	ctx := context.Background()
	const n = 40000
	done := make(chan time.Duration, 1)
	go func() {
		start := time.Now()
		for i := 0; i < n; i++ {
			key := fmt.Sprintf("key-%d", i)
			if _, ok, err := s.Begin(ctx, key, "fp"); err != nil || !ok {
				panic(fmt.Sprintf("Begin %s: %v %v", key, ok, err))
			}
			_ = s.Complete(ctx, key, idempotency.Response{Status: 201})
			if i%1000 == 0 {
				clk.Advance(time.Second)
			}
		}
		done <- time.Since(start)
	}()
	select {
	case d := <-done:
		t.Logf("%d Begin+Complete in %s", n, d)
	case <-time.After(20 * time.Second):
		t.Fatalf("%d Begin+Complete did not finish in 20s; Begin cost grows with the number of stored keys", n)
	}
}

func TestHiddenExpiredNeverReplayedAndEvicted(t *testing.T) {
	clk := clock.NewFake(time.Date(2026, 5, 1, 0, 0, 0, 0, time.UTC))
	s := idempotency.NewMemory(clk, 24*time.Hour)
	ctx := context.Background()
	for i := 0; i < 500; i++ {
		key := fmt.Sprintf("old-%d", i)
		_, _, _ = s.Begin(ctx, key, "fp")
		_ = s.Complete(ctx, key, idempotency.Response{Status: 201, Body: []byte("old")})
	}
	clk.Advance(24 * time.Hour)
	// Exactly at expiry, without waiting for any eviction pass, the key must start fresh.
	rec, started, err := s.Begin(ctx, "old-7", "other-fp")
	if err != nil || !started || rec.Completed {
		t.Fatalf("expired key replayed: started=%v err=%v rec=%+v", started, err, rec)
	}
	clk.Advance(2 * time.Minute)
	_, _, _ = s.Begin(ctx, "fresh-1", "fp")
	clk.Advance(2 * time.Minute)
	_, _, _ = s.Begin(ctx, "fresh-2", "fp")
	if n := s.Len(); n != 3 {
		t.Fatalf("Len = %d, want 3 (old-7 restarted, fresh-1, fresh-2)", n)
	}
	// Unexpired keys keep replaying.
	r, started, err := s.Begin(ctx, "fresh-1", "fp")
	if err == nil || started {
		t.Fatalf("fresh-1 is in progress, got started=%v err=%v rec=%+v", started, err, r)
	}
}
