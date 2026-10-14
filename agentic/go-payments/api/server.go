// Package api exposes the payment service over HTTP/JSON.
package api

import (
	"net/http"

	"example.com/gopayments/idempotency"
	"example.com/gopayments/payment"
	"example.com/gopayments/webhook"
)

// Server is the HTTP entry point of the service.
type Server struct {
	svc   *payment.Service
	idem  idempotency.Store
	hooks *webhook.Dispatcher
	mux   *http.ServeMux
}

// NewServer wires the HTTP routes.
func NewServer(svc *payment.Service, idem idempotency.Store, hooks *webhook.Dispatcher) *Server {
	s := &Server{svc: svc, idem: idem, hooks: hooks, mux: http.NewServeMux()}
	s.routes()
	return s
}

func (s *Server) routes() {
	s.mux.HandleFunc("POST /payments", s.createPayment)
	s.mux.HandleFunc("GET /payments/{id}", s.getPayment)
	s.mux.HandleFunc("POST /payments/{id}/authorize", s.authorizePayment)
	s.mux.HandleFunc("POST /payments/{id}/capture", s.capturePayment)
	s.mux.HandleFunc("POST /payments/{id}/decline", s.declinePayment)
	s.mux.HandleFunc("POST /payments/{id}/refunds", s.refundPayment)
	s.mux.HandleFunc("GET /merchants/{merchantID}/payments", s.listPayments)
	s.mux.HandleFunc("GET /webhooks/dead-letters", s.listDeadLetters)
}

// ServeHTTP implements http.Handler.
func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.mux.ServeHTTP(w, r)
}
