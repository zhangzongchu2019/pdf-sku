"""Collaboration 路由。对齐: OpenAPI V2.0 §/tasks + §/annotations"""
from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Path, Body, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.dependencies import DBSession
from pdf_sku.common.models import HumanTask, Annotation, AnnotatorProfile
from pdf_sku.collaboration.annotation_service import TaskManager
from pdf_sku.collaboration.lock_manager import LockManager
from pdf_sku.auth.dependencies import CurrentUser, AnnotatorUser, AdminUser

router = APIRouter(prefix="/api/v1", tags=["Collaboration"])

_task_mgr = TaskManager()
_lock_mgr = LockManager()


@router.get("/tasks/files")
async def list_task_files(db: DBSession):
    """任务文件分组。"""
    result = await db.execute(
        select(
            HumanTask.job_id,
            func.count(HumanTask.task_id).label("task_count"),
        )
        .group_by(HumanTask.job_id)
        .order_by(func.count(HumanTask.task_id).desc())
    )
    rows = result.all()
    return {"data": [
        {"job_id": str(r.job_id), "task_count": r.task_count}
        for r in rows
    ]}


@router.get("/tasks")
async def list_tasks(
    db: DBSession,
    job_id: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """任务列表 (分页 + 过滤)。"""
    query = select(HumanTask).order_by(HumanTask.created_at.desc())
    if job_id:
        query = query.where(HumanTask.job_id == UUID(job_id))
    if status:
        query = query.where(HumanTask.status == status)

    total_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    tasks = result.scalars().all()

    return {
        "data": [_task_to_dict(t) for t in tasks],
        "pagination": {"page": page, "size": size, "total": total},
    }


@router.get("/tasks/{task_id}")
async def get_task(db: DBSession, task_id: str = Path(...)):
    result = await db.execute(
        select(HumanTask).where(HumanTask.task_id == UUID(task_id)))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    return _task_to_dict(task)


@router.post("/tasks/next")
async def auto_pick_next(
    db: DBSession, user: AnnotatorUser,
):
    """原子领取下一个任务 (SKIP LOCKED)。需要标注员角色。"""
    operator = user.username
    task = await _lock_mgr.acquire_next(db, operator)
    if not task:
        return {"data": None, "message": "No tasks available"}
    await db.commit()
    return _task_to_dict(task)


@router.post("/tasks/{task_id}/assign")
async def assign_task(
    db: DBSession,
    task_id: str = Path(...),
    operator: str = Body(..., embed=True),
):
    try:
        task = await _task_mgr.assign_task(db, task_id, operator)
        await db.commit()
        return _task_to_dict(task)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/tasks/{task_id}/complete")
async def complete_task(
    db: DBSession,
    user: AnnotatorUser,
    task_id: str = Path(...),
    body: dict = Body(...),
):
    operator = user.username
    result_data = body.get("result", {})
    try:
        task = await _task_mgr.complete_task(db, task_id, result_data, operator)
        await db.commit()
        return _task_to_dict(task)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/tasks/{task_id}/revert")
async def revert_task(
    db: DBSession,
    task_id: str = Path(...),
    reason: str = Body("", embed=True),
    operator: str = Body("system", embed=True),
):
    try:
        task = await _task_mgr.revert_task(db, task_id, operator, reason)
        await db.commit()
        return _task_to_dict(task)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/tasks/{task_id}/heartbeat")
async def heartbeat(
    db: DBSession,
    task_id: str = Path(...),
    operator: str = Body(..., embed=True),
):
    ok = await _lock_mgr.heartbeat(db, task_id, operator)
    if not ok:
        raise HTTPException(409, "Lock lost")
    await db.commit()
    return {"ok": True}


@router.get("/tasks/{task_id}/cross-page-skus")
async def get_cross_page_skus(db: DBSession, task_id: str = Path(...)):
    return {"data": []}


@router.post("/annotations")
async def create_annotation(db: DBSession, body: dict = Body(...)):
    """独立标注。"""
    annotation = Annotation(
        job_id=UUID(body["job_id"]),
        page_number=body["page_number"],
        annotator=body.get("annotator", ""),
        type=body.get("type", "manual"),
        payload=body.get("payload", {}),
    )
    db.add(annotation)
    await db.commit()
    return {"annotation_id": str(annotation.annotation_id)}


# === Ops 运维端点 ===

@router.post("/ops/tasks/batch-skip")
async def batch_skip(db: DBSession, body: dict = Body(...)):
    result = await _task_mgr.batch_skip(
        db,
        task_ids=body.get("task_ids", []),
        reason=body.get("reason", ""),
        operator=body.get("operator", "ops"),
    )
    await db.commit()
    return result


@router.post("/ops/tasks/batch-reassign")
async def batch_reassign(db: DBSession, body: dict = Body(...)):
    result = await _task_mgr.batch_reassign(
        db,
        task_ids=body.get("task_ids", []),
        target=body.get("target", ""),
        operator=body.get("operator", "ops"),
    )
    await db.commit()
    return result


@router.get("/ops/annotators")
async def list_annotators(db: DBSession):
    result = await db.execute(select(AnnotatorProfile))
    profiles = result.scalars().all()
    return {"data": [
        {
            "annotator_id": p.annotator_id,
            "accuracy_rate": p.accuracy_rate,
            "total_tasks": p.total_tasks,
            "specialties": p.specialties or [],
        }
        for p in profiles
    ]}


@router.get("/ops/annotators/{annotator_id}")
async def get_annotator(db: DBSession, annotator_id: str = Path(...)):
    result = await db.execute(
        select(AnnotatorProfile).where(
            AnnotatorProfile.annotator_id == annotator_id))
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Annotator not found")
    return {
        "annotator_id": p.annotator_id,
        "accuracy_rate": p.accuracy_rate,
        "total_tasks": p.total_tasks,
        "specialties": p.specialties or [],
    }


def _task_to_dict(task: HumanTask) -> dict:
    return {
        "task_id": str(task.task_id),
        "job_id": str(task.job_id),
        "page_number": task.page_number,
        "task_type": task.task_type,
        "status": task.status,
        "priority": task.priority,
        "assigned_to": task.assigned_to,
        "locked_at": task.locked_at.isoformat() if task.locked_at else None,
        "timeout_at": task.timeout_at.isoformat() if task.timeout_at else None,
        "rework_count": task.rework_count,
        "context": task.context,
        "result": task.result,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }
