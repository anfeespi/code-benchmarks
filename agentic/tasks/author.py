"""Authoring spec for the agentic-go-v1 tasks.

Each task is defined as exact string edits over the base module
(agentic/go-payments): `start` edits turn the base into the task's starting
state, `solution` edits turn the starting state into the reference solution
("revert" = undo the non-test start edits). Running this script regenerates,
for every task, agentic/tasks/<id>/{task.json,start.patch,solution.patch}.
Hidden acceptance tests live in agentic/tasks/<id>/hidden/ and are written by
hand; they are never generated here.

  uv run --python 3.12 python agentic/tasks/author.py          # rebuild all
  uv run --python 3.12 python agentic/tasks/author.py 03-...   # rebuild one
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "go-payments"


def E(path, old, new):
    return (path, old, new)


TASKS = []


def task(**kw):
    TASKS.append(kw)


# --------------------------------------------------------------------------- 01
task(
    id="01-currency-exponent-format",
    type="bug",
    title="CLP/JPY/KWD amounts rendered with the wrong number of decimals",
    ticket="""PAY-4411 [Bug] Wrong amounts shown for CLP, JPY and KWD payments

A merchant in Chile created a payment of 15000 CLP. The create call succeeds, but every
response (POST /payments, GET /payments/{id}, list) shows "amount": "150.00" and the fee
looks wrong too. Our Japanese merchant reports the same with JPY. KWD (Kuwaiti dinar,
3 decimals) payments of 1.234 KWD come back as "12.34".

Expected: amounts are always rendered in major units with exactly the number of decimals
of their currency (CLP/JPY: none, USD/EUR/BRL/...: 2, KWD: 3). Negative amounts keep the
minus sign. USD behaviour must not change.""",
    start=[
        E("money/amount.go",
          """	if a.Currency.Exponent == 0 {
		return sign + strconv.FormatInt(m, 10)
	}
	f := a.Currency.Factor()
	return fmt.Sprintf("%s%d.%0*d", sign, m/f, a.Currency.Exponent, m%f)
""",
          """	return fmt.Sprintf("%s%d.%02d", sign, m/100, m%100)
"""),
        E("money/money_test.go",
          """func TestDecimalOtherExponents(t *testing.T) {
	tests := []struct {
		minor int64
		code  string
		want  string
	}{
		{15000, "CLP", "15000"},
		{1500, "JPY", "1500"},
		{1234, "KWD", "1.234"},
		{5, "KWD", "0.005"},
	}
	for _, tt := range tests {
		if got := MustNew(tt.minor, tt.code).Decimal(); got != tt.want {
			t.Errorf("Decimal(%d %s) = %q, want %q", tt.minor, tt.code, got, tt.want)
		}
	}
}

""", ""),
    ],
    solution="revert",
)

# --------------------------------------------------------------------------- 02
task(
    id="02-cumulative-refund-limit",
    type="bug",
    title="Multiple partial refunds can exceed the captured amount",
    ticket="""PAY-4420 [Bug] Total refunds exceed the payment amount

Merchant m_8812 refunded 600.00 twice on a 1000.00 USD payment through
POST /payments/{id}/refunds. Both calls returned 201, the payment shows
"refunded_amount": "1200.00" and "remaining_amount": "-200.00", and its status is
still SUCCEEDED. Finance had to recover 200.00 manually.

Expected: the sum of all refunds of a payment can never exceed the payment amount. A
refund larger than what is left must be rejected with 422 refund_exceeds_remaining and
must not change the payment. Refunding exactly the remaining amount is allowed and moves
the payment to REFUNDED.""",
    start=[
        E("payment/service.go", "		if amount.Minor > p.Remaining().Minor {", "		if amount.Minor > p.Amount.Minor {"),
        E("payment/service_test.go",
          """func TestRefundExceedsRemainingAfterPartial(t *testing.T) {
	s, _ := newTestService()
	ctx := context.Background()
	p := succeeded(t, s, 1000)
	if _, _, err := s.Refund(ctx, p.ID, money.MustNew(600, "USD")); err != nil {
		t.Fatal(err)
	}
	if _, _, err := s.Refund(ctx, p.ID, money.MustNew(600, "USD")); !errors.Is(err, ErrRefundExceedsRemaining) {
		t.Fatalf("second refund error = %v, want ErrRefundExceedsRemaining", err)
	}
}

""", ""),
    ],
    solution="revert",
)

# --------------------------------------------------------------------------- 03
task(
    id="03-pagination-skips-items",
    type="bug",
    title="Cursor pagination silently drops one payment per page",
    ticket="""PAY-4432 [Bug] Reconciliation misses payments when paging

The nightly reconciliation job walks GET /merchants/{merchantID}/payments?limit=50
following next_cursor until it is empty. For merchant m_204 (1,000 payments) it only
collects 981 payments; the missing ones are never the first page's. With limit=1 it
returns about half of the payments.

Expected: walking all pages returns every payment of the merchant exactly once, in
creation order, for any limit. next_cursor must be empty on the last page (also when
the total is an exact multiple of the limit).""",
    start=[
        E("store/memory.go",
          """		if offset, err = decodeCursor(page.Cursor); err != nil {
			return nil, "", err
		}
""",
          """		if offset, err = decodeCursor(page.Cursor); err != nil {
			return nil, "", err
		}
		offset++ // resume after the last item of the previous page
"""),
        E("store/memory_test.go",
          """func TestListWalksAllPages(t *testing.T) {
	m := NewMemory()
	ids := seed(t, m, "m1", 7)
	var seen []string
	cursor := ""
	for i := 0; i < 10; i++ {
		got, next, err := m.ListByMerchant(context.Background(), "m1", payment.Page{Cursor: cursor, Limit: 3})
		if err != nil {
			t.Fatal(err)
		}
		for _, p := range got {
			seen = append(seen, p.ID)
		}
		if next == "" {
			break
		}
		cursor = next
	}
	if fmt.Sprint(seen) != fmt.Sprint(ids) {
		t.Fatalf("walked %v, want %v", seen, ids)
	}
}

""", ""),
    ],
    solution="revert",
)

# --------------------------------------------------------------------------- 04
task(
    id="04-webhook-retry-classification",
    type="bug",
    title="Webhook dispatcher retries permanent 4xx failures and gives up on 5xx",
    ticket="""PAY-4450 [Bug] Webhook retries behave backwards

