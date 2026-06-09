"""
Inspection Scheduler — manage timed inspection tasks.
Supports once / hourly / daily / monthly schedules with per-device selection.
Uses APScheduler for dynamic job management.
"""
import json as _json
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import InspectionSchedule, Device, now_cst
from ..routers.auth import require_auth
from ..templating import templates

router = APIRouter(prefix="/scheduler", tags=["scheduler"])

# Reference to the global scheduler (set by main.py)
_scheduler = None


def set_scheduler(sched):
    """Called by main.py to inject the APScheduler instance."""
    global _scheduler
    _scheduler = sched


def _schedule_config_to_trigger(sc_type: str, config: dict):
    """Convert schedule_type + config dict to APScheduler trigger."""
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    if sc_type == "once":
        date_str = config.get("date", "")  # "2026-06-15"
        time_str = config.get("time", "00:00")  # "14:30"
        if not date_str:
            # No date specified, default to today
            date_str = datetime.now().strftime("%Y-%m-%d")
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            # If the datetime is in the past, add one day
            if dt < datetime.now():
                dt = dt + timedelta(days=1)
        except ValueError:
            return CronTrigger(hour=6, minute=0)  # fallback
        return DateTrigger(run_date=dt)

    elif sc_type == "hourly":
        hours = config.get("interval_hours", 1)
        return IntervalTrigger(hours=hours)

    elif sc_type == "daily":
        time_str = config.get("time", "06:00")
        h, m = time_str.split(":")
        return CronTrigger(hour=int(h), minute=int(m))

    elif sc_type == "monthly":
        day = config.get("day", 1)
        time_str = config.get("time", "06:00")
        h, m = time_str.split(":")
        return CronTrigger(day=int(day), hour=int(h), minute=int(m))

    # Default: daily at 6am
    return CronTrigger(hour=6, minute=0)


def _run_scheduled(job_id: str):
    """Execute inspection for a schedule. Called by APScheduler."""
    from ..database import SessionLocal
    from ..models import Device
    from ..routers.inspect import _inspect_one
    from concurrent.futures import ThreadPoolExecutor

    db = SessionLocal()
    try:
        sched = db.query(InspectionSchedule).filter(InspectionSchedule.id == int(job_id)).first()
        if not sched or not sched.enabled:
            return

        # Determine which devices to inspect
        device_ids = sched.device_ids or []
        if device_ids:
            devs = db.query(Device).filter(Device.id.in_(device_ids)).all()
        else:
            devs = db.query(Device).all()

        if not devs:
            return

        dids = [d.id for d in devs]

        # Initialize progress tracking
        run_id = f"sch_{job_id}"
        from ..routers.inspect import _progress as _sch_prog, _progress_lock as _sch_lock
        with _sch_lock:
            _sch_prog[run_id] = {
                "total": len(dids),
                "done": 0,
                "devices": {d.ip: {"cpu": "...", "memory": "...", "status": "等待中"} for d in devs},
            }

        # Run inspection
        with ThreadPoolExecutor(max_workers=min(10, len(dids))) as pool:
            list(pool.map(lambda did: _inspect_one(did, run_id), dids))

        # Cleanup progress after estimated completion
        def _clean_sch():
            import time as _t
            _t.sleep(max(len(dids) * 60, 10))
            with _sch_lock:
                _sch_prog.pop(run_id, None)
        import threading as _th
        _th.Thread(target=_clean_sch, daemon=True).start()

        # Update last_run
        sched.last_run = now_cst()
        db.commit()

        # Auto-disable once schedules
        if sched.schedule_type == "once":
            sched.enabled = False
            db.commit()
            if _scheduler:
                try:
                    _scheduler.remove_job(job_id)
                except Exception:
                    pass

    finally:
        db.close()


def _register_schedule(sched: InspectionSchedule):
    """Register a single schedule as an APScheduler job."""
    if not _scheduler or not sched.enabled:
        return

    job_id = str(sched.id)
    trigger = _schedule_config_to_trigger(sched.schedule_type, sched.schedule_config or {})

    # Remove existing job if any
    try:
        _scheduler.remove_job(job_id)
    except Exception:
        pass

    _scheduler.add_job(
        _run_scheduled,
        trigger,
        args=[job_id],
        id=job_id,
        name=sched.name,
        replace_existing=True,
    )


def load_all_schedules():
    """Load all enabled schedules from DB and register them. Called by main.py on startup."""
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        schedules = db.query(InspectionSchedule).filter(InspectionSchedule.enabled == True).all()
        for s in schedules:
            _register_schedule(s)
        return len(schedules)
    finally:
        db.close()


