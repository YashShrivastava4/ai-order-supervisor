"""FastAPI app instance (spec §3).

The Temporal worker (app/worker.py, built in S5) is a separate OS process
and is never imported here — this process only serves the HTTP API.
"""
from fastapi import FastAPI

from app.api.routes_supervisors import router as supervisors_router
from app.db.models import Base
from app.db.seed import seed_supervisor_templates
from app.db.session import SessionLocal, engine

app = FastAPI(title="Order Supervisor API")

app.include_router(supervisors_router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    # No migration tool for a POC (spec §12) — create_all is enough here.
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_supervisor_templates(db)
    finally:
        db.close()
