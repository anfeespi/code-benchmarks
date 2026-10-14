package webhook

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/money"
	"example.com/gopayments/payment"
)

// scriptedSender returns the scripted outcomes in order, then 200.
type scriptedSender struct {
	mu       sync.Mutex
	statuses []int
	errs     []error
	calls    []Delivery
}

func (s *scriptedSender) Send(_ context.Context, d Delivery) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	i := len(s.calls)
	s.calls = append(s.calls, d)
	if i < len(s.statuses) {
		var err error
		if i < len(s.errs) {
			err = s.errs[i]
		}
		return s.statuses[i], err
	}
	return http.StatusOK, nil
}

func newDispatcher(sender Sender) (*Dispatcher, *clock.Fake) {
	clk := clock.NewFake(time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC))
	eps := StaticEndpoints{"m_1": {URL: "https://merchant.example/hooks", Secret: "s3cret"}}
	return NewDispatcher(sender, eps, clk, Policy{MaxAttempts: 4, BaseDelay: time.Second, MaxDelay: time.Minute}), clk
}

func publishOne(t *testing.T, d *Dispatcher, merchant string) {
	t.Helper()
	p := payment.Payment{ID: "pay_1", MerchantID: merchant, Amount: money.MustNew(1000, "USD"), Status: payment.StatusSucceeded}
	if err := d.Publish(context.Background(), payment.Event{Type: "payment.succeeded", Payment: p}); err != nil {
		t.Fatal(err)
	}
}

func TestSignVerify(t *testing.T) {
	now := time.Unix(1_800_000_000, 0)
	body := []byte(`{"id":"evt_1"}`)
	h := Sign("k", now.Unix(), body)
	tests := []struct {
		name    string
		secret  string
		body    []byte
		now     time.Time
		wantErr error
	}{
		{"valid", "k", body, now, nil},
		{"wrong secret", "other", body, now, ErrBadSignature},
		{"tampered body", "k", []byte(`{"id":"evt_2"}`), now, ErrBadSignature},
		{"stale", "k", body, now.Add(10 * time.Minute), ErrStaleSignature},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := Verify(tt.secret, h, tt.body, tt.now, 5*time.Minute)
			if !errors.Is(err, tt.wantErr) {
				t.Fatalf("Verify = %v, want %v", err, tt.wantErr)
			}
		})
	}
}

func TestBackoffSchedule(t *testing.T) {
	p := Policy{MaxAttempts: 10, BaseDelay: time.Second, MaxDelay: 10 * time.Second}
	want := []time.Duration{time.Second, 2 * time.Second, 4 * time.Second, 8 * time.Second, 10 * time.Second, 10 * time.Second}
	for i, w := range want {
		if got := p.Backoff(i + 1); got != w {
			t.Errorf("Backoff(%d) = %s, want %s", i+1, got, w)
		}
	}
}

func TestDeliverSuccessFirstTry(t *testing.T) {
	s := &scriptedSender{}
	d, _ := newDispatcher(s)
	publishOne(t, d, "m_1")
	if err := d.Flush(context.Background()); err != nil {
		t.Fatal(err)
	}
	if len(s.calls) != 1 || d.Delivered() != 1 || d.Pending() != 0 {
		t.Fatalf("calls %d delivered %d pending %d", len(s.calls), d.Delivered(), d.Pending())
	}
	c := s.calls[0]
	if err := Verify("s3cret", c.Headers[SignatureHeader], c.Body, time.Date(2026, 6, 1, 0, 0, 0, 0, time.UTC), time.Minute); err != nil {
		t.Fatalf("signature: %v", err)
	}
}

func TestDeliverRetriesNetworkErrors(t *testing.T) {
	boom := errors.New("connection reset")
	s := &scriptedSender{statuses: []int{0, 0}, errs: []error{boom, boom}}
	d, clk := newDispatcher(s)
	publishOne(t, d, "m_1")
	if err := d.Flush(context.Background()); err != nil {
		t.Fatal(err)
	}
	if len(s.calls) != 3 || d.Delivered() != 1 {
		t.Fatalf("calls %d delivered %d", len(s.calls), d.Delivered())
	}
	if got := clk.Sleeps(); len(got) != 2 || got[0] != time.Second || got[1] != 2*time.Second {
		t.Fatalf("sleeps = %v", got)
	}
}

func TestNoEndpointIsDropped(t *testing.T) {
	s := &scriptedSender{}
	d, _ := newDispatcher(s)
	publishOne(t, d, "m_unknown")
	if err := d.Flush(context.Background()); err != nil {
		t.Fatal(err)
	}
	if len(s.calls) != 0 || len(d.DeadLetters()) != 0 {
		t.Fatalf("calls %d dead %d", len(s.calls), len(d.DeadLetters()))
	}
}

func TestHTTPSender(t *testing.T) {
	var gotSig string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotSig = r.Header.Get(SignatureHeader)
		w.WriteHeader(http.StatusAccepted)
	}))
	defer srv.Close()
	status, err := HTTPSender{Client: srv.Client()}.Send(context.Background(), Delivery{URL: srv.URL, Body: []byte("{}"), Headers: map[string]string{SignatureHeader: "t=1,v1=00"}})
	if err != nil || status != http.StatusAccepted || gotSig != "t=1,v1=00" {
		t.Fatalf("status %d err %v sig %q", status, err, gotSig)
	}
}