@router.get("")
def scheduler_page(request: Request, db: Session = Depends(get_db),
                   current_user=Depends(require_auth)):
    schedules = db.query(InspectionSchedule).order_by(InspectionSchedule.id).all()
    devices = db.query(Device).order_by(Device.ip).all()
    return templates.TemplateResponse(request, "scheduler.html", {
        "schedules": schedules,
        "devices": devices,
    })


@router.post("/add")
def add_schedule(
    request: Request,
    name: str = Form(...),
    schedule_type: str = Form(...),
    schedule_time: str = Form(default="06:00"),
    schedule_date: str = Form(default=""),
    schedule_day: int = Form(default=1),
    interval_hours: int = Form(default=1),
    device_ids: list[int] = Form(default=[]),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    if schedule_type not in ("once", "hourly", "daily", "monthly"):
        return RedirectResponse("/scheduler", status_code=303)

    # Build config dict
    config = {}
    if schedule_type == "once":
        config = {"date": schedule_date, "time": schedule_time}
    elif schedule_type == "hourly":
        config = {"interval_hours": max(1, min(interval_hours, 24))}
    elif schedule_type == "daily":
        config = {"time": schedule_time}
    elif schedule_type == "monthly":
        config = {"day": max(1, min(schedule_day, 28)), "time": schedule_time}

    sched = InspectionSchedule(
        name=name,
        schedule_type=schedule_type,
        schedule_config=config,
        device_ids=device_ids if device_ids else [],
        enabled=True,
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)

    # Register with APScheduler
    _register_schedule(sched)

    return RedirectResponse("/scheduler", status_code=303)


@router.post("/toggle/{sched_id}")
def toggle_schedule(sched_id: int, db: Session = Depends(get_db),
                    current_user=Depends(require_auth)):
    sched = db.query(InspectionSchedule).filter(InspectionSchedule.id == sched_id).first()
    if sched:
        sched.enabled = not sched.enabled
        db.commit()
        if sched.enabled:
            _register_schedule(sched)
        else:
            if _scheduler:
                try:
                    _scheduler.remove_job(str(sched_id))
                except Exception:
                    pass
    return RedirectResponse("/scheduler", status_code=303)


@router.post("/delete/{sched_id}")
def delete_schedule(sched_id: int, db: Session = Depends(get_db),
                    current_user=Depends(require_auth)):
    sched = db.query(InspectionSchedule).filter(InspectionSchedule.id == sched_id).first()
    if sched:
        if _scheduler:
            try:
                _scheduler.remove_job(str(sched_id))
            except Exception:
                pass
        db.delete(sched)
        db.commit()
    return RedirectResponse("/scheduler", status_code=303)


@router.post("/run-now/{sched_id}")
def run_now(sched_id: int, request: Request, db: Session = Depends(get_db),
            current_user=Depends(require_auth)):
    """Immediately execute a schedule once."""
    import threading

    sched = db.query(InspectionSchedule).filter(InspectionSchedule.id == sched_id).first()
    if not sched:
        if "application/json" in request.headers.get("accept", ""):
            from fastapi.responses import JSONResponse
            return JSONResponse({"error": "Schedule not found"}, status_code=404)
        return RedirectResponse("/scheduler", status_code=303)

    run_id = f"sch_{sched_id}"
    device_ids = sched.device_ids or []

    # Determine devices for progress tracking
    from ..models import Device
    if device_ids:
        devs = db.query(Device).filter(Device.id.in_(device_ids)).all()
    else:
        devs = db.query(Device).all()

    # Initialize progress
    from ..routers.inspect import _progress, _progress_lock
    with _progress_lock:
        _progress[run_id] = {
            "total": len(devs),
            "done": 0,
            "devices": {d.ip: {"cpu": "...", "memory": "...", "status": "等待中"} for d in devs},
        }

    t = threading.Thread(target=_run_scheduled, args=(str(sched_id),), daemon=True)
    t.start()

    # Auto-cleanup progress after 10s of completion
    def _cleanup_progress():
        import time as _time
        _time.sleep(max(len(devs) * 60, 10))
        with _progress_lock:
            _progress.pop(run_id, None)
    threading.Thread(target=_cleanup_progress, daemon=True).start()

    # Return JSON for AJAX, redirect for form POST
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        from fastapi.responses import JSONResponse
        return JSONResponse({"run_id": run_id, "device_count": len(devs)})
    return RedirectResponse("/scheduler", status_code=303)
