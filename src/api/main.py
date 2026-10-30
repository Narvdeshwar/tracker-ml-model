"""
FastAPI Backend Application for Phase 10: IPO Research & Shadow Monitoring Dashboard.
Strictly Read-Only Endpoints for Research, Audit & Diagnostic Surveillance.
Real-Money Trading & Automated Broker Order Execution are Strictly Prohibited.
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.api.common import (
    load_manifest,
    load_tracked_candidates,
    verify_frozen_models,
    get_committed_ledgers,
    MANIFEST_PATH,
    DECISION_LEDGER,
    OUTCOME_LEDGER,
    REGISTRY_PATH
)
from src.api.routes_ipos import router as ipos_router
from src.api.routes_metrics import router as metrics_router
from src.api.routes_monitoring import router as monitoring_router

app = FastAPI(
    title="IPO ML Research & Prospective Monitoring API",
    description="Read-only research and audit API for Indian IPO prediction models and shadow tracking.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dashboard", "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def get_dashboard_root():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "IPO Research Dashboard API active. Visit /docs for OpenAPI specs."}

app.include_router(ipos_router)
app.include_router(metrics_router)
app.include_router(monitoring_router)
