package clock

import (
	"context"
	"testing"
	"time"
)

func TestFakeSleepAdvances(t *testing.T) {
	start := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	f := NewFake(start)
	if err := f.Sleep(context.Background(), 3*time.Second); err != nil {
		t.Fatal(err)
	}
	f.Advance(time.Minute)
	if got, want := f.Now(), start.Add(time.Minute+3*time.Second); !got.Equal(want) {
		t.Fatalf("Now = %v, want %v", got, want)
	}
	if s := f.Sleeps(); len(s) != 1 || s[0] != 3*time.Second {
		t.Fatalf("Sleeps = %v", s)
	}
}

func TestFakeSleepCanceled(t *testing.T) {
	f := NewFake(time.Unix(0, 0))
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := f.Sleep(ctx, time.Second); err == nil {
		t.Fatal("expected error on canceled context")
	}
}
