package money_test

import (
	"testing"

	"example.com/gopayments/money"
)

func TestHiddenDecimalAllExponents(t *testing.T) {
	tests := []struct {
		minor int64
		code  string
		want  string
	}{
		{15000, "CLP", "15000"},
		{0, "CLP", "0"},
		{-250, "CLP", "-250"},
		{1500, "JPY", "1500"},
		{7, "JPY", "7"},
		{1234, "KWD", "1.234"},
		{5, "KWD", "0.005"},
		{-1005, "KWD", "-1.005"},
		{1000, "KWD", "1.000"},
		{1050, "USD", "10.50"},
		{5, "EUR", "0.05"},
		{-325, "BRL", "-3.25"},
		{0, "MXN", "0.00"},
	}
	for _, tt := range tests {
		if got := money.MustNew(tt.minor, tt.code).Decimal(); got != tt.want {
			t.Errorf("Decimal(%d %s) = %q, want %q", tt.minor, tt.code, got, tt.want)
		}
	}
}

func TestHiddenParseDecimalRoundTrip(t *testing.T) {
	for _, tc := range []struct{ s, code string }{
		{"15000", "CLP"}, {"1.234", "KWD"}, {"0.005", "KWD"}, {"99", "JPY"}, {"10.50", "USD"}, {"-7.25", "COP"},
	} {
		a, err := money.Parse(tc.s, tc.code)
		if err != nil {
			t.Fatalf("Parse(%q, %s): %v", tc.s, tc.code, err)
		}
		if got := a.Decimal(); got != tc.s {
			t.Errorf("round trip %q %s -> %q", tc.s, tc.code, got)
		}
	}
}

func TestHiddenStringIncludesCode(t *testing.T) {
	if got := money.MustNew(15000, "CLP").String(); got != "15000 CLP" {
		t.Fatalf("String = %q", got)
	}
}
