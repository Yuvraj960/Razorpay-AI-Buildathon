"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type EvalReport = {
  catalog_mode?: string;
  dataset: number;
  passed?: number;
  discovery_accuracy: number;
  constraint_precision: number;
  constraint_recall: number;
  policy_accuracy: number;
  variant_accuracy: number;
  hallucination_rate: number;
  checkout_accuracy: number;
  task_success: number;
  readiness?: number;
  failed_cases?: { id: string; type: string; query: string; reason: string }[];
  error?: string;
};

const METRICS: [keyof EvalReport, string][] = [
  ["discovery_accuracy", "Discovery Accuracy"],
  ["constraint_precision", "Constraint Precision"],
  ["constraint_recall", "Constraint Recall"],
  ["policy_accuracy", "Policy Accuracy"],
  ["variant_accuracy", "Variant Accuracy"],
  ["hallucination_rate", "Hallucination Rate (lower is better)"],
  ["checkout_accuracy", "Checkout Accuracy"],
  ["task_success", "Overall Task Success"],
];

export default function EvaluationLab() {
  const [report, setReport] = useState<EvalReport | null>(null);
  const [raw, setRaw] = useState<EvalReport | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadLatest = useCallback(async () => {
    try {
      setReport(await api("/evaluation/latest"));
    } catch {
      /* no run yet */
    }
  }, []);

  useEffect(() => {
    loadLatest();
  }, [loadLatest]);

  async function runEval(catalog: "compiled" | "raw") {
    setBusy(catalog);
    setError(null);
    try {
      const r = await api<EvalReport>("/evaluation/run?catalog=" + catalog, { method: "POST" });
      if (r.error) throw new Error(r.error);
      if (catalog === "compiled") setReport(r);
      else setRaw(r);
    } catch (e: any) {
      setError(String(e.message ?? e));
    } finally {
      setBusy(null);
    }
  }

  const MetricTable = ({ r }: { r: EvalReport | null }) =>
    !r ? null : (
      <div className="space-y-1.5">
        {METRICS.map(([key, label]) => (
          <div key={String(key)} className="flex items-center justify-between text-sm">
            <span className="text-slate-600">{label}</span>
            <span className="font-semibold">{(r as any)[key]}%</span>
          </div>
        ))}
        <div className="mt-2 border-t border-slate-200 pt-2 text-sm font-semibold text-indigo-700">
          Task success: {r.passed ?? "—"}/{r.dataset} · readiness {r.readiness ?? "—"}/100
        </div>
      </div>
    );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Evaluation Lab</h1>
        <p className="mt-1 text-sm text-slate-500">
          50 golden buyer tasks — simple, constrained, policy, impossible, and adversarial —
          scored against the compiled canonical catalog. Run both modes for the before/after story.
        </p>
      </div>

      <div className="flex gap-2">
        <button className="btn" onClick={() => runEval("compiled")} disabled={!!busy}>
          {busy === "compiled" ? "Evaluating…" : "Run eval (compiled)"}
        </button>
        <button className="btn-secondary" onClick={() => runEval("raw")} disabled={!!busy}>
          {busy === "raw" ? "Evaluating…" : "Run eval (raw catalog)"}
        </button>
      </div>

      {error && <div className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card">
          <div className="label mb-3">Compiled Catalog (after)</div>
          {report?.error ? (
            <p className="text-sm text-slate-500">No evaluation yet — run one above.</p>
          ) : (
            <MetricTable r={report} />
          )}
        </div>
        <div className="card">
          <div className="label mb-3">Raw Catalog (before)</div>
          {raw ? <MetricTable r={raw} /> : (
            <p className="text-sm text-slate-500">
              Run the raw eval to see how the same 50 tasks fare against the un-compiled export.
            </p>
          )}
        </div>
      </div>

      {!!report?.failed_cases?.length && (
        <div className="card">
          <div className="label mb-3">Failed Cases (compiled)</div>
          <ul className="space-y-2 text-sm">
            {report.failed_cases.map((f) => (
              <li key={f.id} className="rounded-lg bg-slate-50 p-3">
                <span className="font-mono text-xs text-slate-500">{f.id}</span>{" "}
                <span className="font-medium">{f.query}</span>
                <div className="text-xs text-rose-600">{f.reason}</div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