Two merchant complaints this week:
1. Merchant m_77 decommissioned an old endpoint that now answers 410 Gone. Every event is
   still POSTed to it MaxAttempts times with backoff, which their WAF flags as abuse.
   Same with 400/401/404 responses.
2. Merchant m_91 had a 5-minute outage (503). All events from that window went straight
   to the dead-letter list after a single attempt, nothing was retried.

Expected: the dispatcher follows the retry policy documented in the service README.
Dead letters must record the number of attempts and the last HTTP status.""",
    start=[
        E("webhook/dispatcher.go",
          "	return status == http.StatusRequestTimeout || status == http.StatusTooManyRequests || status >= 500\n",
          "	return status == http.StatusRequestTimeout || status == http.StatusTooManyRequests || (status >= 400 && status < 500)\n"),
    ],
    solution="revert",
)

# --------------------------------------------------------------------------- 05
task(
    id="05-idempotency-expiry",
    type="bug",
    title="Idempotency keys never expire after 24h",
    ticket="""PAY-4461 [Bug] Idempotency-Key replays after the 24h TTL

Support case: a merchant reused an Idempotency-Key 40 hours after the original request
(their key generator wraps around daily) for a brand-new payment and received the old
cached response, so the new payment was never created. We also see the idempotency
store's memory growing for two days before it drops.

Expected (as documented): a key expires 24h after it was first used. From that moment
(now >= first use + TTL) it behaves as if it had never been used: Begin starts a new
request, whatever the fingerprint. Before expiry, replay/reuse/in-progress semantics are
unchanged. Expired records must be evicted from memory.""",
    start=[
        E("idempotency/store.go", "	if r, ok := m.records[key]; ok && now.Before(r.ExpiresAt) {", "	if r, ok := m.records[key]; ok {"),
        E("idempotency/store.go", "		if !now.Before(r.ExpiresAt) {\n			delete(m.records, k)", "		if now.Sub(r.ExpiresAt) > m.ttl {\n			delete(m.records, k)"),
    ],
    solution="revert",
)

# --------------------------------------------------------------------------- 06
task(
    id="06-error-status-mapping",
    type="bug",
    title="Every client error is returned as 500 internal_error",
    ticket="""PAY-4475 [Bug] API returns 500 for not-found / conflicts / validation errors

Since last week's release (which added context to error messages across the service),
GET /payments/pay_unknown returns 500 {"error":{"code":"internal_error"}} instead of 404,
capturing an already captured payment returns 500 instead of 409, over-refunds return 500
instead of 422 and malformed bodies return 500 instead of 400. Alerting is firing on the
5xx rate.

Expected: the documented status codes and error codes (see README) for every domain
error, regardless of how much context the error carries. Unexpected errors stay 500 with
a generic message.""",
    start=[
        E("api/errors.go",
          """// errorResponse maps a domain error to an HTTP status and error body. The
// service wraps every error with context, so matching uses errors.Is.
func errorResponse(err error) (int, any) {
	status, code := http.StatusInternalServerError, "internal_error"
	switch {
	case errors.Is(err, payment.ErrNotFound):
		status, code = http.StatusNotFound, "not_found"
	case errors.Is(err, payment.ErrInvalidTransition):
		status, code = http.StatusConflict, "invalid_transition"
	case errors.Is(err, payment.ErrVersionConflict):
		status, code = http.StatusConflict, "conflict"
	case errors.Is(err, payment.ErrRefundExceedsRemaining):
		status, code = http.StatusUnprocessableEntity, "refund_exceeds_remaining"
	case errors.Is(err, payment.ErrInvalidInput),
		errors.Is(err, payment.ErrInvalidCursor),
		errors.Is(err, money.ErrInvalidAmount),
		errors.Is(err, money.ErrPrecision),
		errors.Is(err, money.ErrUnknownCurrency),
		errors.Is(err, money.ErrCurrencyMismatch):
		status, code = http.StatusBadRequest, "invalid_request"
	}
""",
          """// errorResponse maps a domain error to an HTTP status and error body.
func errorResponse(err error) (int, any) {
	status, code := http.StatusInternalServerError, "internal_error"
	switch err {
	case payment.ErrNotFound:
		status, code = http.StatusNotFound, "not_found"
	case payment.ErrInvalidTransition:
		status, code = http.StatusConflict, "invalid_transition"
	case payment.ErrVersionConflict:
		status, code = http.StatusConflict, "conflict"
	case payment.ErrRefundExceedsRemaining:
		status, code = http.StatusUnprocessableEntity, "refund_exceeds_remaining"
	case payment.ErrInvalidInput, payment.ErrInvalidCursor, money.ErrInvalidAmount,
		money.ErrPrecision, money.ErrUnknownCurrency, money.ErrCurrencyMismatch:
		status, code = http.StatusBadRequest, "invalid_request"
	}
"""),
        E("api/errors.go", 'import (\n\t"errors"\n\t"net/http"\n', 'import (\n\t"net/http"\n'),
        E("api/api_test.go",
          """func TestCreatePaymentValidation(t *testing.T) {
	tests := []struct {
		name, body string
	}{
		{"malformed", `{`},
		{"unknown field", `{"merchant_id":"m","amount":"1","currency":"USD","x":1}`},
		{"bad amount", `{"merchant_id":"m","amount":"1.234","currency":"USD"}`},
		{"bad currency", `{"merchant_id":"m","amount":"1","currency":"ZZZ"}`},
		{"missing merchant", `{"amount":"1","currency":"USD"}`},
		{"zero", `{"merchant_id":"m","amount":"0","currency":"USD"}`},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			a := newTestAPI(t)
			rec := a.do("POST", "/payments", tt.body)
			if rec.Code != http.StatusBadRequest {
				t.Fatalf("status %d: %s", rec.Code, rec.Body)
			}
			if e := decode[errorBody](t, rec); e.Error.Code != "invalid_request" {
				t.Fatalf("code %q", e.Error.Code)
			}
		})
	}
}

