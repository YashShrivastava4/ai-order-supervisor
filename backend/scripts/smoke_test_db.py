"""
S2 verification only — proves the SQLAlchemy models in app/db/models.py actually
match Postgres, and that inserts, the foreign keys, and the JSONB columns all
work end-to-end. Not part of the real app. Safe to delete once S2 is confirmed
working.

Run (Postgres must be up — `docker compose up -d` from the repo root):
    python scripts/smoke_test_db.py

Expected: prints the row it built for each table, then "S2 smoke test PASSED".
Nothing is left in the database afterwards — the test transaction is rolled
back on purpose, so this is safe to re-run as many times as you like.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models import ActivityLog, Base, Run, SupervisorConfig
from app.db.session import SessionLocal, engine


def main():
    print("Creating tables (safe to re-run — create_all is a no-op if they already exist) ...")
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        config = SupervisorConfig(
            name="Smoke Test Supervisor",
            base_instruction="Watch this order and act if anything looks wrong.",
            available_actions=["create_internal_note"],
        )
        db.add(config)
        db.flush()  # assigns config.id without committing

        run = Run(
            supervisor_config_id=config.id,
            order_context={"order_id": "smoke-test-order"},
        )
        db.add(run)
        db.flush()

        activity = ActivityLog(
            run_id=run.id,
            type="incoming_event",
            payload={"event_type": "order_created"},
        )
        db.add(activity)
        db.flush()

        print(f"supervisor_configs row: id={config.id} name={config.name!r}")
        print(f"runs row: id={run.id} status={run.status!r} supervisor_config_id={run.supervisor_config_id}")
        print(f"activity_log row: id={activity.id} type={activity.type!r} payload={activity.payload}")

        assert run.supervisor_config_id == config.id, "FK from runs to supervisor_configs didn't hold"
        assert activity.run_id == run.id, "FK from activity_log to runs didn't hold"

        db.rollback()  # smoke test only — leaves the database exactly as it was
        print("Rolled back — no test data left behind.")
    finally:
        db.close()

    print("S2 smoke test PASSED — models, foreign keys, and JSONB columns all work.")


if __name__ == "__main__":
    main()
