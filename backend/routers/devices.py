from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Device
from ..schemas import DeviceCreate, DeviceUpdate
from ..templating import templates
from ..routers.auth import require_auth
from ..crypto import encrypt_password

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/api")
def list_devices_api(db: Session = Depends(get_db), current_user=Depends(require_auth)):
    return db.query(Device).order_by(Device.ip).all()


@router.post("/api")
def create_device_api(data: DeviceCreate, db: Session = Depends(get_db), current_user=Depends(require_auth)):
    dev_data = data.model_dump()
    dev_data["password"] = encrypt_password(dev_data["password"])
    dev = Device(**dev_data)
    db.add(dev)
    db.commit()
    db.refresh(dev)
    return dev


@router.post("/add")
def create_device_form(ip: str = Form(...), device_type: str = Form(...),
                       current_user=Depends(require_auth),
                       username: str = Form(...), password: str = Form(...),
                       port: int = Form(22), db: Session = Depends(get_db)):
    dev = Device(ip=ip, device_type=device_type, username=username, password=encrypt_password(password), port=port)
    db.add(dev)
    db.commit()
    return RedirectResponse("/devices", status_code=303)


@router.put("/api/{device_id}")
def update_device_api(device_id: int, data: DeviceUpdate, db: Session = Depends(get_db), current_user=Depends(require_auth)):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(404, "device not found")
    update_data = data.model_dump(exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        update_data["password"] = encrypt_password(update_data["password"])
    for k, v in update_data.items():
        setattr(dev, k, v)
    db.commit()
    return dev


@router.delete("/api/{device_id}")
def delete_device_api(device_id: int, db: Session = Depends(get_db), current_user=Depends(require_auth)):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        raise HTTPException(404, "device not found")
    db.delete(dev)
    db.commit()
    return {"ok": True}


@router.get("")
def devices_page(request: Request, db: Session = Depends(get_db)):
    devices = db.query(Device).order_by(Device.ip).all()
    return templates.TemplateResponse(request, "devices.html", {"devices": devices})