""", ""),
        E("api/api_test.go",
          """func TestErrorMapping(t *testing.T) {
	a := newTestAPI(t)
	p := a.createSucceeded("10.00", "USD")
	tests := []struct {
		name, method, path, body string
		wantStatus               int
		wantCode                 string
	}{
		{"unknown payment", "GET", "/payments/pay_nope", "", http.StatusNotFound, "not_found"},
		{"capture twice", "POST", "/payments/" + p.ID + "/capture", "", http.StatusConflict, "invalid_transition"},
		{"refund too much", "POST", "/payments/" + p.ID + "/refunds", `{"amount":"10.01"}`, http.StatusUnprocessableEntity, "refund_exceeds_remaining"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			rec := a.do(tt.method, tt.path, tt.body)
			if rec.Code != tt.wantStatus {
				t.Fatalf("status %d, want %d: %s", rec.Code, tt.wantStatus, rec.Body)
			}
			if e := decode[errorBody](t, rec); e.Error.Code != tt.wantCode {
				t.Fatalf("code %q, want %q", e.Error.Code, tt.wantCode)
			}
		})
	}
}

""", ""),
        E("api/api_test.go",
          """	if rec := a.do("GET", "/merchants/m_1/payments?limit=x", ""); rec.Code != http.StatusBadRequest {
		t.Fatalf("bad limit status %d", rec.Code)
	}
""", ""),
    ],
    solution="revert",
)

# --------------------------------------------------------------------------- 07
task(
    id="07-backoff-overflow",
    type="bug",
    title="Late webhook retries fire with no delay",
    ticket="""PAY-4488 [Bug] Webhook retry storm for enterprise merchants

Enterprise merchants run with a custom policy (MaxAttempts: 48, BaseDelay: 1s,
MaxDelay: 1h). When their endpoint is down for a long time, the first ~30 retries are
spaced as expected, but after that the dispatcher fires the remaining attempts
back-to-back with no wait at all (their logs show ~18 requests in the same second).

Expected: the wait between attempts follows the documented exponential backoff and is
always positive, never decreasing, and capped at MaxDelay, for any attempt number and
any reasonable BaseDelay/MaxDelay.""",
    start=[
        E("webhook/dispatcher.go",
          """func (p Policy) Backoff(n int) time.Duration {
	d := p.BaseDelay
	for i := 1; i < n; i++ {
		if d >= p.MaxDelay/2 {
			return p.MaxDelay
		}
		d *= 2
	}
	return min(d, p.MaxDelay)
}""",
          """func (p Policy) Backoff(n int) time.Duration {
	d := p.BaseDelay << (n - 1)
	if d > p.MaxDelay {
		return p.MaxDelay
	}
	return d
}"""),
    ],
    solution="revert",
)

# --------------------------------------------------------------------------- 08
task(
    id="08-cancel-payment",
    type="feature",
    title="Add payment cancellation (CANCELED status + endpoint + webhook)",
    ticket="""PAY-4502 [Story] Merchants can cancel a payment before capture

As a merchant I want to cancel a payment that has not been captured yet (e.g. the
customer abandoned checkout) so it no longer shows as open.

Acceptance criteria:
- New status CANCELED (string "CANCELED"), exported as payment.StatusCanceled. It is final
  (Status.Final() is true) and ParseStatus accepts it (case-insensitive like the others).
- New service method `func (s *Service) Cancel(ctx context.Context, id string) (Payment, error)`.
  Allowed from CREATED and PENDING only; anything else fails with an error wrapping
  ErrInvalidTransition. Unknown ids fail with an error wrapping ErrNotFound.
- A successful cancel emits the event "payment.canceled" (delivered as a webhook like the
  other events).
- HTTP: POST /payments/{id}/cancel returns 200 with the payment body (status "CANCELED"),
  409 invalid_transition when not cancelable, 404 not_found for unknown ids.
- A canceled payment cannot be authorized, captured, declined or refunded (409).""",
    start=[],
    solution=[
        E("payment/payment.go",
          """	StatusRefunded  Status = "REFUNDED"
)

var allStatuses = []Status{StatusCreated, StatusPending, StatusSucceeded, StatusDeclined, StatusRefunded}""",
          """	StatusRefunded  Status = "REFUNDED"
	StatusCanceled  Status = "CANCELED"
)

var allStatuses = []Status{StatusCreated, StatusPending, StatusSucceeded, StatusDeclined, StatusRefunded, StatusCanceled}"""),
        E("payment/payment.go",
          "func (s Status) Final() bool { return s == StatusDeclined || s == StatusRefunded }",
          "func (s Status) Final() bool {\n\treturn s == StatusDeclined || s == StatusRefunded || s == StatusCanceled\n}"),
        E("payment/service.go",
          """// Refund refunds amount of a SUCCEEDED payment.""",
          """// Cancel moves a CREATED or PENDING payment to CANCELED.
func (s *Service) Cancel(ctx context.Context, id string) (Payment, error) {
	return s.mutate(ctx, id, func(p *Payment) (Event, error) {
		switch p.Status {
		case StatusCreated, StatusPending:
			p.Status = StatusCanceled
			return Event{Type: "payment.canceled"}, nil
		default:
			return Event{}, fmt.Errorf("%w: cannot cancel a %s payment", ErrInvalidTransition, p.Status)
		}
	})
}

// Refund refunds amount of a SUCCEEDED payment."""),
        E("api/server.go",
          '	s.mux.HandleFunc("POST /payments/{id}/decline", s.declinePayment)\n',
          '	s.mux.HandleFunc("POST /payments/{id}/decline", s.declinePayment)\n	s.mux.HandleFunc("POST /payments/{id}/cancel", s.cancelPayment)\n'),
        E("api/handlers.go",
          "func (s *Server) refundPayment(",
          """func (s *Server) cancelPayment(w http.ResponseWriter, r *http.Request) {
	s.respondPayment(w, func() (payment.Payment, error) { return s.svc.Cancel(r.Context(), r.PathValue("id")) })
}

func (s *Server) refundPayment("""),
    ],
)

