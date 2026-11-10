// Package store provides repository implementations for the payment domain.
package store

import (
	"context"
	"encoding/base64"
	"fmt"
	"strconv"
	"strings"
	"sync"

	"example.com/gopayments/payment"
)

const (
	defaultLimit = 20
	maxLimit     = 100
)

// Memory is an in-memory payment.Repository used in tests and local runs.
type Memory struct {
	mu         sync.RWMutex
	byID       map[string]payment.Payment
	byMerchant map[string][]string // payment ids in creation order
}

var _ payment.Repository = (*Memory)(nil)

// NewMemory returns an empty repository.
func NewMemory() *Memory {
	return &Memory{
		byID:       make(map[string]payment.Payment),
		byMerchant: make(map[string][]string),
	}
}

// Create stores a new payment.
func (m *Memory) Create(_ context.Context, p payment.Payment) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok := m.byID[p.ID]; ok {
		return fmt.Errorf("%w: %s", payment.ErrDuplicate, p.ID)
	}
	m.byID[p.ID] = p.Clone()
	m.byMerchant[p.MerchantID] = append(m.byMerchant[p.MerchantID], p.ID)
	return nil
}

// Get returns a copy of the stored payment.
func (m *Memory) Get(_ context.Context, id string) (payment.Payment, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	p, ok := m.byID[id]
	if !ok {
		return payment.Payment{}, fmt.Errorf("%w: %s", payment.ErrNotFound, id)
	}
	return p.Clone(), nil
}

// Update replaces the stored payment if versions match.
func (m *Memory) Update(_ context.Context, p payment.Payment) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	cur, ok := m.byID[p.ID]
	if !ok {
		return fmt.Errorf("%w: %s", payment.ErrNotFound, p.ID)
	}
	if cur.Version != p.Version {
		return fmt.Errorf("%w: payment %s has version %d, update based on %d", payment.ErrVersionConflict, p.ID, cur.Version, p.Version)
	}
	next := p.Clone()
	next.Version++
	m.byID[p.ID] = next
	return nil
}

// ListByMerchant pages through a merchant's payments in creation order.
func (m *Memory) ListByMerchant(_ context.Context, merchantID string, page payment.Page) ([]payment.Payment, string, error) {
	limit := page.Limit
	switch {
	case limit < 0:
		return nil, "", fmt.Errorf("%w: limit must not be negative", payment.ErrInvalidInput)
	case limit == 0:
		limit = defaultLimit
	case limit > maxLimit:
		limit = maxLimit
	}
	offset := 0
	if page.Cursor != "" {
		var err error
		if offset, err = decodeCursor(page.Cursor); err != nil {
			return nil, "", err
		}
	}

	m.mu.RLock()
	defer m.mu.RUnlock()
	ids := m.byMerchant[merchantID]
	if offset > len(ids) {
		offset = len(ids)
	}
	end := min(offset+limit, len(ids))
	out := make([]payment.Payment, 0, end-offset)
	for _, id := range ids[offset:end] {
		out = append(out, m.byID[id].Clone())
	}
	next := ""
	if end < len(ids) {
		next = encodeCursor(end)
	}
	return out, next, nil
}

func encodeCursor(offset int) string {
	return base64.RawURLEncoding.EncodeToString([]byte("o:" + strconv.Itoa(offset)))
}

func decodeCursor(c string) (int, error) {
	raw, err := base64.RawURLEncoding.DecodeString(c)
	if err != nil {
		return 0, fmt.Errorf("%w: %v", payment.ErrInvalidCursor, err)
	}
	n, ok := strings.CutPrefix(string(raw), "o:")
	if !ok {
		return 0, fmt.Errorf("%w: unexpected format", payment.ErrInvalidCursor)
	}
	off, err := strconv.Atoi(n)
	if err != nil || off < 0 {
		return 0, fmt.Errorf("%w: bad offset %q", payment.ErrInvalidCursor, n)
	}
	return off, nil
}
