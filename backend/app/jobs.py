# backend/app/jobs.py
"""Gerenciador de jobs assíncronos de exportação isolado por tenant."""

from datetime import datetime, timezone
from threading import Lock
from typing import Any
import uuid

_JOBS: dict[str, dict[str, Any]] = {}
_LOCK = Lock()


def create_job(tenant_id: int | None, user: str, tipo: str, params: dict[str, Any]) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "usuario": user,
        "tipo": tipo,
        "status": "pending",
        "params": params,
        "result": None,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    with _LOCK:
        _JOBS[job_id] = job
    return dict(job)


def update_job(job_id: str, **fields) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.update(fields)
        job["updated_at"] = datetime.now(timezone.utc).isoformat()


def get_job_for_tenant(job_id: str, tenant_id: int | None, is_admin_geral: bool = False) -> dict[str, Any] | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return None
        if not is_admin_geral and job.get("tenant_id") != tenant_id:
            return None
        return dict(job)
