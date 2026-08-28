/**
 * Runtime API proxy: forwards /api/* from the browser to the FastAPI backend.
 *
 * Lives in a route handler (not next.config rewrites) because standalone
 * builds serialize next.config at IMAGE BUILD time — env-dependent rewrite
 * destinations get baked as localhost and break inside containers. Here
 * BACKEND_URL is read per request, so docker-compose's runtime env works.
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL || "http://localhost:8000";

async function forward(req: NextRequest, path: string[]) {
  const qs = req.nextUrl.search;
  const url = `${BACKEND}/api/${path.join("/")}${qs}`;
  const init: RequestInit = {
    method: req.method,
    headers: {
      "Content-Type": req.headers.get("content-type") ?? "application/json",
    },
  };
  if (!["GET", "HEAD"].includes(req.method)) {
    init.body = await req.arrayBuffer();
  }
  try {
    const res = await fetch(url, init);
    const body = await res.arrayBuffer();
    return new NextResponse(body, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch (e: any) {
    return NextResponse.json(
      { error: "backend_unreachable", detail: String(e?.cause?.code ?? e.message) },
      { status: 502 },
    );
  }
}

type Ctx = { params: { path: string[] } };

export const GET = (req: NextRequest, ctx: Ctx) => forward(req, ctx.params.path);
export const POST = (req: NextRequest, ctx: Ctx) => forward(req, ctx.params.path);
export const PUT = (req: NextRequest, ctx: Ctx) => forward(req, ctx.params.path);
export const DELETE = (req: NextRequest, ctx: Ctx) => forward(req, ctx.params.path);
