# 08 — Razorpay Integration

Owner: Module F. Depends on: `04-agent-tools-and-mcp.md` (`prepare_checkout`). Use **Test Mode** credentials only for development/demo.

## Integration philosophy

Do NOT integrate twenty APIs. The MVP uses exactly four capabilities. The story is:

> **AI-discoverable merchant → AI-selected product → Razorpay transaction**

### Skip unless time remains after core works

Refunds, payouts, settlements, subscriptions, QR codes, invoices, Route, RazorpayX.

## 1. Orders API — `POST /v1/orders`

Server-side order creation (required — the resulting `order_id` is passed into Checkout):

```json
{
  "amount": 499900,
  "currency": "INR",
  "receipt": "agent_order_001",
  "notes": {
    "source": "agent-commerce",
    "product_id": "shoe-001"
  }
}
```

> ⚠️ **Razorpay amounts are currency subunits.** ₹4,999 → `499900`. Regression test mandatory:
> ```text
> ✓ ₹4999  → 499900
> ✓ ₹999   → 99900
> ✓ ₹49.50 → 4950
> ```
> Test name: `test_razorpay_amount_conversion`.

The order amount always comes from the database price of the verified variant — never from LLM output (see `09-security-and-audit.md`).

## 2. Standard Checkout

```text
AI chooses product
  → server creates Razorpay Order
  → order_id
  → frontend opens Razorpay Checkout
  → test payment completes
  → payment_id + signature returned
  → server verifies signature
```

Razorpay requires server-side verification of the returned payment signature. This gives the demonstrable chain:

> **AI selected → Razorpay created → payment completed → server verified.**

## 3. Payment Links — fallback path

```text
POST /v1/payment_links
```

Create/fetch/update/cancel/resend are supported by the API. Secondary transaction path when Standard Checkout isn't available:

```text
prepare_checkout()
  ├─→ Razorpay Order → Standard Checkout
  └─→ Razorpay Payment Link
```

UI shows both buttons: `[ Open Razorpay Checkout ]` / `[ Generate Payment Link ]`.

## 4. Payment verification

After payment attempt:

```text
GET /v1/payments/:id          or
GET /v1/orders/:id/payments   (all payments for an order)
```

Flow: order created → payment attempted → payment ID received → fetch payment → verify status → mark order paid.

## 5. Webhooks

Implement at minimum:

```text
payment.captured
payment.failed
order.paid
```

(Razorpay recommends exactly these for Standard Checkout integrations.)

Signature verification:

- Algorithm: **HMAC-SHA256**
- Header: `X-Razorpay-Signature`
- Verify over the **raw request body**
- Regression test: `test_webhook_signature`

## Python SDK notes

Official Razorpay Python SDK requires **Python 3.12+**. Pin backend accordingly.

## Acceptance criteria

- [ ] Order created server-side with DB-derived amount in subunits (conversion test green)
- [ ] Standard Checkout flow completes in Test Mode; signature verified server-side
- [ ] Payment Link generation works as alternate path
- [ ] Payment status fetched via orders-payments endpoint; order marked paid
- [ ] Three webhook events handled with raw-body HMAC verification + test
- [ ] `RAZORPAY_KEY_SECRET` never leaves the server
