"""FastAPI application entrypoint."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .api import buyer as buyer_api
from .api import catalog as catalog_api
from .api import checkout as checkout_api
from .api import evaluation as evaluation_api
from .api import tools as tools_api
from .api import webhooks as webhooks_api

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Agent Commerce Readiness Lab",
    description="Merchant-side compiler + AI buyer simulation + Razorpay "
                "transaction proof (docs/00–14).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (catalog_api.router, buyer_api.router, checkout_api.router,
               evaluation_api.router, tools_api.router, webhooks_api.router):
    app.include_router(router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "seeded": db.is_seeded(),
    }


@app.on_event("startup")
def ensure_seeded() -> None:
    """Auto-seed on empty DB so `docker compose up` yields a working demo."""
    from .catalog.generator import generate
    from .catalog.importer import run_compiler

    if not db.is_seeded():
        logging.info("empty database — seeding synthetic catalog")
        stats = generate()
        logging.info("generated %s rows", stats["rows"])
        result = run_compiler()
        logging.info("compiled %s products / %s variants",
                     result["products"], result["variants"])
