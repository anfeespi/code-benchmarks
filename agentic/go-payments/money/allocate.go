package money

import (
	"fmt"
	"sort"
)

// Allocate splits a into len(ratios) parts proportional to ratios, for example
// to pay out one charge to several sub-merchants.
//
// Contract (reconciliation depends on it):
//   - the parts always sum exactly to a;
//   - every part differs from its exact proportional share by less than one
//     minor unit;
//   - leftover minor units go one each to the parts with the largest fractional
//     remainder, ties broken by lower index.
//
// a must be non-negative, ratios non-negative with a positive sum.
func Allocate(a Amount, ratios []int64) ([]Amount, error) {
	if a.Minor < 0 {
		return nil, fmt.Errorf("%w: cannot allocate negative amount %s", ErrInvalidAmount, a)
	}
	var total int64
	for _, r := range ratios {
		if r < 0 {
			return nil, fmt.Errorf("%w: negative ratio %d", ErrInvalidAmount, r)
		}
		total += r
	}
	if total == 0 {
		return nil, fmt.Errorf("%w: ratios must sum to a positive value", ErrInvalidAmount)
	}

	parts := make([]Amount, len(ratios))
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
	return parts, nil
}
