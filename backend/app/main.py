import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.db import Run, SessionLocal, Supervisor
from app.temporal_client import start_run


def _format_utc_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)

    return value.isoformat().replace("+00:00", "Z")


class RunCreateRequest(BaseModel):
    order_id: str
    supervisor_id: str
    order_context: str | None = None


class SupervisorCreateRequest(BaseModel):
    name: str
    base_instruction: str
    available_actions: list[str]
    default_wakeup_behavior: str | None = None
    model_config_value: str | None = Field(default=None, alias="model_config")
    wakeup_aggressiveness: str | None = None

    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())


class SupervisorRead(BaseModel):
    id: str
    name: str
    base_instruction: str
    available_actions: list[str]
    default_wakeup_behavior: str | None = None
    model_config_value: str | None = Field(default=None, alias="model_config")
    wakeup_aggressiveness: str | None = None

    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())


class RunRead(BaseModel):
    id: str
    order_id: str
    supervisor_id: str
    order_context: str | None = None
    status: str


app = FastAPI(title="Order Supervisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/supervisors", response_model=list[SupervisorRead])
def list_supervisors():
    db = SessionLocal()
    try:
        supervisors = db.query(Supervisor).all()
        return [
            SupervisorRead(
                id=supervisor.id,
                name=supervisor.name,
                base_instruction=supervisor.base_instruction,
                available_actions=supervisor.available_actions,
                default_wakeup_behavior=supervisor.default_wakeup_behavior,
                model_config=supervisor.model_config,
                wakeup_aggressiveness=supervisor.wakeup_aggressiveness,
            )
            for supervisor in supervisors
        ]
    finally:
        db.close()


@app.post("/api/supervisors", response_model=SupervisorRead)
def create_supervisor(payload: SupervisorCreateRequest):
    supervisor_id = f"supervisor-{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        supervisor = Supervisor(
            id=supervisor_id,
            name=payload.name,
            base_instruction=payload.base_instruction,
            available_actions=payload.available_actions,
            default_wakeup_behavior=payload.default_wakeup_behavior,
            model_config=payload.model_config_value,
            wakeup_aggressiveness=payload.wakeup_aggressiveness,
            created_at=now,
        )
        db.add(supervisor)
        db.commit()
        db.refresh(supervisor)

        return SupervisorRead(
            id=supervisor.id,
            name=supervisor.name,
            base_instruction=supervisor.base_instruction,
            available_actions=supervisor.available_actions,
            default_wakeup_behavior=supervisor.default_wakeup_behavior,
            model_config=supervisor.model_config,
            wakeup_aggressiveness=supervisor.wakeup_aggressiveness,
        )
    finally:
        db.close()


@app.get("/api/supervisors/{supervisor_id}", response_model=SupervisorRead)
def get_supervisor(supervisor_id: str):
    db = SessionLocal()
    try:
        supervisor = db.get(Supervisor, supervisor_id)
        if supervisor is None:
            raise HTTPException(status_code=404, detail="supervisor not found")

        return SupervisorRead(
            id=supervisor.id,
            name=supervisor.name,
            base_instruction=supervisor.base_instruction,
            available_actions=supervisor.available_actions,
            default_wakeup_behavior=supervisor.default_wakeup_behavior,
            model_config=supervisor.model_config,
            wakeup_aggressiveness=supervisor.wakeup_aggressiveness,
        )
    finally:
        db.close()


