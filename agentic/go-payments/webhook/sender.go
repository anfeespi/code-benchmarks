package webhook

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net/http"
)

// Delivery is one HTTP attempt of an event to a merchant endpoint.
type Delivery struct {
	EventID string
	URL     string
	Body    []byte
	Headers map[string]string
	Attempt int
}

// Sender performs one delivery attempt. A transport error is returned as err;
// any HTTP response (including 4xx/5xx) is returned as status with err == nil.
type Sender interface {
	Send(ctx context.Context, d Delivery) (status int, err error)
}

// HTTPSender delivers over HTTP.
type HTTPSender struct {
	Client *http.Client
}

// Send implements Sender.
func (s HTTPSender) Send(ctx context.Context, d Delivery) (int, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, d.URL, bytes.NewReader(d.Body))
	if err != nil {
		return 0, fmt.Errorf("build request for %s: %w", d.URL, err)
	}
	for k, v := range d.Headers {
		req.Header.Set(k, v)
	}
	client := s.Client
	if client == nil {
		client = http.DefaultClient
	}
	resp, err := client.Do(req)
	if err != nil {
		return 0, fmt.Errorf("post %s: %w", d.URL, err)
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, resp.Body)
	return resp.StatusCode, nil
}
