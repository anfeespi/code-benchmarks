// Package webhook delivers payment events to merchant endpoints with signed
// payloads, retries with exponential backoff and a dead-letter list.
package webhook

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"sync"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/payment"
)

// Event is the webhook payload.
type Event struct {
	ID         string          `json:"id"`
	Type       string          `json:"type"`
	MerchantID string          `json:"merchant_id"`
	CreatedAt  time.Time       `json:"created_at"`
	Data       json.RawMessage `json:"data"`
}

// Endpoint is a merchant's webhook destination.
type Endpoint struct {
	URL    string
	Secret string
}

// Endpoints resolves the endpoint of a merchant.
type Endpoints interface {
	Endpoint(merchantID string) (Endpoint, bool)
}

// StaticEndpoints is a fixed merchant -> endpoint map.
type StaticEndpoints map[string]Endpoint

// Endpoint implements Endpoints.
func (s StaticEndpoints) Endpoint(merchantID string) (Endpoint, bool) {
	e, ok := s[merchantID]
	return e, ok
}

// Policy controls retries.
type Policy struct {
	MaxAttempts int
	BaseDelay   time.Duration
	MaxDelay    time.Duration
}

// DefaultPolicy is the production retry policy.
func DefaultPolicy() Policy {
	return Policy{MaxAttempts: 6, BaseDelay: time.Second, MaxDelay: 10 * time.Minute}
}

// Backoff is the wait after failed attempt n (n >= 1): BaseDelay * 2^(n-1),
// capped at MaxDelay.
func (p Policy) Backoff(n int) time.Duration {
	d := p.BaseDelay
	for i := 1; i < n; i++ {
		if d >= p.MaxDelay/2 {
			return p.MaxDelay
		}
		d *= 2
	}
	return min(d, p.MaxDelay)
}

// DeadLetter is an event that exhausted its retries or failed permanently.
type DeadLetter struct {
	Event      Event
	Attempts   int
	LastStatus int
	LastError  string
	FailedAt   time.Time
}

// Dispatcher queues events and delivers them.
type Dispatcher struct {
	sender    Sender
	endpoints Endpoints
	clock     clock.Clock
	policy    Policy

	mu        sync.Mutex
	seq       int
	queue     []Event
	dead      []DeadLetter
	delivered int
}

var _ payment.Publisher = (*Dispatcher)(nil)

// NewDispatcher wires a dispatcher.
func NewDispatcher(sender Sender, endpoints Endpoints, clk clock.Clock, policy Policy) *Dispatcher {
	return &Dispatcher{sender: sender, endpoints: endpoints, clock: clk, policy: policy}
}

type paymentData struct {
	PaymentID string `json:"payment_id"`
	Status    string `json:"status"`
	Amount    string `json:"amount"`
	Currency  string `json:"currency"`
	Refunded  string `json:"refunded_amount"`
	RefundID  string `json:"refund_id,omitempty"`
}

// Publish implements payment.Publisher by queueing a webhook event.
func (d *Dispatcher) Publish(_ context.Context, ev payment.Event) error {
	data := paymentData{
		PaymentID: ev.Payment.ID,
		Status:    string(ev.Payment.Status),
		Amount:    ev.Payment.Amount.Decimal(),
		Currency:  ev.Payment.Amount.Currency.Code,
		Refunded:  ev.Payment.RefundedAmount().Decimal(),
	}
	if ev.Refund != nil {
		data.RefundID = ev.Refund.ID
	}
	raw, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("encode %s event: %w", ev.Type, err)
	}
	d.mu.Lock()
	defer d.mu.Unlock()
	d.seq++
	d.queue = append(d.queue, Event{
		ID:         fmt.Sprintf("evt_%06d", d.seq),
		Type:       ev.Type,
		MerchantID: ev.Payment.MerchantID,
		CreatedAt:  d.clock.Now(),
		Data:       raw,
	})
	return nil
}

// Pending returns the number of queued, undelivered events.
func (d *Dispatcher) Pending() int {
	d.mu.Lock()
	defer d.mu.Unlock()
	return len(d.queue)
}

// Delivered returns how many events were delivered successfully.
func (d *Dispatcher) Delivered() int {
	d.mu.Lock()
	defer d.mu.Unlock()
	return d.delivered
}

// DeadLetters returns a snapshot of the dead-letter list.
func (d *Dispatcher) DeadLetters() []DeadLetter {
	d.mu.Lock()
	defer d.mu.Unlock()
	return append([]DeadLetter(nil), d.dead...)
}

// Flush delivers every queued event. It returns early only if ctx is done;
// undelivered events stay queued in that case.
func (d *Dispatcher) Flush(ctx context.Context) error {
	d.mu.Lock()
	batch := d.queue
	d.queue = nil
	d.mu.Unlock()

	for i, ev := range batch {
		if err := d.deliver(ctx, ev); err != nil {
			d.mu.Lock()
			d.queue = append(append([]Event(nil), batch[i:]...), d.queue...)
			d.mu.Unlock()
			return fmt.Errorf("flush webhooks: %w", err)
		}
	}
	return nil
}

// deliver attempts ev until success, a permanent failure or MaxAttempts.
// It only returns an error when ctx is done.
func (d *Dispatcher) deliver(ctx context.Context, ev Event) error {
	ep, ok := d.endpoints.Endpoint(ev.MerchantID)
	if !ok {
		return nil // merchant has no webhook configured
	}
	body, err := json.Marshal(ev)
	if err != nil {
		d.deadLetter(ev, 0, 0, fmt.Errorf("encode event: %w", err))
		return nil
	}
	var (
		status  int
		sendErr error
		attempt int
	)
	for attempt = 1; attempt <= d.policy.MaxAttempts; attempt++ {
		headers := map[string]string{
			"Content-Type":  "application/json",
			"Webhook-Id":    ev.ID,
			SignatureHeader: Sign(ep.Secret, d.clock.Now().Unix(), body),
		}
		status, sendErr = d.sender.Send(ctx, Delivery{EventID: ev.ID, URL: ep.URL, Body: body, Headers: headers, Attempt: attempt})
		if sendErr == nil && status >= 200 && status < 300 {
			d.mu.Lock()
			d.delivered++
			d.mu.Unlock()
			return nil
		}
		if !retryable(status, sendErr) || attempt == d.policy.MaxAttempts {
			break
		}
		if err := d.clock.Sleep(ctx, d.policy.Backoff(attempt)); err != nil {
			return err
		}
	}
	d.deadLetter(ev, attempt, status, sendErr)
	return nil
}

func (d *Dispatcher) deadLetter(ev Event, attempts, status int, err error) {
	dl := DeadLetter{Event: ev, Attempts: attempts, LastStatus: status, FailedAt: d.clock.Now()}
	if err != nil {
		dl.LastError = err.Error()
	}
	d.mu.Lock()
	defer d.mu.Unlock()
	d.dead = append(d.dead, dl)
}

// retryable reports whether a failed attempt should be retried: transport
// errors, 408, 429 and 5xx are transient; any other status is permanent.
func retryable(status int, err error) bool {
	if err != nil {
		return true
	}
	return status == http.StatusRequestTimeout || status == http.StatusTooManyRequests || status >= 500
}
