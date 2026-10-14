package money_test

import (
	"fmt"
	"math/big"
	"math/rand"
	"testing"

	"example.com/gopayments/money"
)

func TestHiddenAllocateExamples(t *testing.T) {
	tests := []struct {
		amount int64
		ratios []int64
		want   []int64
	}{
		{10000, []int64{1, 1, 1}, []int64{3334, 3333, 3333}},
		{100, []int64{1, 1, 1}, []int64{34, 33, 33}},
		{10, []int64{1, 1, 1, 1, 1, 1, 1}, []int64{2, 2, 2, 1, 1, 1, 1}},
		{5, []int64{3, 7}, []int64{2, 3}},
		{100, []int64{1, 1}, []int64{50, 50}},
		{101, []int64{1, 1}, []int64{51, 50}},
		{1, []int64{1, 1, 1}, []int64{1, 0, 0}},
		{100, []int64{0, 1, 0, 1}, []int64{0, 50, 0, 50}},
		{1000, []int64{1, 2, 3}, []int64{167, 333, 500}},
		{11, []int64{10, 70, 20}, []int64{1, 8, 2}},
		{7, []int64{1, 1, 1, 6}, []int64{1, 1, 1, 4}},
		{0, []int64{1, 2}, []int64{0, 0}},
		{9_007_199_254_740_993, []int64{1, 1}, []int64{4_503_599_627_370_497, 4_503_599_627_370_496}},
		{36_028_797_018_963_971, []int64{1, 2}, []int64{12_009_599_006_321_324, 24_019_198_012_642_647}},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%d/%v", tt.amount, tt.ratios), func(t *testing.T) {
			parts, err := money.Allocate(money.MustNew(tt.amount, "USD"), tt.ratios)
			if err != nil {
				t.Fatal(err)
			}
			got := make([]int64, len(parts))
			for i, p := range parts {
				got[i] = p.Minor
				if p.Currency.Code != "USD" {
					t.Fatalf("part %d currency %s", i, p.Currency.Code)
				}
			}
			if fmt.Sprint(got) != fmt.Sprint(tt.want) {
				t.Fatalf("Allocate = %v, want %v", got, tt.want)
			}
		})
	}
}

// TestHiddenAllocateContract checks the documented contract on random inputs
// with exact rational arithmetic.
func TestHiddenAllocateContract(t *testing.T) {
	rng := rand.New(rand.NewSource(42))
	for i := 0; i < 3000; i++ {
		n := 1 + rng.Intn(9)
		ratios := make([]int64, n)
		var total int64
		for j := range ratios {
			ratios[j] = int64(rng.Intn(1000))
			total += ratios[j]
		}
		if total == 0 {
			ratios[0], total = 1, 1
		}
		amount := rng.Int63n(1_000_000_000)
		if i%10 == 0 {
			amount = rng.Int63n(1 << 52)
		}
		parts, err := money.Allocate(money.MustNew(amount, "BRL"), ratios)
		if err != nil {
			t.Fatal(err)
		}
		var sum int64
		type rem struct {
			idx int
			r   *big.Rat
		}
		var extra []int
		var rems []rem
		for j, p := range parts {
			sum += p.Minor
			exact := new(big.Rat).SetFrac(new(big.Int).Mul(big.NewInt(amount), big.NewInt(ratios[j])), big.NewInt(total))
			diff := new(big.Rat).Sub(new(big.Rat).SetInt64(p.Minor), exact)
			if diff.Cmp(big.NewRat(-1, 1)) <= 0 || diff.Cmp(big.NewRat(1, 1)) >= 0 {
				t.Fatalf("Allocate(%d, %v)[%d] = %d, exact share %s", amount, ratios, j, p.Minor, exact.FloatString(3))
			}
			floor := new(big.Int).Quo(exact.Num(), exact.Denom())
			frac := new(big.Rat).Sub(exact, new(big.Rat).SetInt(floor))
			rems = append(rems, rem{j, frac})
			if p.Minor > floor.Int64() {
				extra = append(extra, j)
			}
		}
		if sum != amount {
			t.Fatalf("Allocate(%d, %v) sums to %d", amount, ratios, sum)
		}
		// every part that got an extra unit must have a fractional remainder >= every
		// part that did not (ties broken by lower index).
		got := map[int]bool{}
		for _, j := range extra {
			got[j] = true
		}
		for _, a := range rems {
			for _, b := range rems {
				if got[a.idx] && !got[b.idx] {
					c := a.r.Cmp(b.r)
					if c < 0 || (c == 0 && a.idx > b.idx) {
						t.Fatalf("Allocate(%d, %v): part %d got the extra unit before part %d", amount, ratios, a.idx, b.idx)
					}
				}
			}
		}
	}
}
