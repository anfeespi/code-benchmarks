package money

import (
	"errors"
	"testing"
)

func TestParse(t *testing.T) {
	tests := []struct {
		in, code string
		want     int64
		wantErr  error
	}{
		{"10.50", "USD", 1050, nil},
		{"10.5", "USD", 1050, nil},
		{"10", "USD", 1000, nil},
		{"0.01", "eur", 1, nil},
		{"-3.25", "BRL", -325, nil},
		{"10.005", "USD", 0, ErrPrecision},
		{"abc", "USD", 0, ErrInvalidAmount},
		{"1.", "USD", 0, ErrInvalidAmount},
		{"", "USD", 0, ErrInvalidAmount},
		{"1.00", "XXX", 0, ErrUnknownCurrency},
		{"99999999999999999999", "USD", 0, ErrInvalidAmount},
	}
	for _, tt := range tests {
		t.Run(tt.in+"_"+tt.code, func(t *testing.T) {
			got, err := Parse(tt.in, tt.code)
			if !errors.Is(err, tt.wantErr) {
				t.Fatalf("Parse(%q, %q) error = %v, want %v", tt.in, tt.code, err, tt.wantErr)
			}
			if err == nil && got.Minor != tt.want {
				t.Fatalf("Parse(%q, %q) = %d, want %d", tt.in, tt.code, got.Minor, tt.want)
			}
		})
	}
}

func TestDecimalUSD(t *testing.T) {
	tests := []struct {
		minor int64
		want  string
	}{
		{1050, "10.50"},
		{5, "0.05"},
		{0, "0.00"},
		{-325, "-3.25"},
	}
	for _, tt := range tests {
		if got := MustNew(tt.minor, "USD").Decimal(); got != tt.want {
			t.Errorf("Decimal(%d USD) = %q, want %q", tt.minor, got, tt.want)
		}
	}
}

func TestDecimalOtherExponents(t *testing.T) {
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

func TestAddSub(t *testing.T) {
	a, b := MustNew(1000, "USD"), MustNew(250, "USD")
	sum, err := a.Add(b)
	if err != nil || sum.Minor != 1250 {
		t.Fatalf("Add = %v, %v", sum, err)
	}
	diff, err := a.Sub(b)
	if err != nil || diff.Minor != 750 {
		t.Fatalf("Sub = %v, %v", diff, err)
	}
	if _, err := a.Add(MustNew(1, "EUR")); !errors.Is(err, ErrCurrencyMismatch) {
		t.Fatalf("Add across currencies error = %v", err)
	}
}

func TestAllocateEven(t *testing.T) {
	parts, err := Allocate(MustNew(1000, "USD"), []int64{1, 1, 2})
	if err != nil {
		t.Fatal(err)
	}
	want := []int64{250, 250, 500}
	for i, p := range parts {
		if p.Minor != want[i] {
			t.Fatalf("part %d = %d, want %d", i, p.Minor, want[i])
		}
	}
}

func TestAllocateRemainder(t *testing.T) {
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

func TestAllocateErrors(t *testing.T) {
	if _, err := Allocate(MustNew(-1, "USD"), []int64{1}); !errors.Is(err, ErrInvalidAmount) {
		t.Errorf("negative amount: %v", err)
	}
	if _, err := Allocate(MustNew(1, "USD"), []int64{0, 0}); !errors.Is(err, ErrInvalidAmount) {
		t.Errorf("zero ratios: %v", err)
	}
}

func TestFeeSimple(t *testing.T) {
	tests := []struct {
		minor, bps, want int64
	}{
		{10000, 290, 290},
		{0, 290, 0},
		{100000, 0, 0},
		{12345, 10000, 12345},
	}
	for _, tt := range tests {
		got, err := Fee(MustNew(tt.minor, "USD"), tt.bps)
		if err != nil {
			t.Fatal(err)
		}
		if got.Minor != tt.want {
			t.Errorf("Fee(%d, %d bps) = %d, want %d", tt.minor, tt.bps, got.Minor, tt.want)
		}
	}
}

func TestFeeRejectsBadInput(t *testing.T) {
	if _, err := Fee(MustNew(100, "USD"), 10001); !errors.Is(err, ErrInvalidAmount) {
		t.Errorf("bps > 10000: %v", err)
	}
	if _, err := Fee(MustNew(-100, "USD"), 10); !errors.Is(err, ErrInvalidAmount) {
		t.Errorf("negative amount: %v", err)
	}
}
