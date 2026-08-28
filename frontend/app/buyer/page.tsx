"use client";

import { useState } from "react";
import { api, rupees } from "@/lib/api";

type TraceEvent = {
  stage: string;
  detail: string;
  candidates_remaining: number | null;
  timestamp?: string;
};

type BuyerResult = {
  status: string;
  intent?: unknown;
  trace?: TraceEvent[];
  best?: Record<string, any>;
  alternatives?: Record<string, any>[];
  quote?: Record<string, any>;
  reason?: string;
};

const SAMPLES = [
  "Find black running shoes under ₹5,000, size 10.",
  "I need a laptop under ₹60,000 deliverable in Delhi within 3 days.",
  "Find white sneakers size 9 available now.",
  "Find a gold mechanical keyboard under ₹500.",
];

export default function BuyerLab() {
  const [query, setQuery] = useState(SAMPLES[0]);
  const [result, setResult] = useState<BuyerResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [order, setOrder] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setBusy(true);
    setError(null);
    setResult(null);
    setOrder(null);
    try {
      setResult(await api<BuyerResult>("/buyer/run", {
        method: "POST",
        body: JSON.stringify({ query }),
      }));
    } catch (e: any) {
      setError(String(e.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  async function createOrder() {
    if (!result?.best) return;
    setBusy(true);
    try {
      // only identifiers cross the wire; the server re-quotes from the DB
      const r = await api<{ order?: { id: string }; error?: string }>("/checkout/order", {
        method: "POST",
        body: JSON.stringify({ items: [{ variant_id: result.best.variant_id }] }),
      });
      if (r.error || !r.order) throw new Error(r.error ?? "order failed");
      const cap = await api<{ payment: { payment_id: string }; signature: string }>(
        `/checkout/mock/capture?order_id=${encodeURIComponent(r.order.id)}`,
        { method: "POST" },
      );
      const verdict = await api("/checkout/verify", {
        method: "POST",
        body: JSON.stringify({
          order_id: r.order.id,
          payment_id: cap.payment.payment_id,
          signature: cap.signature,
        }),
      });
      setOrder({ ...r.order, verdict });
    } catch (e: any) {
      setError(String(e.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">AI Buyer Lab</h1>
        <p className="mt-1 text-sm text-slate-500">
          The buyer parses intent into a Pydantic constraint object, then calls only the six
          deterministic merchant tools. Money facts come from the database — never the model.
        </p>
      </div>

      <div className="card space-y-3">
        <textarea
          className="input min-h-[72px]"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="What is the buyer looking for?"
        />
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn" onClick={run} disabled={busy || !query.trim()}>
            {busy ? "Running…" : "Run buyer"}
          </button>
          {SAMPLES.map((s) => (
            <button key={s} className="btn-secondary !px-3 !py-1.5 text-xs" onClick={() => setQuery(s)}>
              {s.length > 42 ? s.slice(0, 42) + "…" : s}
            </button>
          ))}
        </div>
        {error && <div className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
      </div>

      {result && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="card">
            <div className="label mb-3">Pipeline Trace</div>
            <ol className="space-y-2">
              {(result.trace ?? []).map((t, i) => (
                <li key={i} className="flex items-start gap-3 text-sm">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-[10px] font-semibold text-indigo-700">
                    {i + 1}
                  </span>
                  <div>
                    <div className="font-medium">{t.stage.replaceAll("_", " ")}</div>
                    {t.detail && <div className="text-xs text-slate-500">{t.detail.slice(0, 220)}</div>}
                    {t.candidates_remaining != null && (
                      <div className="text-xs text-slate-400">{t.candidates_remaining} candidates left</div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </div>

          <div className="space-y-4">
            <div className="card">
              <div className="label mb-2">Outcome</div>
              <div
                className={`text-lg font-semibold ${
                  result.status === "match" ? "text-emerald-600" : "text-amber-600"
                }`}
              >
                {result.status}
              </div>
              {result.reason && <p className="mt-1 text-sm text-slate-500">{result.reason}</p>}
              {result.best && (
                <div className="mt-3 rounded-lg bg-slate-50 p-3 text-sm">
                  <div className="font-medium">{result.best.title}</div>
                  <div className="text-xs text-slate-500">
                    {result.best.variant_id} · {result.best.color ?? "—"} · size {result.best.size ?? "—"}
                  </div>
                  <div className="mt-1 font-semibold">{rupees(result.best.price_paise)}</div>
                </div>
              )}
              {result.quote?.verification?.price_verified && (
                <button className="btn mt-3 w-full" onClick={createOrder} disabled={busy}>
                  {error && !busy ? "Retry order" : "Create Razorpay order (Test Mode)"}
                </button>
              )}
              {order && !order.error && (
                <div className="mt-3 rounded-lg border border-slate-200 p-3 text-xs">
                  <div className="font-mono">{order.id}</div>
                  <div className="mt-1 text-slate-500">
                    {rupees(order.amount)} · {(order.verdict as any)?.payment_status} ·
                    signature verified server-side
                  </div>
                </div>
              )}
            </div>

            {!!result.alternatives?.length && (
              <div className="card">
                <div className="label mb-2">Alternatives</div>
                <ul className="space-y-1 text-sm text-slate-600">
                  {result.alternatives.slice(0, 5).map((a: any) => (
                    <li key={a.variant_id} className="flex justify-between">
                      <span>{a.title} · {a.color ?? "—"} · {a.size ?? "—"}</span>
                      <span>{rupees(a.price_paise)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