# --------------------------------------------------------------------------- 09
task(
    id="09-list-status-filter",
    type="feature",
    title="Filter the merchant payment listing by status",
    ticket="""PAY-4510 [Story] Filter payments by status in the listing endpoint

The merchant dashboard needs "show only succeeded payments".

Acceptance criteria:
- GET /merchants/{merchantID}/payments accepts an optional `status` query parameter
  (case-insensitive, one of the payment statuses). Only payments in that status are
  returned.
- Pagination keeps working on the filtered result: every page except the last one is
  full (exactly `limit` items), items stay in creation order, walking next_cursor returns
  each matching payment exactly once and next_cursor is empty after the last match.
- An unknown status returns 400 invalid_request.
- Without `status` the endpoint behaves exactly as today.""",
    start=[],
    solution=[
        E("payment/payment.go",
          """type Page struct {
	Cursor string
	Limit  int
}""",
          """type Page struct {
	Cursor string
	Limit  int
	// Status, when set, restricts the listing to payments in that status.
	Status Status
}"""),
        E("store/memory.go",
          """	ids := m.byMerchant[merchantID]
	if offset > len(ids) {""",
          """	ids := m.byMerchant[merchantID]
	if page.Status != "" {
		filtered := make([]string, 0, len(ids))
		for _, id := range ids {
			if m.byID[id].Status == page.Status {
				filtered = append(filtered, id)
			}
		}
		ids = filtered
	}
	if offset > len(ids) {"""),
        E("api/handlers.go",
          """		page.Limit = n
	}
""",
          """		page.Limit = n
	}
	if v := q.Get("status"); v != "" {
		st, err := payment.ParseStatus(v)
		if err != nil {
			writeError(w, err)
			return
		}
		page.Status = st
	}
"""),
    ],
)

# --------------------------------------------------------------------------- 10
task(
    id="10-dead-letter-replay",
    type="feature",
    title="Replay a dead-lettered webhook event",
    ticket="""PAY-4523 [Story] Ops can re-deliver dead-lettered webhooks

After a merchant fixes their endpoint, ops needs to re-send the events that ended in
the dead-letter list (GET /webhooks/dead-letters already lists them).

Acceptance criteria:
- New method `func (d *Dispatcher) Replay(ctx context.Context, eventID string) (delivered bool, err error)`
  in package webhook. It removes the event from the dead-letter list and delivers it
  again with the normal retry policy, with the SAME event id and payload (merchants
  dedupe on Webhook-Id; the signature is recomputed at send time as usual).
  - delivered: returns (true, nil); the event is no longer dead-lettered.
  - fails again: returns (false, nil); the event is in the dead-letter list exactly once,
    with the attempts/status of the new delivery.
  - unknown event id: returns an error wrapping the new exported `webhook.ErrDeadLetterNotFound`.
- HTTP: POST /webhooks/dead-letters/{eventID}/replay returns 200
  {"event_id": "<id>", "delivered": true|false}; unknown id -> 404 not_found.""",
    start=[],
    solution=[
        E("webhook/dispatcher.go",
          """import (
	"context"
	"encoding/json"
	"fmt\"""",
          """import (
	"context"
	"encoding/json"
	"errors"
	"fmt\""""),
        E("webhook/dispatcher.go",
          """// Event is the webhook payload.""",
          """// ErrDeadLetterNotFound is returned when replaying an event that is not dead-lettered.
var ErrDeadLetterNotFound = errors.New("dead letter not found")

// Event is the webhook payload."""),
        E("webhook/dispatcher.go",
          """	for i, ev := range batch {
		if err := d.deliver(ctx, ev); err != nil {""",
          """	for i, ev := range batch {
		if _, err := d.deliver(ctx, ev); err != nil {"""),
        E("webhook/dispatcher.go",
          """// deliver attempts ev until success, a permanent failure or MaxAttempts.
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
	}""",
          """// Replay re-delivers a dead-lettered event with the normal retry policy.
func (d *Dispatcher) Replay(ctx context.Context, eventID string) (bool, error) {
	d.mu.Lock()
	idx := -1
	for i, dl := range d.dead {
		if dl.Event.ID == eventID {
			idx = i
			break
		}
	}
	if idx < 0 {
		d.mu.Unlock()
		return false, fmt.Errorf("replay %s: %w", eventID, ErrDeadLetterNotFound)
	}
	dl := d.dead[idx]
	d.dead = append(d.dead[:idx:idx], d.dead[idx+1:]...)
	d.mu.Unlock()

	delivered, err := d.deliver(ctx, dl.Event)
	if err != nil {
		d.mu.Lock()
		d.dead = append(d.dead, dl)
		d.mu.Unlock()
		return false, fmt.Errorf("replay %s: %w", eventID, err)
	}
	return delivered, nil
}

// deliver attempts ev until success, a permanent failure or MaxAttempts and
// reports whether it was delivered. It only returns an error when ctx is done.
func (d *Dispatcher) deliver(ctx context.Context, ev Event) (bool, error) {
	ep, ok := d.endpoints.Endpoint(ev.MerchantID)
	if !ok {
		return false, nil // merchant has no webhook configured
	}
	body, err := json.Marshal(ev)
	if err != nil {
		d.deadLetter(ev, 0, 0, fmt.Errorf("encode event: %w", err))
		return false, nil
	}"""),
        E("webhook/dispatcher.go",
          """			d.delivered++
			d.mu.Unlock()
			return nil
		}""",
          """			d.delivered++
			d.mu.Unlock()
			return true, nil
		}"""),
        E("webhook/dispatcher.go",
          """		if err := d.clock.Sleep(ctx, d.policy.Backoff(attempt)); err != nil {
			return err
		}
	}
	d.deadLetter(ev, attempt, status, sendErr)
	return nil
}""",
          """		if err := d.clock.Sleep(ctx, d.policy.Backoff(attempt)); err != nil {
			return false, err
		}
	}
	d.deadLetter(ev, attempt, status, sendErr)
	return false, nil
}"""),
        E("api/server.go",
          '	s.mux.HandleFunc("GET /webhooks/dead-letters", s.listDeadLetters)\n',
          '	s.mux.HandleFunc("GET /webhooks/dead-letters", s.listDeadLetters)\n	s.mux.HandleFunc("POST /webhooks/dead-letters/{eventID}/replay", s.replayDeadLetter)\n'),
        E("api/handlers.go",
          "func (s *Server) respondPayment(",
          """func (s *Server) replayDeadLetter(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("eventID")
	delivered, err := s.hooks.Replay(r.Context(), id)
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"event_id": id, "delivered": delivered})
}

func (s *Server) respondPayment("""),
        E("api/errors.go",
          """	case errors.Is(err, payment.ErrNotFound):""",
          """	case errors.Is(err, payment.ErrNotFound), errors.Is(err, webhook.ErrDeadLetterNotFound):"""),
        E("api/errors.go",
          '	"example.com/gopayments/payment"\n)',
          '	"example.com/gopayments/payment"\n	"example.com/gopayments/webhook"\n)'),
    ],
)