@app.post("/api/runs", response_model=RunRead)
async def create_run(payload: RunCreateRequest):
    order_id = payload.order_id
    supervisor_id = payload.supervisor_id

    if not order_id or not supervisor_id:
        raise HTTPException(
            status_code=400, detail="order_id and supervisor_id are required"
        )

    db = SessionLocal()
    try:
        supervisor = db.get(Supervisor, supervisor_id)
        if supervisor is None:
            raise HTTPException(status_code=404, detail="supervisor not found")

        run_id = f"run-{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc)
        run = Run(
            id=run_id,
            supervisor_id=supervisor_id,
            order_id=order_id,
            order_context=payload.order_context,
            status="running",
            memory_summary=None,
            wakeup_guidance=None,
            next_wakeup_at=None,
            final_summary=None,
            created_at=now,
            updated_at=now,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
    finally:
        db.close()

    workflow_run_id = await start_run(
        run_id=run_id,
        order_id=order_id,
        supervisor_id=supervisor_id,
        order_context=payload.order_context,
    )

    return RunRead(
        id=workflow_run_id,
        order_id=order_id,
        supervisor_id=supervisor_id,
        order_context=payload.order_context,
        status="running",
    )


class OrderEventRequest(BaseModel):
    event_type: str
    payload: dict | None = None


@app.post("/api/runs/{run_id}/events")
async def send_order_event(run_id: str, payload: OrderEventRequest):
    from app.temporal_client import send_order_event_signal

    try:
        await send_order_event_signal(run_id, payload.event_type, payload.payload)
        return {
            "status": "event sent",
            "run_id": run_id,
            "event_type": payload.event_type,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/runs/{run_id}/terminate")
async def terminate_run(run_id: str):
    from app.temporal_client import send_terminate_signal

    try:
        await send_terminate_signal(run_id)
        return {"status": "terminate sent", "run_id": run_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/runs/{run_id}/interrupt")
async def interrupt_run(run_id: str):
    from app.temporal_client import send_interrupt_signal

    try:
        await send_interrupt_signal(run_id)
        return {"status": "interrupt sent", "run_id": run_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/runs/{run_id}/resume")
async def resume_run(run_id: str):
    from app.temporal_client import send_resume_signal

    try:
        await send_resume_signal(run_id)
        return {"status": "resume sent", "run_id": run_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class InstructionRequest(BaseModel):
    text: str


@app.post("/api/runs/{run_id}/instructions")
async def add_instruction(run_id: str, payload: InstructionRequest):
    from app.temporal_client import send_add_instruction_signal

    cleaned = payload.text.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="text is required")

    try:
        await send_add_instruction_signal(run_id, cleaned)
        return {"status": "instruction sent", "run_id": run_id, "text": cleaned}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/runs")
def list_runs():
    """List all runs with basic info: id, order_id, status, next_wakeup_at"""
    db = SessionLocal()
    try:
        from app.db import ActivityLog

        runs = db.query(Run).all()
        result = []
        for run in runs:
            result.append(
                {
                    "id": run.id,
                    "order_id": run.order_id,
                    "supervisor_id": run.supervisor_id,
                    "status": run.status,
                    "memory_summary": run.memory_summary,
                    "next_wakeup_at": _format_utc_datetime(run.next_wakeup_at),
                    "created_at": _format_utc_datetime(run.created_at),
                    "updated_at": _format_utc_datetime(run.updated_at),
                }
            )
        return result
    finally:
        db.close()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    """Get full run details including activity log timeline and final_summary"""
    db = SessionLocal()
    try:
        from app.db import ActivityLog

        run = db.get(Run, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")

        # Get activity log for this run, in chronological order
        activity_log = db.query(ActivityLog).filter(ActivityLog.run_id == run_id).all()

        timeline = [
            {
                "id": entry.id,
                "type": entry.type,
                "payload": entry.payload,
                "created_at": _format_utc_datetime(entry.created_at),
            }
            for entry in activity_log
        ]

        return {
            "id": run.id,
            "order_id": run.order_id,
            "supervisor_id": run.supervisor_id,
            "order_context": run.order_context,
            "status": run.status,
            "memory_summary": run.memory_summary,
            "wakeup_guidance": run.wakeup_guidance,
            "next_wakeup_at": _format_utc_datetime(run.next_wakeup_at),
            "final_summary": run.final_summary,
            "created_at": _format_utc_datetime(run.created_at),
            "updated_at": _format_utc_datetime(run.updated_at),
            "timeline": timeline,
        }
    finally:
        db.close()
