"use client";

import { useEffect, useState } from "react";
import { api, rupees } from "@/lib/api";

type Readiness = {
  total: number;
  band: string;
  dimensions?: { name: string; weight: number; score: number; weighted: number }[];
};

type Product = {
  product_id: string;
  title: string;
  brand: string | null;
  category: string | null;
  price_paise: number;
  availability: string;
  problems: string[];
};

export default function Dashboard() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [stats, setStats] = useState<{ products: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [r, p] = await Promise.all([
          api<Readiness>("/catalog/readiness"),
          api<{ products: Product[]; total: number }>("/catalog/products?limit=8"),
        ]);
        setReadiness(r);
        setProducts(p.products ?? []);
        setStats({ products: p.total ?? (p.products?.length ?? 0) });
      } catch (e: any) {
        setError(String(e.message ?? e));
      }
    })();
  }, []);

  const bandColor =
    (readiness?.total ?? 0) >= 90
      ? "text-emerald-600"
      : (readiness?.total ?? 0) >= 75
      ? "text-amber-600"
      : "text-rose-600";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Catalog Health</h1>
        <p className="mt-1 text-sm text-slate-500">
          The compiler turns the messy merchant export into machine-readable commerce —
          readiness is scored on a weighted 8-dimension rubric.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          Backend unreachable: {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="card">
          <div className="label">Agent-Readiness Score</div>
          <div className={`metric ${bandColor}`}>{readiness?.total ?? "—"}/100</div>
          <div className="mt-1 text-xs text-slate-500">{readiness?.band ?? ""}</div>
        </div>
        <div className="card">
          <div className="label">Compiled Products</div>
          <div className="metric">{stats?.products ?? "—"}</div>
          <div className="mt-1 text-xs text-slate-500">from raw merchant export</div>
        </div>
        <div className="card">
          <div className="label">Machine-Readable Artifacts</div>
          <div className="metric">3</div>
          <div className="mt-1 text-xs text-slate-500">agent-feed.json · product-schema.jsonld · tools API</div>
        </div>
      </div>

      {readiness?.dimensions && (
        <div className="card">
          <div className="label mb-3">Rubric Dimensions</div>
          <div className="space-y-2">
            {readiness.dimensions.map((d) => (
              <div key={d.name} className="flex items-center gap-3">
                <div className="w-56 shrink-0 text-sm text-slate-700">{d.name}</div>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-indigo-500"
                    style={{ width: `${Math.min(100, d.score)}%` }}
                  />
                </div>
                <div className="w-20 text-right text-xs text-slate-500">
                  {Math.round(d.score)}% · w{d.weight}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <div className="label mb-3">Catalog Sample</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="py-2 pr-4">ID</th>
                <th className="py-2 pr-4">Title</th>
                <th className="py-2 pr-4">Category</th>
                <th className="py-2 pr-4">Price</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2">Findings</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.product_id} className="border-b border-slate-100">
                  <td className="py-2 pr-4 font-mono text-xs">{p.product_id}</td>
                  <td className="py-2 pr-4">{p.title}</td>
                  <td className="py-2 pr-4 text-slate-500">{p.category ?? "—"}</td>
                  <td className="py-2 pr-4">{rupees(p.price_paise)}</td>
                  <td className="py-2 pr-4">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        p.availability === "in_stock"
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {p.availability}
                    </span>
                  </td>
                  <td className="py-2 text-xs text-slate-500">
                    {(p.problems ?? []).length ? p.problems.slice(0, 3).join(", ") : "clean"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
