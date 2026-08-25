# 00 — Vision & Positioning

## What we are building

A **merchant-side Agent Commerce Readiness & Buyer Simulation platform**, codename **Agent Commerce Readiness Lab**.

Core proposition:

> **Take a normal merchant catalog that was designed for humans, transform it into machine-readable commerce infrastructure, expose it to an AI buyer, and prove — with automated tests — that the AI can discover, understand, trust, and transact with the merchant correctly.**

## Explicitly NOT this project

Do not drift toward any of these. Each was considered and rejected as too common, too narrow, or already owned by someone else:

- ❌ Generic shopping chatbot
- ❌ Product recommendation engine
- ❌ ChatGPT clone
- ❌ AI product-description generator
- ❌ Full UCP specification implementation (build a *UCP-inspired abstraction* instead; never claim "fully UCP compliant")
- ❌ Razorpay payment chatbot (Razorpay already has Agentic Payments, Agent Studio, MCP server)
- ❌ Huge multi-agent swarm
- ❌ Vector database "just to say RAG"
- ❌ "Paste URL → get AI readiness score" (products named AgentReady already exist on Shopify/WooCommerce app stores doing exactly this)

## Why the differentiation is **Proof**

Razorpay already ships Agentic Payments, payments inside LLMs, Razorpay for ChatGPT/Claude, an Agentic Stack, an official MCP server (35+ tools), and Agent Studio. Shopify's Catalog + Agentic Storefronts distribute structured catalogs into AI channels. Stripe launched an Agentic Commerce Suite. Google/Shopify back the Universal Commerce Protocol (UCP).

All of them give merchants *infrastructure*. Nobody gives merchants **behavioral evidence** that an AI buyer can actually succeed against their data:

> "Here are 50 buyer tasks. Here are the 11 that failed. Here is exactly why. Here is the fix. Now rerun the test."

That sentence is the product. Static scoring alone ("your catalog has good data") is commodity; simulation ("an AI buyer actually succeeded") is the moat.

## The gap we occupy: Merchant Readiness

Millions of merchants will not have BigBasket-grade catalogs. They will have Excel sheets, inconsistent SKUs, missing attributes, vague descriptions, inconsistent prices, incomplete inventory, unclear delivery rules, undocumented returns, missing variants, and no machine-readable APIs. Once Razorpay can transact through AI, the remaining problem is whether the merchant's data survives contact with an AI buyer. We solve that layer.

## The four words

**Discover → Understand → Decide → Transact.** A merchant counts as Agent Ready only if an AI buyer succeeds at all four. Detailed definitions in `01-product-spec-mvp.md`.

## Where we sit relative to Razorpay

Do not compete with Razorpay's transaction infrastructure. Sit above it:

```text
                YOUR PROJECT
Merchant Catalog
      ↓
Agent Readiness Compiler
      ↓
Buyer Simulation
      ↓
Readiness Evaluation
      ↓
Razorpay Transaction Layer
```

Positioning sentence for judges: **"They built a system that takes messy merchant data, makes it agent-readable, tests it using simulated buyers, and then proves an actual Razorpay transaction."**

If an evaluator can repeat that sentence after the demo, the project succeeded.

## Reference material to keep open while building

- Razorpay Agentic Payments, Agent Studio, MCP Server docs
- Razorpay Orders API, Standard Checkout, Payment Links API, Webhooks docs
- Google Universal Commerce Protocol (UCP) + Product structured-data docs (`ProductGroup`/`hasVariant`)
- Shopify Agentic Storefronts help docs
- Stripe Agentic Commerce use-case page
