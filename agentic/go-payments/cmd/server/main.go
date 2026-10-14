// Command server runs the payments API on :8080 with in-memory storage.
package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"time"

	"example.com/gopayments/api"
	"example.com/gopayments/clock"
	"example.com/gopayments/idempotency"
	"example.com/gopayments/payment"
	"example.com/gopayments/store"
	"example.com/gopayments/webhook"
)

func main() {
	clk := clock.Real{}
	endpoints := webhook.StaticEndpoints{}
	if url := os.Getenv("DEMO_WEBHOOK_URL"); url != "" {
		endpoints["m_demo"] = webhook.Endpoint{URL: url, Secret: os.Getenv("DEMO_WEBHOOK_SECRET")}
	}
	hooks := webhook.NewDispatcher(webhook.HTTPSender{Client: &http.Client{Timeout: 10 * time.Second}}, endpoints, clk, webhook.DefaultPolicy())
	svc := payment.NewService(store.NewMemory(), clk, payment.NewSeqIDs(), hooks, payment.Config{FeeBps: 290})
	srv := api.NewServer(svc, idempotency.NewMemory(clk, 24*time.Hour), hooks)

	go func() {
		for range time.Tick(time.Second) {
			if err := hooks.Flush(context.Background()); err != nil {
				log.Printf("webhooks: %v", err)
			}
		}
	}()

	log.Println("listening on :8080")
	log.Fatal(http.ListenAndServe(":8080", srv))
}
