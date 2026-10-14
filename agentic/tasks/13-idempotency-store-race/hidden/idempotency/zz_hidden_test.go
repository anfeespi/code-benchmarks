package idempotency_test

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/idempotency"
)

func TestHiddenConcurrentDistinctKeys(t *testing.T) {
	clk := clock.NewFake(time.Date(2026, 5, 1, 0, 0, 0, 0, time.UTC))
	s := idempotency.NewMemory(clk, 24*time.Hour)
	ctx := context.Background()
	var wg sync.WaitGroup
	for g := 0; g < 16; g++ {
		wg.Add(1)
		go func(g int) {
			defer wg.Done()
			for i := 0; i < 200; i++ {
				key := fmt.Sprintf("g%d-%d", g, i)
				if _, started, err := s.Begin(ctx, key, "fp"); err != nil || !started {
					t.Errorf("Begin %s: %v %v", key, started, err)
					return
				}
				if i%3 == 0 {
					_ = s.Release(ctx, key)
					continue
				}
				if err := s.Complete(ctx, key, idempotency.Response{Status: 201, Body: []byte(key)}); err != nil {
					t.Errorf("Complete %s: %v", key, err)
					return
				}
				rec, started, err := s.Begin(ctx, key, "fp")
				if err != nil || started || string(rec.Response.Body) != key {
					t.Errorf("replay %s: %v %v %q", key, started, err, rec.Response.Body)
					return
				}
				if i%50 == 0 {
					clk.Advance(time.Minute)
				}
			}
		}(g)
	}
	wg.Wait()
}

func TestHiddenSingleWinnerPerKey(t *testing.T) {
	for round := 0; round < 30; round++ {
		s := idempotency.NewMemory(clock.NewFake(time.Date(2026, 5, 1, 0, 0, 0, 0, time.UTC)), time.Hour)
		var started, inProgress, other atomic.Int32
		var wg sync.WaitGroup
		gate := make(chan struct{})
		for i := 0; i < 64; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				<-gate
				_, ok, err := s.Begin(context.Background(), "refund-key", "fp")
				switch {
				case err == nil && ok:
					started.Add(1)
				case errors.Is(err, idempotency.ErrInProgress):
					inProgress.Add(1)
				default:
					other.Add(1)
				}
			}()
		}
		close(gate)
		wg.Wait()
		if started.Load() != 1 || inProgress.Load() != 63 || other.Load() != 0 {
			t.Fatalf("round %d: started=%d inProgress=%d other=%d", round, started.Load(), inProgress.Load(), other.Load())
		}
	}
}

func TestHiddenConcurrentCompleteAndReplay(t *testing.T) {
	s := idempotency.NewMemory(clock.NewFake(time.Date(2026, 5, 1, 0, 0, 0, 0, time.UTC)), time.Hour)
	ctx := context.Background()
	if _, ok, err := s.Begin(ctx, "k", "fp"); err != nil || !ok {
		t.Fatal(ok, err)
	}
	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer wg.Done()
		_ = s.Complete(ctx, "k", idempotency.Response{Status: 200, Body: []byte("done")})
	}()
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				rec, ok, err := s.Begin(ctx, "k", "fp")
				if ok || (err == nil && string(rec.Response.Body) != "done") || (err != nil && !errors.Is(err, idempotency.ErrInProgress)) {
					t.Errorf("Begin during Complete: ok=%v err=%v body=%q", ok, err, rec.Response.Body)
					return
				}
			}
		}()
	}
	wg.Wait()
}