# --------------------------------------------------------------------------- 11
task(
    id="11-amount-minor-contract",
    type="api-change",
    title="Accept and return integer minor units, backward compatible",
    ticket="""PAY-4530 [Story] API v2 amounts: integer minor units (backward compatible)

New SDKs send amounts as integers in minor units to avoid any decimal parsing. Old
SDKs (decimal strings) must keep working unchanged for at least two more quarters.

Acceptance criteria:
- POST /payments accepts `amount_minor` (JSON integer, minor units of `currency`) as an
  alternative to the legacy `amount` (decimal string). Exactly one is required: if
  neither is present -> 400 invalid_request. If both are present they must denote the
  same value (e.g. "10.50" and 1050 for USD), otherwise 400 invalid_request.
- POST /payments/{id}/refunds accepts `amount_minor` the same way (minor units of the
  payment's currency), with the same rules.
- Payment responses keep every existing field unchanged and ADD the integers
  `amount_minor`, `fee_minor`, `refunded_minor`, `remaining_minor`; each item of `refunds`
  gains `amount_minor`. This applies to every endpoint returning payments (incl. list).
- Idempotency: a retry that uses the other format for the same amount (e.g. first call
  `"amount":"10.50"`, retry `"amount_minor":1050`) is the same request and is replayed.
- Unknown JSON fields are still rejected.""",
    start=[],
    solution=[
        E("api/dto.go",
          """type createPaymentRequest struct {
	MerchantID string `json:"merchant_id"`
	Amount     string `json:"amount"`
	Currency   string `json:"currency"`
}

type refundRequest struct {
	Amount string `json:"amount"`
}""",
          """type createPaymentRequest struct {
	MerchantID  string `json:"merchant_id"`
	Amount      string `json:"amount"`
	AmountMinor *int64 `json:"amount_minor"`
	Currency    string `json:"currency"`
}

type refundRequest struct {
	Amount      string `json:"amount"`
	AmountMinor *int64 `json:"amount_minor"`
}"""),
        E("api/dto.go",
          """type refundResponse struct {
	ID        string    `json:"id"`
	Amount    string    `json:"amount"`
	CreatedAt time.Time `json:"created_at"`
}""",
          """type refundResponse struct {
	ID          string    `json:"id"`
	Amount      string    `json:"amount"`
	AmountMinor int64     `json:"amount_minor"`
	CreatedAt   time.Time `json:"created_at"`
}"""),
        E("api/dto.go",
          """	Refunds         []refundResponse `json:"refunds"`
	CreatedAt       time.Time        `json:"created_at"`
	UpdatedAt       time.Time        `json:"updated_at"`
}""",
          """	Refunds         []refundResponse `json:"refunds"`
	CreatedAt       time.Time        `json:"created_at"`
	UpdatedAt       time.Time        `json:"updated_at"`
	AmountMinor     int64            `json:"amount_minor"`
	FeeMinor        int64            `json:"fee_minor"`
	RefundedMinor   int64            `json:"refunded_minor"`
	RemainingMinor  int64            `json:"remaining_minor"`
}"""),
        E("api/dto.go",
          """		CreatedAt:       p.CreatedAt.UTC(),
		UpdatedAt:       p.UpdatedAt.UTC(),
	}
	for _, r := range p.Refunds {
		out.Refunds = append(out.Refunds, refundResponse{ID: r.ID, Amount: r.Amount.Decimal(), CreatedAt: r.CreatedAt.UTC()})
	}""",
          """		CreatedAt:       p.CreatedAt.UTC(),
		UpdatedAt:       p.UpdatedAt.UTC(),
		AmountMinor:     p.Amount.Minor,
		FeeMinor:        p.Fee.Minor,
		RefundedMinor:   p.Refunded,
		RemainingMinor:  p.Remaining().Minor,
	}
	for _, r := range p.Refunds {
		out.Refunds = append(out.Refunds, refundResponse{ID: r.ID, Amount: r.Amount.Decimal(), AmountMinor: r.Amount.Minor, CreatedAt: r.CreatedAt.UTC()})
	}"""),
        E("api/handlers.go",
          """	amount, err := money.Parse(req.Amount, req.Currency)
	if err != nil {
		writeError(w, fmt.Errorf("amount: %w", err))
		return
	}
	in := payment.CreateInput""",
          """	amount, err := resolveAmount(req.Amount, req.AmountMinor, req.Currency)
	if err != nil {
		writeError(w, fmt.Errorf("amount: %w", err))
		return
	}
	in := payment.CreateInput"""),
        E("api/handlers.go",
          """	amount, err := money.Parse(req.Amount, p.Amount.Currency.Code)
	if err != nil {""",
          """	amount, err := resolveAmount(req.Amount, req.AmountMinor, p.Amount.Currency.Code)
	if err != nil {"""),
        E("api/handlers.go",
          "func decodeJSON(",
          """// resolveAmount accepts the legacy decimal string, the v2 integer minor
// units, or both when they agree.
func resolveAmount(decimal string, minor *int64, currency string) (money.Amount, error) {
	switch {
	case decimal == "" && minor == nil:
		return money.Amount{}, fmt.Errorf("%w: amount or amount_minor is required", payment.ErrInvalidInput)
	case minor == nil:
		return money.Parse(decimal, currency)
	}
	fromMinor, err := money.New(*minor, currency)
	if err != nil {
		return money.Amount{}, err
	}
	if decimal != "" {
		fromDecimal, err := money.Parse(decimal, currency)
		if err != nil {
			return money.Amount{}, err
		}
		if fromDecimal != fromMinor {
			return money.Amount{}, fmt.Errorf("%w: amount %q and amount_minor %d disagree", payment.ErrInvalidInput, decimal, *minor)
		}
	}
	return fromMinor, nil
}

func decodeJSON("""),
    ],
)

