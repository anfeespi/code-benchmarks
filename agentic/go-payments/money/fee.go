package money

import "fmt"

// Fee returns bps basis points (1 bps = 0.01%) of a.
//
// Finance policy: the fee is computed on the exact value and rounded
// half-to-even (banker's rounding) to the currency's minor unit.
func Fee(a Amount, bps int64) (Amount, error) {
	if a.Minor < 0 {
		return Amount{}, fmt.Errorf("%w: fee on negative amount %s", ErrInvalidAmount, a)
	}
	if bps < 0 || bps > 10000 {
		return Amount{}, fmt.Errorf("%w: bps %d out of range [0, 10000]", ErrInvalidAmount, bps)
	}
	// Split a into a multiple of 10000 and a remainder so a*bps never overflows.
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
	return Amount{Minor: fee, Currency: a.Currency}, nil
}
