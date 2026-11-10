// Package clock abstracts time so expiry and backoff logic can be tested
// without real sleeps.
package clock

import (
	"context"
	"sync"
	"time"
)

// Clock is the time source used across the service.
type Clock interface {
	Now() time.Time
	// Sleep blocks for d or until ctx is done, whichever happens first.
	Sleep(ctx context.Context, d time.Duration) error
}

// Real is the wall clock.
type Real struct{}

// Now returns the current wall-clock time.
func (Real) Now() time.Time { return time.Now() }

// Sleep waits for d or until ctx is done.
func (Real) Sleep(ctx context.Context, d time.Duration) error {
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}

// Fake is a manually driven clock. Sleep advances the clock instantly and
// records the requested duration so tests can assert on backoff schedules.
type Fake struct {
	mu     sync.Mutex
	now    time.Time
	sleeps []time.Duration
}

// NewFake returns a fake clock set to start.
func NewFake(start time.Time) *Fake { return &Fake{now: start} }

// Now returns the fake current time.
func (f *Fake) Now() time.Time {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.now
}

// Advance moves the clock forward by d.
func (f *Fake) Advance(d time.Duration) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.now = f.now.Add(d)
}

// Sleep advances the clock by d without blocking.
func (f *Fake) Sleep(ctx context.Context, d time.Duration) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	f.now = f.now.Add(d)
	f.sleeps = append(f.sleeps, d)
	return nil
}

// Sleeps returns every duration passed to Sleep, in order.
func (f *Fake) Sleeps() []time.Duration {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]time.Duration(nil), f.sleeps...)
}