# --------------------------------------------------------------------------- 12
task(
    id="12-transition-table-refactor",
    type="refactor",
    title="Centralize the payment status machine in one transition table",
    ticket="""PAY-4541 [Tech debt] Single source of truth for status transitions

The allowed status changes are scattered across switch statements in
payment.Service (Authorize, Capture, Decline, Refund). Every new status means touching
all of them, and we already shipped one inconsistency last quarter.

Do:
- Add `func CanTransition(from, to Status) bool` in package payment. It is the only place
  that knows which transitions are allowed:
  CREATED->PENDING, CREATED->DECLINED, PENDING->SUCCEEDED, PENDING->DECLINED,
  SUCCEEDED->REFUNDED. Nothing else (no self transitions). A partial refund is not a
  status change; it is allowed exactly when a full refund would be.
- Every service method must validate status changes through CanTransition; no
  `switch p.Status` (or equivalent if/else chains on the status) may remain in
  payment/service.go.
- Pure refactor: public behaviour, events, returned payments and errors (still wrapping
  ErrInvalidTransition, ErrRefundExceedsRemaining, ...) must not change.""",
    start=[],
    solution=[
        E("payment/transitions.go", None,
          """package payment

// transitions lists every allowed status change.
var transitions = map[Status][]Status{
	StatusCreated:   {StatusPending, StatusDeclined},
	StatusPending:   {StatusSucceeded, StatusDeclined},
	StatusSucceeded: {StatusRefunded},
}

// CanTransition reports whether a payment may move from one status to another.
func CanTransition(from, to Status) bool {
	for _, s := range transitions[from] {
		if s == to {
			return true
		}
	}
	return false
}
"""),
        E("payment/service.go",
          """		switch p.Status {
		case StatusCreated:
			p.Status = StatusPending
			return Event{Type: "payment.pending"}, nil
		default:
			return Event{}, fmt.Errorf("%w: cannot authorize a %s payment", ErrInvalidTransition, p.Status)
		}""",
          """		if !CanTransition(p.Status, StatusPending) {
			return Event{}, fmt.Errorf("%w: cannot authorize a %s payment", ErrInvalidTransition, p.Status)
		}
		p.Status = StatusPending
		return Event{Type: "payment.pending"}, nil"""),
        E("payment/service.go",
          """		switch p.Status {
		case StatusPending:
			p.Status = StatusSucceeded
			return Event{Type: "payment.succeeded"}, nil
		default:
			return Event{}, fmt.Errorf("%w: cannot capture a %s payment", ErrInvalidTransition, p.Status)
		}""",
          """		if !CanTransition(p.Status, StatusSucceeded) {
			return Event{}, fmt.Errorf("%w: cannot capture a %s payment", ErrInvalidTransition, p.Status)
		}
		p.Status = StatusSucceeded
		return Event{Type: "payment.succeeded"}, nil"""),
        E("payment/service.go",
          """		switch p.Status {
		case StatusCreated, StatusPending:
			p.Status = StatusDeclined
			p.DeclineReason = reason
			return Event{Type: "payment.declined"}, nil
		default:
			return Event{}, fmt.Errorf("%w: cannot decline a %s payment", ErrInvalidTransition, p.Status)
		}""",
          """		if !CanTransition(p.Status, StatusDeclined) {
			return Event{}, fmt.Errorf("%w: cannot decline a %s payment", ErrInvalidTransition, p.Status)
		}
		p.Status = StatusDeclined
		p.DeclineReason = reason
		return Event{Type: "payment.declined"}, nil"""),
        E("payment/service.go",
          """		switch p.Status {
		case StatusSucceeded:
		default:
			return Event{}, fmt.Errorf("%w: cannot refund a %s payment", ErrInvalidTransition, p.Status)
		}""",
          """		if !CanTransition(p.Status, StatusRefunded) {
			return Event{}, fmt.Errorf("%w: cannot refund a %s payment", ErrInvalidTransition, p.Status)
		}"""),
    ],
)

# --------------------------------------------------------------------------- 13
task(
    id="13-idempotency-store-race",
    type="concurrency",
    title="Idempotency store is not safe under concurrent retries",
    ticket="""PAY-4555 [Bug][P1] Crash and duplicate refunds under concurrent retries

During the Black Friday load test (clients retry aggressively with the same
Idempotency-Key):
1. Pods crashed several times with `fatal error: concurrent map read and map write`;
   the goroutine dump points at package idempotency.
2. Twice, two refunds were created for a single Idempotency-Key when two retries
   arrived at the same time.
`go test -race` on our integration suite also reports DATA RACE in the same package.

Expected: idempotency.Memory is safe for concurrent use by any number of goroutines,
and for a given key at most one concurrent Begin can start the request (the others get
ErrInProgress or, once completed, the stored response).""",
    start=[
        E("idempotency/store.go",
          """	m.mu.Lock()
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
}""",
          """	now := m.clock.Now()
	m.mu.Lock()
	m.purgeLocked(now)
	r, ok := m.records[key]
	m.mu.Unlock()

	if ok && now.Before(r.ExpiresAt) {
		if r.Fingerprint != fingerprint {
			return Record{}, false, fmt.Errorf("%w: key %q", ErrKeyReuse, key)
		}
		if !r.Completed {
			return Record{}, false, fmt.Errorf("%w: key %q", ErrInProgress, key)
		}
		return copyRecord(r), false, nil
	}
	r = &Record{Key: key, Fingerprint: fingerprint, ExpiresAt: now.Add(m.ttl)}
	m.mu.Lock()
	m.records[key] = r
	m.mu.Unlock()
	return copyRecord(r), true, nil
}"""),
        E("idempotency/store.go",
          """// Complete implements Store.
func (m *Memory) Complete(_ context.Context, key string, resp Response) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	r, ok := m.records[key]""",
          """// Complete implements Store. Only the request that began key writes its
// record, so no locking is needed here.
func (m *Memory) Complete(_ context.Context, key string, resp Response) error {
	r, ok := m.records[key]"""),
        E("idempotency/store.go",
          """func (m *Memory) Release(_ context.Context, key string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if _, ok""",
          """func (m *Memory) Release(_ context.Context, key string) error {
	if _, ok"""),
        E("idempotency/store.go",
          """	if _, ok := m.records[key]; !ok {
		return fmt.Errorf("%w: %q", ErrUnknownKey, key)
	}
	delete(m.records, key)
	return nil""",
          """	if _, ok := m.records[key]; !ok {
		return fmt.Errorf("%w: %q", ErrUnknownKey, key)
	}
	m.mu.Lock()
	delete(m.records, key)
	m.mu.Unlock()
	return nil"""),
    ],
    solution="revert",
)

