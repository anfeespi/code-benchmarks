// Package money implements exact amounts in minor units (cents, centavos...).
// Floating point is never used for money.
package money

import (
	"errors"
	"fmt"
	"strings"
)

// ErrUnknownCurrency is returned for ISO codes the service does not support.
var ErrUnknownCurrency = errors.New("unknown currency")

// Currency is an ISO 4217 currency with its number of minor-unit digits.
type Currency struct {
	Code     string
	Exponent int
}

var currencies = map[string]Currency{
	"USD": {Code: "USD", Exponent: 2},
	"EUR": {Code: "EUR", Exponent: 2},
	"BRL": {Code: "BRL", Exponent: 2},
	"MXN": {Code: "MXN", Exponent: 2},
	"COP": {Code: "COP", Exponent: 2},
	"CLP": {Code: "CLP", Exponent: 0},
	"JPY": {Code: "JPY", Exponent: 0},
	"KWD": {Code: "KWD", Exponent: 3},
}

// LookupCurrency resolves an ISO code (case-insensitive).
func LookupCurrency(code string) (Currency, error) {
	c, ok := currencies[strings.ToUpper(strings.TrimSpace(code))]
	if !ok {
		return Currency{}, fmt.Errorf("%w: %q", ErrUnknownCurrency, code)
	}
	return c, nil
}

// MustCurrency is LookupCurrency for constants in tests and wiring; it panics
// on unknown codes.
func MustCurrency(code string) Currency {
	c, err := LookupCurrency(code)
	if err != nil {
		panic(err)
	}
	return c
}

// Factor is 10^Exponent, the number of minor units in one major unit.
func (c Currency) Factor() int64 {
	f := int64(1)
	for i := 0; i < c.Exponent; i++ {
		f *= 10
	}
	return f
}
