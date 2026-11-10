package money_test

import (
	"fmt"
	"math/big"
	"math/rand"
	"testing"

	"example.com/gopayments/money"
)

func h18Exact(minor, bps int64) int64 {
	r := new(big.Rat).SetFrac(new(big.Int).Mul(big.NewInt(minor), big.NewInt(bps)), big.NewInt(10000))
	fl := new(big.Int).Quo(r.Num(), r.Denom())
	c := new(big.Rat).Sub(r, new(big.Rat).SetInt(fl)).Cmp(big.NewRat(1, 2))
	f := fl.Int64()
	if c > 0 || (c == 0 && f%2 != 0) {
		f++
	}
	return f
}

func TestHiddenFeeExamples(t *testing.T) {
	tests := []struct {
		minor, bps, want int64
	}{
		{1005, 290, 29},   // 29.145 -> 29
		{1000, 290, 29},   // exact
		{1050, 290, 30},   // 30.45 -> 30
		{15, 1000, 2},     // 1.5 -> 2 (half to even)
		{25, 1000, 2},     // 2.5 -> 2 (half to even)
		{35, 1000, 4},     // 3.5 -> 4
		{45, 1000, 4},     // 4.5 -> 4
		{1, 5000, 0},      // 0.5 -> 0
		{3, 5000, 2},      // 1.5 -> 2
		{1500, 290, 44},   // 43.5 -> 44
		{2500, 290, 72},   // 72.5 -> 72
		{1, 1, 0},
		{9999, 1, 1},      // 0.9999 -> 1
		{0, 290, 0},
		{12345, 10000, 12345},
		{36028797018963982, 290, 1044835113549955},
		{36028797018963996, 349, 1257405015961843},
		{36028797018964997, 15, 54043195528447},
		{36028797018963989, 2500, 9007199254740997},
		{9223372036854775807, 10000, 9223372036854775807},
		{9223372036854775807, 290, 267477789068788498},
	}
	for _, tt := range tests {
		t.Run(fmt.Sprintf("%d@%d", tt.minor, tt.bps), func(t *testing.T) {
			got, err := money.Fee(money.MustNew(tt.minor, "USD"), tt.bps)
			if err != nil {
				t.Fatal(err)
			}
			if got.Minor != tt.want {
				t.Fatalf("Fee(%d, %d bps) = %d, want %d", tt.minor, tt.bps, got.Minor, tt.want)
			}
		})
	}
}

func TestHiddenFeeMatchesExactArithmetic(t *testing.T) {
	rng := rand.New(rand.NewSource(7))
	for i := 0; i < 20000; i++ {
		minor := rng.Int63n(10_000_000)
		switch i % 4 {
		case 1:
			minor = rng.Int63()
		case 2:
			minor = rng.Int63n(1<<40) * 10000 + 5000 // exact halves for odd bps multiples
		}
		bps := rng.Int63n(10001)
		if i%5 == 0 {
			bps = 290
		}
		got, err := money.Fee(money.MustNew(minor, "EUR"), bps)
		if err != nil {
			t.Fatal(err)
		}
		if want := h18Exact(minor, bps); got.Minor != want || got.Currency.Code != "EUR" {
			t.Fatalf("Fee(%d, %d bps) = %d %s, want %d", minor, bps, got.Minor, got.Currency.Code, want)
		}
	}
}

func TestHiddenFeeValidation(t *testing.T) {
	for _, tc := range []struct{ minor, bps int64 }{{-1, 10}, {100, -1}, {100, 10001}} {
		if _, err := money.Fee(money.MustNew(tc.minor, "USD"), tc.bps); err == nil {
			t.Errorf("Fee(%d, %d) should fail", tc.minor, tc.bps)
		}
	}
}