# --------------------------------------------------------------------------- 14
task(
    id="14-repository-aliasing-race",
    type="concurrency",
    title="In-memory repository shares mutable state with callers",
    ticket="""PAY-4561 [Bug] DATA RACE and phantom refunds under concurrent refunds

Our integration suite (`go test -race`, store.Memory as repository) reports DATA RACE
between payment.(*Service).Refund calls running concurrently on the same payment.
In a staging soak test one payment ended with 5 entries in `refunds` whose amounts do not
add up to `refunded_amount`; one refund id appears that was never returned to any client
(its request had failed with a version conflict).

Expected: concurrent operations on the same payment are race-free; a failed update
(version conflict) leaves no trace in the stored payment; values handed to or returned by
the repository never share mutable state with what is stored. Optimistic locking
semantics must not change.""",
    start=[
        E("store/memory.go", "	m.byID[p.ID] = p.Clone()\n	m.byMerchant", "	m.byID[p.ID] = p\n	m.byMerchant"),
        E("store/memory.go",
          """// Get returns a copy of the stored payment.""",
          """// Get returns the stored payment. Payment is a value type, so the caller
// gets its own copy."""),
        E("store/memory.go", "	return p.Clone(), nil\n}", "	return p, nil\n}"),
        E("store/memory.go", "	next := p.Clone()\n	next.Version++", "	next := p\n	next.Version++"),
        E("store/memory.go", "		out = append(out, m.byID[id].Clone())", "		out = append(out, m.byID[id])"),
    ],
    solution="revert",
)

# --------------------------------------------------------------------------- 15
task(
    id="15-idempotency-purge-perf",
    type="performance",
    title="Idempotency Begin gets slower with every stored key",
    ticket="""PAY-4570 [Bug][Perf] POST latency grows with traffic since last deploy

After the last deploy, p99 of POST /payments and POST /payments/{id}/refunds grows
steadily with traffic and only recovers when pods restart: ~5ms right after a restart,
>2s after a few hours of peak traffic. CPU profiles show almost all time under
idempotency.(*Memory).Begin.

Expected: Begin cost must not grow with the number of stored keys (a store holding tens
of thousands of live keys must keep Begin in the microsecond range). Expiry semantics
must not change: expired keys must never be replayed, and expired records must still be
evicted so memory stays bounded (evicting at most once per minute is acceptable).""",
    start=[
        E("idempotency/store.go",
          """import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time\"""",
          """import (
	"context"
	"errors"
	"fmt"
	"sort"
	"sync"
	"time\""""),
        E("idempotency/store.go",
          """// DefaultPurgeInterval is how often expired records are evicted.
const DefaultPurgeInterval = time.Minute

""", ""),
        E("idempotency/store.go",
          """	mu        sync.Mutex
	records   map[string]*Record
	nextPurge time.Time
}""",
          """	mu      sync.Mutex
	records map[string]*Record
}"""),
        E("idempotency/store.go",
          """// purgeLocked evicts expired records at most once per DefaultPurgeInterval.
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
}""",
          """// purgeLocked evicts expired records, oldest first.
func (m *Memory) purgeLocked(now time.Time) {
	recs := make([]*Record, 0, len(m.records))
	for _, r := range m.records {
		recs = append(recs, r)
	}
	sort.Slice(recs, func(i, j int) bool { return recs[i].ExpiresAt.Before(recs[j].ExpiresAt) })
	for _, r := range recs {
		if now.Before(r.ExpiresAt) {
			break
		}
		delete(m.records, r.Key)
	}
}"""),
    ],
    solution="revert",
)

# --------------------------------------------------------------------------- 16
task(
    id="16-split-payout-rounding",
    type="trap",
    title="Split payouts do not reconcile with the charged amount",
    ticket="""PAY-4588 [Bug] Marketplace split payouts lose or create cents

Marketplace merchants split each charge between sub-merchants with money.Allocate.
Finance reconciliation fails daily:
- a 100.00 USD charge split equally across 3 sub-merchants pays out 33.33 x 3 = 99.99;
- a 0.10 USD charge split 1:1:1:1:1:1:1 pays out 0.07;
- some splits pay out MORE than was charged (0.05 USD split 1:1 pays 0.03 + 0.03).

Fix the split so payouts always reconcile, respecting the documented contract of
money.Allocate.""",
    start=[
        E("money/allocate.go",
          """import (
	"fmt"
	"sort"
)""",
          """import (
	"fmt"
	"math"
)"""),
        E("money/allocate.go",
          """	parts := make([]Amount, len(ratios))
	rems := make([]int64, len(ratios))
	var assigned int64
	for i, r := range ratios {
		share := a.Minor * r
		parts[i] = Amount{Minor: share / total, Currency: a.Currency}
		rems[i] = share % total
		assigned += parts[i].Minor
	}

	order := make([]int, len(ratios))
	for i := range order {
		order[i] = i
	}
	sort.SliceStable(order, func(x, y int) bool { return rems[order[x]] > rems[order[y]] })
	for i := int64(0); i < a.Minor-assigned; i++ {
		parts[order[i]].Minor++
	}
	return parts, nil""",
          """	parts := make([]Amount, len(ratios))
	for i, r := range ratios {
		share := float64(a.Minor) * float64(r) / float64(total)
		parts[i] = Amount{Minor: int64(math.Round(share)), Currency: a.Currency}
	}
	return parts, nil"""),
        E("money/money_test.go",
          """func TestAllocateRemainder(t *testing.T) {
	tests := []struct {
		amount int64
		ratios []int64
		want   []int64
	}{
		{100, []int64{1, 1, 1}, []int64{34, 33, 33}},
		{5, []int64{3, 7}, []int64{2, 3}},
	}
	for _, tt := range tests {
		parts, err := Allocate(MustNew(tt.amount, "USD"), tt.ratios)
		if err != nil {
			t.Fatal(err)
		}
		for i, p := range parts {
			if p.Minor != tt.want[i] {
				t.Fatalf("Allocate(%d, %v)[%d] = %d, want %d", tt.amount, tt.ratios, i, p.Minor, tt.want[i])
			}
		}
	}
}

""", ""),
    ],
    solution="revert",
)

