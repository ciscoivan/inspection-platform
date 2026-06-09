import sys, asyncio, time, threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from .database import engine, Base, get_db
from .models import Device, InspectionRun, User, hash_password
from .routers import devices, inspect, auth, reports, alerts, ping, subnet_calc, config_compare, custom_cmds, config_push, scheduler
from .templating import templates
_last_cleanup = {"ts": 0}
_last_cleanup_lock = threading.Lock()
Base.metadata.create_all(bind=engine)

# Migrate existing plaintext device passwords to encrypted storage
from .crypto import migrate_plaintext_passwords
from .database import SessionLocal as _MigrationSession
migrate_plaintext_passwords(_MigrationSession)
from .database import SessionLocal as _SeedSession
_seed_db = _SeedSession()
try:
    if not _seed_db.query(User).filter(User.username == "admin").first():
        _seed_db.add(User(username="admin", password_hash=hash_password("123.com"), is_admin=True))
        _seed_db.commit()
except Exception:
    _seed_db.rollback()
finally:
    _seed_db.close()
static_dir = Path(__file__).resolve().parent / "static"
app = FastAPI(title="ivan", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(inspect.router)
app.include_router(reports.router)
app.include_router(alerts.router)
app.include_router(ping.router)
app.include_router(subnet_calc.router)
app.include_router(config_compare.router)
app.include_router(custom_cmds.router)
app.include_router(config_push.router)
app.include_router(scheduler.router)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse as MWRedirect
PUBLIC_PATHS = {"/login", "/logout", "/static", "/docs", "/openapi.json", "/favicon.ico"}
class LoginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in PUBLIC_PATHS):
            return await call_next(request)
        token = request.cookies.get("inspect_session")
        if not token:
            return MWRedirect("/login?next=" + request.url.path, status_code=303)
        now = time.time()
        if now - _last_cleanup.get("ts", 0) > 3600:
            from .routers.auth import _sessions_lock, _cleanup_sessions
            with _sessions_lock:
                _cleanup_sessions()
            with _last_cleanup_lock:
                _last_cleanup["ts"] = now
        db = next(get_db())
        try:
            from .routers.auth import validate_session
            user = validate_session(request, db)
            if not user:
                resp = MWRedirect("/login?next=" + request.url.path, status_code=303)
                resp.delete_cookie("inspect_session")
                return resp
        finally:
            db.close()
        return await call_next(request)
app.add_middleware(LoginMiddleware)
async def scheduled_inspection():
    from .database import SessionLocal
    from .routers.inspect import _inspect_one
    from concurrent.futures import ThreadPoolExecutor
    def _run():
        import uuid as _uuid
        from .routers.inspect import _progress, _progress_lock
        ddb = SessionLocal()
        try:
            devs = ddb.query(Device).all()
            if not devs: return
            dids = [d.id for d in devs]
            run_id = str(_uuid.uuid4())[:8]
            with _progress_lock:
                _progress[run_id] = {
                    "total": len(dids),
                    "done": 0,
                    "devices": {d.ip: {"cpu": "...", "memory": "...", "status": "waiting"} for d in devs},
                }
            with ThreadPoolExecutor(max_workers=min(10,len(dids))) as pool:
                list(pool.map(lambda did: _inspect_one(did, run_id), dids))
            # Cleanup after estimated completion
            def _cleanup():
                import time as _t
                _t.sleep(max(len(dids) * 60, 10))
                with _progress_lock:
                    _progress.pop(run_id, None)
            threading.Thread(target=_cleanup, daemon=True).start()
        finally:
            ddb.close()
    await asyncio.get_event_loop().run_in_executor(None, _run)
scheduler = AsyncIOScheduler()

# Inject scheduler reference into the scheduler router module FIRST
from .routers.scheduler import load_all_schedules, set_scheduler as _set_sched
_set_sched(scheduler)

# Load schedules from DB and register dynamically
loaded = load_all_schedules()

# Fallback: if no DB schedules exist, keep the default daily 6am
if loaded == 0:
    scheduler.add_job(scheduled_inspection, CronTrigger(hour=6, minute=0), id="daily", name="daily")

try:
    scheduler.start()
except RuntimeError:
    pass
@app.get("/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    total = db.query(Device).count()
    connected = db.query(Device).filter(Device.status == "connected").count()
    failed = total - connected
    subq = db.query(InspectionRun.device_id, func.max(InspectionRun.timestamp).label("max_ts")).group_by(InspectionRun.device_id).subquery()
    latest = db.query(InspectionRun).join(subq, (InspectionRun.device_id == subq.c.device_id) & (InspectionRun.timestamp == subq.c.max_ts)).all()
    return templates.TemplateResponse(request, "dashboard.html", {"total": total, "connected": connected, "failed": failed, "latest": latest})
@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")
