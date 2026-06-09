import secrets
import threading
import time
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal
from ..models import User, hash_password, verify_password
from ..templating import templates

router = APIRouter(tags=["auth"])

SESSION_COOKIE = "inspect_session"
SESSION_TTL = 86400 * 7
_sessions: dict[str, dict] = {}
_sessions_lock = threading.Lock()


def _cleanup_sessions():
    now = time.time()
    expired = [t for t, v in _sessions.items() if v["expires"] < now]
    for t in expired:
        _sessions.pop(t, None)


def _session_get(token: str):
    with _sessions_lock:
        entry = _sessions.get(token)
        if not entry:
            return None
        if entry["expires"] < time.time():
            _sessions.pop(token, None)
            return None
        return entry["user_id"]


def get_current_user(request: Request, db: Session):
    token = request.cookies.get(SESSION_COOKIE)
    user_id = _session_get(token) if token else None
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


def get_current_user_sync(request: Request, db: Session):
    return get_current_user(request, db)


def validate_session(request: Request, db: Session):
    token = request.cookies.get(SESSION_COOKIE)
    user_id = _session_get(token) if token else None
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        _sessions.pop(token, None)
        return None
    return user




def require_auth(request: Request, db: Session = Depends(get_db)):
    """Dependency for API endpoints — returns 401 JSON instead of redirect."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...),
          next: str = Form(default="/"), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(request, "login.html", {"error": "wrong password"})
    with _sessions_lock:
        _cleanup_sessions()
        token = secrets.token_hex(32)
        _sessions[token] = {"user_id": user.id, "expires": time.time() + SESSION_TTL}
    resp = RedirectResponse(next or "/", status_code=303)
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, max_age=SESSION_TTL)
    return resp


@router.get("/logout")
def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with _sessions_lock:
            _sessions.pop(token, None)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@router.get("/users")
def users_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_sync(request, db)
    if not user or not user.is_admin:
        return RedirectResponse("/login", status_code=303)
    users = db.query(User).all()
    return templates.TemplateResponse(request, "users.html", {"users": users, "current_user": user})


@router.post("/users/add")
def add_user(request: Request, username: str = Form(...), password: str = Form(...),
             is_admin: str = Form(default="0"), db: Session = Depends(get_db)):
    admin = get_current_user_sync(request, db)
    if not admin or not admin.is_admin:
        return RedirectResponse("/login", status_code=303)
    if db.query(User).filter(User.username == username).first():
        return templates.TemplateResponse(request, "users.html", {
            "users": db.query(User).all(), "current_user": admin,
            "error": "user exists",
        })
    u = User(username=username, password_hash=hash_password(password), is_admin=(is_admin == "1"))
    db.add(u)
    db.commit()
    return RedirectResponse("/users", status_code=303)


@router.post("/users/delete/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_current_user_sync(request, db)
    if not admin or not admin.is_admin:
        return RedirectResponse("/login", status_code=303)
    if user_id == admin.id:
        return RedirectResponse("/users", status_code=303)
    target = db.query(User).filter(User.id == user_id).first()
    if target and target.is_admin:
        if db.query(User).filter(User.is_admin == True).count() <= 1:
            return RedirectResponse("/users", status_code=303)
    if target:
        db.delete(target)
        db.commit()
    return RedirectResponse("/users", status_code=303)
