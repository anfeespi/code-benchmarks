package webhook

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"time"
)

// SignatureHeader carries "t=<unix seconds>,v1=<hex hmac-sha256>".
const SignatureHeader = "Webhook-Signature"

var (
	// ErrBadSignature is returned when a signature header is malformed or does not match.
	ErrBadSignature = errors.New("invalid webhook signature")
	// ErrStaleSignature is returned when the signed timestamp is outside the tolerance.
	ErrStaleSignature = errors.New("stale webhook signature")
)

// Sign returns the signature header value for body sent at ts. The MAC
// covers "<ts>.<body>" so a captured payload cannot be replayed with a new
// timestamp.
func Sign(secret string, ts int64, body []byte) string {
	return fmt.Sprintf("t=%d,v1=%s", ts, hex.EncodeToString(mac(secret, ts, body)))
}

// Verify checks header against body. now and tolerance bound the accepted
// timestamp skew in both directions.
func Verify(secret, header string, body []byte, now time.Time, tolerance time.Duration) error {
	var ts int64
	var sig []byte
	for _, part := range strings.Split(header, ",") {
		k, v, ok := strings.Cut(strings.TrimSpace(part), "=")
		if !ok {
			return fmt.Errorf("%w: malformed part %q", ErrBadSignature, part)
		}
		switch k {
		case "t":
			n, err := strconv.ParseInt(v, 10, 64)
			if err != nil {
				return fmt.Errorf("%w: bad timestamp: %v", ErrBadSignature, err)
			}
			ts = n
		case "v1":
			b, err := hex.DecodeString(v)
			if err != nil {
				return fmt.Errorf("%w: bad v1: %v", ErrBadSignature, err)
			}
			sig = b
		}
	}
	if ts == 0 || sig == nil {
		return fmt.Errorf("%w: missing t or v1", ErrBadSignature)
	}
	skew := now.Sub(time.Unix(ts, 0))
	if skew > tolerance || skew < -tolerance {
		return fmt.Errorf("%w: skew %s exceeds %s", ErrStaleSignature, skew, tolerance)
	}
	if !hmac.Equal(sig, mac(secret, ts, body)) {
		return fmt.Errorf("%w: mismatch", ErrBadSignature)
	}
	return nil
}

func mac(secret string, ts int64, body []byte) []byte {
	h := hmac.New(sha256.New, []byte(secret))
	h.Write([]byte(strconv.FormatInt(ts, 10)))
	h.Write([]byte("."))
	h.Write(body)
	return h.Sum(nil)
}
