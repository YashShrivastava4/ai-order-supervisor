"""Supervisor config endpoints (spec §10)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import SupervisorConfig
from app.db.session import get_db
from app.schemas import SupervisorConfigCreate, SupervisorConfigResponse

router = APIRouter(prefix="/supervisors", tags=["supervisors"])


@router.post("", response_model=SupervisorConfigResponse)
def create_supervisor(
    payload: SupervisorConfigCreate, db: Session = Depends(get_db)
) -> SupervisorConfig:
    config = SupervisorConfig(
        name=payload.name,
        base_instruction=payload.base_instruction,
        available_actions=payload.available_actions,
        default_wake_seconds=payload.default_wake_seconds,
        wake_aggressiveness=payload.wake_aggressiveness,
        model_config=payload.model_cfg,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.get("", response_model=list[SupervisorConfigResponse])
def list_supervisors(db: Session = Depends(get_db)) -> list[SupervisorConfig]:
    return db.query(SupervisorConfig).order_by(SupervisorConfig.created_at).all()


@router.get(
    "/{supervisor_id}",
    response_model=SupervisorConfigResponse,
    responses={404: {"description": "Supervisor config not found"}},
)
def get_supervisor(
    supervisor_id: UUID, db: Session = Depends(get_db)
) -> SupervisorConfig:
    config = db.get(SupervisorConfig, supervisor_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Supervisor config not found")
    return config
