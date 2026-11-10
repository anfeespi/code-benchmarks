# go-payments

Payments microservice (stdlib only, Go 1.22+). In-memory storage; production
swaps `store.Memory` for a database-backed `payment.Repository`.

## Layout

| package       | responsibility |
|---------------|----------------|
| `money`       | exact amounts in minor units, parsing/formatting, fee and split rounding |
| `payment`     | domain model, status machine, `Repository` contract, `Service` |
| `store`       | in-memory `payment.Repository` with cursor pagination |
| `idempotency` | `Idempotency-Key` store (TTL 24h in production) |
| `webhook`     | signed event delivery with retries and a dead-letter list |
| `api`         | net/http handlers (Go 1.22 `ServeMux` patterns) |
| `clock`       | injectable clock; `clock.Fake` never really sleeps |
| `cmd/server`  | wiring |

## Payment lifecycle

```
CREATED --authorize--> PENDING --capture--> SUCCEEDED --refund (full)--> REFUNDED
   |                      |                     |
   +------decline---------+--> DECLINED         +-- refund (partial): stays SUCCEEDED
```

Every state change emits an event (`payment.created`, `payment.pending`,
`payment.succeeded`, `payment.declined`, `payment.partially_refunded`,
`payment.refunded`) that the webhook dispatcher delivers to the merchant.

## Conventions

- Money never touches floating point. Amounts on the API are decimal strings
  in major units (`"10.50"`), with the currency's exact number of decimals.
- Errors are wrapped with `fmt.Errorf("...: %w", err)`; match them with `errors.Is`.
- Error responses: `{"error": {"code": "...", "message": "..."}}`.
  `not_found` 404, `invalid_transition` 409, `conflict` 409,
  `refund_exceeds_remaining` 422, `invalid_request` 400,
  `idempotency_key_reused` 422, `request_in_progress` 409.
- Public constructors (`NewService`, `NewServer`, `NewMemory`, `NewDispatcher`)
  are used by other teams' integration tests: keep their signatures stable.

## Webhooks

- Header `Webhook-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, "<t>.<body>")>`.
- Retry policy: transport errors, `408`, `429` and `5xx` are retried with
  exponential backoff (`BaseDelay * 2^(n-1)`, capped at `MaxDelay`) up to
  `MaxAttempts`; any other non-2xx status is permanent and goes straight to the
  dead-letter list.

## Idempotency

`POST /payments` and `POST /payments/{id}/refunds` accept `Idempotency-Key`.
A retry with the same key and the same request replays the stored response
(header `Idempotent-Replayed: true`); the same key with a different request is
rejected with `422 idempotency_key_reused`. Keys expire 24h after first use.

## Development

```
go build ./...
go test ./...
go vet ./...
gofmt -l .
```
