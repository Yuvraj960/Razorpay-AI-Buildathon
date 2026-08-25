# 04 — Agent-Facing Tools & MCP Server

Owner: Module B. Depends on: `03-canonical-schema.md`.

## Design stance

Expose a **small, deterministic tool layer** — six tools. These are the merchant's executable commerce interface. Every tool queries the database; none consults an LLM.

## The six tools

### 1. search_products(query, filters)

```json
{
  "query": "running shoes",
  "filters": { "max_price": 5000, "color": "black", "size": "10" }
}
```

Structured filtering first (price/stock/category/color/size/brand), keyword second.

### 2. get_product(product_id)

Returns the full canonical product.

### 3. check_availability(product_id, variant_id)

**Queries the database, not the LLM.**

### 4. get_shipping(product_id, pincode)

Delivery estimate + fee for a destination.

### 5. get_return_policy(product_id)

Returns the policy object.

### 6. prepare_checkout(cart)

Must NOT charge money. Returns a verified quote:

```json
{
  "items": [],
  "subtotal": 4999,
  "shipping": 0,
  "tax": 0,
  "total": 4999,
  "currency": "INR",
  "verification": {
    "price_verified": true,
    "inventory_verified": true
  }
}
```

Only after `prepare_checkout` succeeds does the transaction layer create a Razorpay order (see `08-razorpay-integration.md`).

## MCP server

Yes, implement MCP — but keep it small. Mirror Razorpay's own architectural idea (they expose an official MCP server connecting Claude, ChatGPT, Cursor, VS Code, Windsurf, Replit, Gemini CLI) applied to the **merchant catalog**:

```text
mcp-server/
├── server.py
└── tools/
    ├── search_products
    ├── get_product
    ├── check_inventory
    ├── get_shipping
    ├── get_returns
    └── prepare_checkout
```

The same six tools must be available both as REST endpoints (`backend/app/api/`) and through MCP — one implementation, two transports.

## Why MCP earns its place: the demo trace

```text
AI BUYER: "I need black running shoes under ₹5,000, size 10."
   ↓ search_products()          → 3 products
   ↓ check_inventory()          → 2 valid variants
   ↓ get_shipping()             → 1 meets the 4-day requirement
   ↓ prepare_checkout()         → verified quote
   ↓ Razorpay Order
```

This trace is substantially more impressive than "a chatbot calling a database" — it shows a real tool-using agent against a real interface.

## Acceptance criteria

- [ ] Six REST endpoints + equivalent MCP tools share one service layer
- [ ] `check_availability` and all pricing come from DB reads (grep-able proof: no LLM call in the tool path)
- [ ] `prepare_checkout` never creates a charge; returns verification block
- [ ] Tool schemas documented and typed (Pydantic request/response models)
