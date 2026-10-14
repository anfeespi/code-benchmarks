// Package idempotency stores the outcome of requests sent with an
// Idempotency-Key so retries replay the first response instead of executing
// the operation twice.
package idempotency

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"

	"example.com/gopayments/clock"
)

var (
	// ErrInProgress means another request with the same key has not finished yet.
	ErrInProgress = errors.New("request with this idempotency key is still in progress")
	// ErrKeyReuse means the key was already used for a different request.
	ErrKeyReuse = errors.New("idempotency key reused with a different request")
	// ErrUnknownKey is returned when completing or releasing a key that was never begun.
	ErrUnknownKey = errors.New("unknown idempotency key")
	// ErrEmptyKey is returned for an empty key.
	ErrEmptyKey = errors.New("empty idempotency key")
)

// Response is the stored outcome replayed to retries.
type Response struct {
	Status int
	Body   []byte
}

// Record is the state of one key.
type Record struct {
	Key         string
	Fingerprint string
	Completed   bool
	Response    Response
	ExpiresAt   time.Time
}

// Store is the idempotency contract.
type Store interface {
	// Begin reserves key for a request identified by fingerprint. started is
	// true when the caller must execute the request and then call Complete or
	// Release. When started is false and err is nil, rec holds the stored
	// response to replay.
	Begin(ctx context.Context, key, fingerprint string) (rec Record, started bool, err error)
	Complete(ctx context.Context, key string, resp Response) error
	// Release forgets a key whose request failed so it can be retried.
	Release(ctx context.Context, key string) error
}

// DefaultPurgeInterval is how often expired records are evicted.
const DefaultPurgeInterval = time.Minute

// Memory is an in-memory Store. Records expire TTL after Begin; a key is
// considered expired once now >= ExpiresAt.
type Memory struct {
	clock clock.Clock
	ttl   time.Duration

	mu        sync.Mutex
	records   map[string]*Record
	nextPurge time.Time
}

var _ Store = (*Memory)(nil)

// NewMemory returns a store whose records live for ttl.
func NewMemory(clk clock.Clock, ttl time.Duration) *Memory {
	return &Memory{clock: clk, ttl: ttl, records: make(map[string]*Record)}
}

// Begin implements Store.
func (m *Memory) Begin(_ context.Context, key, fingerprint string) (Record, bool, error) {
	if key == "" {
		return Record{}, false, ErrEmptyKey
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	now := m.clock.Now()
	m.purgeLocked(now)

	if r, ok := m.records[key]; ok && now.Before(r.ExpiresAt) {
		if r.Fingerprint != fingerprint {
			return Record{}, false, fmt.Errorf("%w: key %q", ErrKeyReuse, key)
		}
		if !r.Completed {
			return Record{}, false, fmt.Errorf("%w: key %q", ErrInProgress, key)
		}
		return copyRecord(r), false, nil
	}
	r := &Record{Key: key, Fingerprint: fingerprint, ExpiresAt: now.Add(m.ttl)}
	m.records[key] = r
	return copyRecord(r), true, nil
}

// Complete implements Store.
func (m *Memory) Complete(_ context.Context, key string, resp Response) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	r, ok := m.records[key]
	if !ok {
		return fmt.Errorf("%w: %q", ErrUnknownKey, key)
	}
	r.Completed = true
	r.Response = Response{Status: resp.Status, Body: append([]byte(nil), resp.Body...)}
	return nil
}

// Release implements Store.
func (m *Memory) Release(_ context.Context, key string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.records[key]; !ok {
		return fmt.Errorf("%w: %q", ErrUnknownKey, key)
	}
	delete(m.records, key)
	return nil
}

// Len returns the number of records currently held (expired ones included
// until the next purge).
func (m *Memory) Len() int {
	m.mu.Lock()
	defer m.mu.Unlock()
	return len(m.records)
}

// purgeLocked evicts expired records at most once per DefaultPurgeInterval.
func (m *Memory) purgeLocked(now time.Time) {
	if now.Before(m.nextPurge) {
		return
	}
	for k, r := range m.records {
		if !now.Before(r.ExpiresAt) {
			delete(m.records, k)
		}
	}
	m.nextPurge = now.Add(DefaultPurgeInterval)
}

func copyRecord(r *Record) Record {
	c := *r
	c.Response.Body = append([]byte(nil), r.Response.Body...)
	return c
}