# --------------------------------------------------------------------------- 17
task(
    id="17-idempotency-fingerprint",
    type="trap",
    title="Identical retries rejected as idempotency key reuse",
    ticket="""PAY-4593 [Bug] Mobile SDK retries rejected with 422 idempotency_key_reused

Since the new iOS SDK rollout, ~3% of payment creations fail: the first POST /payments
times out on the client, the SDK retries with the same Idempotency-Key and gets
422 {"error":{"code":"idempotency_key_reused"}}. The customer is then charged on
the second manual attempt, but the merchant sees two payments in some cases.

The SDK rebuilds the JSON on retry. Captured example for one key:
  first:  {"merchant_id":"m_310","amount":"10.50","currency":"USD"}
  retry:  {"currency": "usd", "amount": "10.5", "merchant_id": "m_310"}
Refund retries (POST /payments/{id}/refunds) show the same problem
({"amount":"5.00"} then {"amount": "5"}).

Make retries of the same request with the same key replay the original response.""",
    start=[
        E("api/handlers.go",
          """func (s *Server) createPayment(w http.ResponseWriter, r *http.Request) {
	var req createPaymentRequest""",
          """func (s *Server) createPayment(w http.ResponseWriter, r *http.Request) {
	fp, err := bodyFingerprint(r)
	if err != nil {
		writeError(w, err)
		return
	}
	var req createPaymentRequest"""),
        E("api/handlers.go",
          "	s.idempotent(w, r, createFingerprint(in), func() (int, any) {",
          "	s.idempotent(w, r, fp, func() (int, any) {"),
        E("api/handlers.go",
          """	id := r.PathValue("id")
	var req refundRequest""",
          """	id := r.PathValue("id")
	fp, err := bodyFingerprint(r)
	if err != nil {
		writeError(w, err)
		return
	}
	var req refundRequest"""),
        E("api/handlers.go",
          "	s.idempotent(w, r, refundFingerprint(id, amount), func() (int, any) {",
          "	s.idempotent(w, r, fp, func() (int, any) {"),
        E("api/idempotency.go",
          """// createFingerprint hashes the decoded request, not the raw body, so
// semantically identical retries match regardless of JSON formatting.
func createFingerprint(in payment.CreateInput) string {
	return hash(fmt.Sprintf("create|%s|%d|%s", in.MerchantID, in.Amount.Minor, in.Amount.Currency.Code))
}

func refundFingerprint(paymentID string, amount money.Amount) string {
	return hash(fmt.Sprintf("refund|%s|%d|%s", paymentID, amount.Minor, amount.Currency.Code))
}
""",
          """// bodyFingerprint hashes the request path and raw body, then restores the
// body so the handler can decode it.
func bodyFingerprint(r *http.Request) (string, error) {
	raw, err := io.ReadAll(io.LimitReader(r.Body, maxBodyBytes))
	if err != nil {
		return "", fmt.Errorf("%w: read body: %v", payment.ErrInvalidInput, err)
	}
	r.Body = io.NopCloser(bytes.NewReader(raw))
	return hash(r.URL.Path + "|" + string(raw)), nil
}
"""),
        E("api/idempotency.go",
          """import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"

	"example.com/gopayments/idempotency"
	"example.com/gopayments/money"
	"example.com/gopayments/payment"
)""",
          """import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"

	"example.com/gopayments/idempotency"
	"example.com/gopayments/payment"
)"""),
    ],
    solution="revert",
)

# --------------------------------------------------------------------------- 18
task(
    id="18-fee-rounding",
    type="trap",
    title="Processing fees overcharged by one cent",
    ticket="""PAY-4601 [Bug] Merchants overcharged one cent on processing fees

Merchant statements show fees one minor unit too high on many payments. Example with
the standard 290 bps (2.9%) fee: a 10.05 USD payment shows fee 0.30, finance expects 0.29.
Large-ticket merchants (KRW-like volumes in minor units, B2B invoices) also report fees
that are off by a few units on very large amounts.

Fees must follow the finance rounding policy documented on money.Fee for every amount
the type can hold.""",
    start=[
        E("money/fee.go",
          """import "fmt\"""",
          """import (
	"fmt"
	"math"
)"""),
        E("money/fee.go",
          """	// Split a into a multiple of 10000 and a remainder so a*bps never overflows.
	q, r := a.Minor/10000, a.Minor%10000
	fee := q * bps
	num := r * bps
	fee += num / 10000
	rem := num % 10000
	switch {
	case rem*2 > 10000:
		fee++
	case rem*2 == 10000 && fee%2 != 0:
		fee++
	}
	return Amount{Minor: fee, Currency: a.Currency}, nil""",
          """	fee := math.Ceil(float64(a.Minor) * float64(bps) / 10000)
	return Amount{Minor: int64(fee), Currency: a.Currency}, nil"""),
    ],
    solution="revert",
)


# --------------------------------------------------------------------------- build

def apply_edits(root: Path, edits):
    for path, old, new in edits:
        f = root / path
        if old is None:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(new)
            continue
        text = f.read_text()
        n = text.count(old)
        if n != 1:
            raise SystemExit("%s: edit target found %d times in %s:\n%s" % (root.name, n, path, old[:200]))
        f.write_text(text.replace(old, new))


def revert(root: Path, edits):
    """Restore every non-test file touched by the start edits from the base."""
    for path in sorted({e[0] for e in edits if not e[0].endswith("_test.go")}):
        shutil.copyfile(BASE / path, root / path)


def diff(a: Path, b: Path) -> str:
    r = subprocess.run(["diff", "-ruN", "a", "b"], cwd=a.parent, capture_output=True, text=True)
    if r.returncode not in (0, 1):
        raise SystemExit(r.stderr)
    return r.stdout


def build(t):
    out = HERE / t["id"]
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        base = tmp / "p1" / "a"
        start = tmp / "p1" / "b"
        shutil.copytree(BASE, base)
        shutil.copytree(BASE, start)
        apply_edits(start, t["start"])
        start_patch = diff(base, start)
        start_a = tmp / "p2" / "a"
        sol = tmp / "p2" / "b"
        shutil.copytree(start, start_a)
        shutil.copytree(start, sol)
        if t["solution"] == "revert":
            revert(sol, t["start"])
        else:
            apply_edits(sol, t["solution"])
        sol_patch = diff(start_a, sol)
    (out / "start.patch").write_text(start_patch)
    (out / "solution.patch").write_text(sol_patch)
    touched = sorted({line[6:].split("\t")[0] for line in sol_patch.splitlines() if line.startswith("+++ b/")})
    meta = {"id": t["id"], "type": t["type"], "title": t["title"], "ticket": t["ticket"],
            "solution_files": touched}
    (out / "task.json").write_text(json.dumps(meta, indent=1) + "\n")
    print("%-34s start %4d lines  solution %4d lines  %s" % (t["id"], len(start_patch.splitlines()),
                                                            len(sol_patch.splitlines()), ",".join(touched)))


if __name__ == "__main__":
    only = set(sys.argv[1:])
    for t in TASKS:
        if not only or t["id"] in only:
            build(t)
