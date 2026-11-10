package payment_test

import (
	"context"
	"errors"
	"go/ast"
	"go/parser"
	"go/token"
	"strings"
	"sync"
	"testing"
	"time"

	"example.com/gopayments/clock"
	"example.com/gopayments/money"
	"example.com/gopayments/payment"
	"example.com/gopayments/store"
)

var h12All = []payment.Status{payment.StatusCreated, payment.StatusPending, payment.StatusSucceeded, payment.StatusDeclined, payment.StatusRefunded}

func TestHiddenCanTransitionMatrix(t *testing.T) {
	allowed := map[[2]payment.Status]bool{
		{payment.StatusCreated, payment.StatusPending}:    true,
		{payment.StatusCreated, payment.StatusDeclined}:   true,
		{payment.StatusPending, payment.StatusSucceeded}:  true,
		{payment.StatusPending, payment.StatusDeclined}:   true,
		{payment.StatusSucceeded, payment.StatusRefunded}: true,
	}
	for _, from := range h12All {
		for _, to := range h12All {
			if got, want := payment.CanTransition(from, to), allowed[[2]payment.Status{from, to}]; got != want {
				t.Errorf("CanTransition(%s, %s) = %v, want %v", from, to, got, want)
			}
		}
	}
	if payment.CanTransition("BOGUS", payment.StatusPending) || payment.CanTransition(payment.StatusCreated, "BOGUS") {
		t.Error("unknown statuses must not transition")
	}
}

func TestHiddenServiceHasNoStatusSwitch(t *testing.T) {
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, "service.go", nil, 0)
	if err != nil {
		t.Fatal(err)
	}
	usesCanTransition := false
	ast.Inspect(f, func(n ast.Node) bool {
		switch n := n.(type) {
		case *ast.SwitchStmt:
			if sel, ok := n.Tag.(*ast.SelectorExpr); ok && sel.Sel.Name == "Status" {
				t.Errorf("%s: switch on .Status remains in service.go", fset.Position(n.Pos()))
			}
		case *ast.BinaryExpr:
			if n.Op == token.EQL || n.Op == token.NEQ {
				for _, side := range []ast.Expr{n.X, n.Y} {
					if sel, ok := side.(*ast.SelectorExpr); ok && sel.Sel.Name == "Status" {
						other := n.Y
						if side == n.Y {
							other = n.X
						}
						if id, ok := other.(*ast.Ident); ok && strings.HasPrefix(id.Name, "Status") {
							t.Errorf("%s: comparison of .Status with %s remains in service.go", fset.Position(n.Pos()), id.Name)
						}
					}
				}
			}
		case *ast.CallExpr:
			if id, ok := n.Fun.(*ast.Ident); ok && id.Name == "CanTransition" {
				usesCanTransition = true
			}
		}
		return true
	})
	if !usesCanTransition {
		t.Error("service.go does not call CanTransition")
	}
}

type h12Events struct {
	mu    sync.Mutex
	types []string
}

func (e *h12Events) Publish(_ context.Context, ev payment.Event) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.types = append(e.types, ev.Type)
	return nil
}

func TestHiddenBehaviourUnchanged(t *testing.T) {
	ctx := context.Background()
	ev := &h12Events{}
	s := payment.NewService(store.NewMemory(), clock.NewFake(time.Unix(1_800_000_000, 0)), payment.NewSeqIDs(), ev, payment.Config{FeeBps: 290})
	newP := func() string {
		p, err := s.Create(ctx, payment.CreateInput{MerchantID: "m", Amount: money.MustNew(1000, "USD")})
		if err != nil {
			t.Fatal(err)
		}
		return p.ID
	}
	a := newP()
	if _, err := s.Capture(ctx, a); !errors.Is(err, payment.ErrInvalidTransition) {
		t.Fatalf("capture created: %v", err)
	}
	if _, _, err := s.Refund(ctx, a, money.MustNew(1, "USD")); !errors.Is(err, payment.ErrInvalidTransition) {
		t.Fatalf("refund created: %v", err)
	}
	if p, err := s.Authorize(ctx, a); err != nil || p.Status != payment.StatusPending || p.Version != 2 {
		t.Fatalf("authorize: %+v %v", p, err)
	}
	if _, err := s.Authorize(ctx, a); !errors.Is(err, payment.ErrInvalidTransition) {
		t.Fatalf("authorize twice: %v", err)
	}
	if p, err := s.Capture(ctx, a); err != nil || p.Status != payment.StatusSucceeded {
		t.Fatalf("capture: %+v %v", p, err)
	}
	if _, err := s.Decline(ctx, a, "late"); !errors.Is(err, payment.ErrInvalidTransition) {
		t.Fatalf("decline succeeded: %v", err)
	}
	p, _, err := s.Refund(ctx, a, money.MustNew(400, "USD"))
	if err != nil || p.Status != payment.StatusSucceeded || p.Refunded != 400 {
		t.Fatalf("partial refund: %+v %v", p, err)
	}
	if _, _, err := s.Refund(ctx, a, money.MustNew(601, "USD")); !errors.Is(err, payment.ErrRefundExceedsRemaining) {
		t.Fatalf("over refund: %v", err)
	}
	if _, _, err := s.Refund(ctx, a, money.MustNew(5, "EUR")); !errors.Is(err, money.ErrCurrencyMismatch) {
		t.Fatalf("currency mismatch: %v", err)
	}
	p, _, err = s.Refund(ctx, a, money.MustNew(600, "USD"))
	if err != nil || p.Status != payment.StatusRefunded {
		t.Fatalf("full refund: %+v %v", p, err)
	}
	if _, _, err := s.Refund(ctx, a, money.MustNew(1, "USD")); !errors.Is(err, payment.ErrInvalidTransition) {
		t.Fatalf("refund refunded: %v", err)
	}

	b := newP()
	if p, err := s.Decline(ctx, b, "nsf"); err != nil || p.Status != payment.StatusDeclined || p.DeclineReason != "nsf" {
		t.Fatalf("decline created: %+v %v", p, err)
	}
	c := newP()
	_, _ = s.Authorize(ctx, c)
	if p, err := s.Decline(ctx, c, "risk"); err != nil || p.Status != payment.StatusDeclined {
		t.Fatalf("decline pending: %+v %v", p, err)
	}
	for _, op := range []func() error{
		func() error { _, err := s.Authorize(ctx, b); return err },
		func() error { _, err := s.Capture(ctx, b); return err },
		func() error { _, err := s.Decline(ctx, b, "x"); return err },
	} {
		if err := op(); !errors.Is(err, payment.ErrInvalidTransition) {
			t.Fatalf("op on declined: %v", err)
		}
	}
	if _, err := s.Authorize(ctx, "pay_nope"); !errors.Is(err, payment.ErrNotFound) {
		t.Fatalf("unknown: %v", err)
	}
	want := "payment.created,payment.pending,payment.succeeded,payment.partially_refunded,payment.refunded," +
		"payment.created,payment.declined,payment.created,payment.pending,payment.declined"
	if got := strings.Join(ev.types, ","); got != want {
		t.Fatalf("events:\n got %s\nwant %s", got, want)
	}
}
