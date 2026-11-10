package money

import (
	"errors"
	"fmt"
	"math"
	"strconv"
	"strings"
)

var (
	// ErrInvalidAmount is returned for malformed or out-of-range amounts.
	ErrInvalidAmount = errors.New("invalid amount")
	// ErrPrecision is returned when an amount has more decimals than its currency allows.
	ErrPrecision = errors.New("too many decimal places for currency")
	// ErrCurrencyMismatch is returned when combining amounts in different currencies.
	ErrCurrencyMismatch = errors.New("currency mismatch")
)

// Amount is an exact quantity of money in minor units.
type Amount struct {
	Minor    int64
	Currency Currency
}

// New builds an amount from minor units.
func New(minor int64, code string) (Amount, error) {
	c, err := LookupCurrency(code)
	if err != nil {
		return Amount{}, err
	}
	return Amount{Minor: minor, Currency: c}, nil
}

// MustNew is New for tests and constants; it panics on unknown currencies.
func MustNew(minor int64, code string) Amount {
	a, err := New(minor, code)
	if err != nil {
		panic(err)
	}
	return a
}

// Parse reads a decimal string in major units ("10.50") for the given currency.
// More fractional digits than the currency exponent is an error, never rounded.
func Parse(s, code string) (Amount, error) {
	cur, err := LookupCurrency(code)
	if err != nil {
		return Amount{}, err
	}
	s = strings.TrimSpace(s)
	neg := strings.HasPrefix(s, "-")
	s = strings.TrimPrefix(s, "-")
	intPart, frac, hasDot := strings.Cut(s, ".")
	if intPart == "" || (hasDot && frac == "") || !digits(intPart) || !digits(frac) {
		return Amount{}, fmt.Errorf("%w: %q", ErrInvalidAmount, s)
	}
	if len(frac) > cur.Exponent {
		return Amount{}, fmt.Errorf("%w: %s allows %d, got %q", ErrPrecision, cur.Code, cur.Exponent, s)
	}
	major, err := strconv.ParseInt(intPart, 10, 64)
	if err != nil || major > math.MaxInt64/cur.Factor() {
		return Amount{}, fmt.Errorf("%w: %q out of range", ErrInvalidAmount, s)
	}
	minor := major * cur.Factor()
	if frac != "" {
		frac += strings.Repeat("0", cur.Exponent-len(frac))
		f, err := strconv.ParseInt(frac, 10, 64)
		if err != nil {
			return Amount{}, fmt.Errorf("%w: %q", ErrInvalidAmount, s)
		}
		minor += f
	}
	if neg {
		minor = -minor
	}
	return Amount{Minor: minor, Currency: cur}, nil
}

func digits(s string) bool {
	for _, r := range s {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}

// Decimal renders the amount in major units with exactly Exponent decimals.
func (a Amount) Decimal() string {
	m := a.Minor
	sign := ""
	if m < 0 {
		sign = "-"
		m = -m
	}
	if a.Currency.Exponent == 0 {
		return sign + strconv.FormatInt(m, 10)
	}
	f := a.Currency.Factor()
	return fmt.Sprintf("%s%d.%0*d", sign, m/f, a.Currency.Exponent, m%f)
}

// String renders "10.50 USD".
func (a Amount) String() string { return a.Decimal() + " " + a.Currency.Code }

// Add returns a+b; both must share a currency.
func (a Amount) Add(b Amount) (Amount, error) {
	if a.Currency != b.Currency {
		return Amount{}, fmt.Errorf("%w: %s + %s", ErrCurrencyMismatch, a.Currency.Code, b.Currency.Code)
	}
	return Amount{Minor: a.Minor + b.Minor, Currency: a.Currency}, nil
}

// Sub returns a-b; both must share a currency.
func (a Amount) Sub(b Amount) (Amount, error) {
	if a.Currency != b.Currency {
		return Amount{}, fmt.Errorf("%w: %s - %s", ErrCurrencyMismatch, a.Currency.Code, b.Currency.Code)
	}
	return Amount{Minor: a.Minor - b.Minor, Currency: a.Currency}, nil
}

// IsPositive reports whether the amount is strictly greater than zero.
func (a Amount) IsPositive() bool { return a.Minor > 0 }
