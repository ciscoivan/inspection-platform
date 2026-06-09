from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import CustomCommand, Device
from ..templating import templates
from ..routers.auth import require_auth
from ..crypto import decrypt_password

router = APIRouter(prefix="/custom-commands", tags=["custom-commands"])

PLATFORM_TYPES = [
    ("all", "所有平台"),
    ("cisco_ios", "Cisco IOS/IOS-XE"),
    ("cisco_xr", "Cisco IOS-XR"),
    ("cisco_nxos", "Cisco NX-OS"),
    ("juniper", "Juniper JunOS"),
    ("huawei", "Huawei VRP"),
    ("hp_comware", "H3C Comware"),
    ("fortinet", "Fortinet FortiOS"),
    ("arista_eos", "Arista EOS"),
    ("ruijie_os", "Ruijie RGOS"),
]


def get_custom_commands(device_type: str, db: Session) -> dict[str, str]:
    cmds = (
        db.query(CustomCommand)
        .filter(
            (CustomCommand.device_type == device_type) | (CustomCommand.device_type == "all"),
            CustomCommand.enabled == True,
        )
        .all()
    )
    return {c.command: c.description or c.command for c in cmds}


def _ssh_execute(dev: Device, cmds: list[CustomCommand]) -> dict:
    """Execute commands on a device via SSH. Returns {results, status, error}."""
    results = {}
    conn = None
    status = "connected"
    error_msg = None

    try:
        from netmiko import ConnectHandler
        conn = ConnectHandler(
            device_type=dev.device_type, host=dev.ip,
            username=dev.username, password=decrypt_password(dev.password), port=dev.port,
            conn_timeout=15, auth_timeout=15, banner_timeout=15,
        )
        for cmd in cmds:
            try:
                out = conn.send_command_timing(cmd.command, read_timeout=30, delay_factor=2)
                results[cmd.description or cmd.command] = out
            except Exception as e:
                results[cmd.description or cmd.command] = f"[Error] {e}"
    except Exception as e:
        status = "error"
        error_msg = str(e)
        for cmd in cmds:
            results[cmd.description or cmd.command] = f"[Error] SSH: {e}"
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass

    return {"results": results, "status": status, "error": error_msg}


def _save_inspection_run(db: Session, dev: Device, result_data: dict, status: str, error_msg: str | None):
    """Save execution result as an inspection run."""
    import json as _json
    from ..models import InspectionRun, now_cst

    run = InspectionRun(
        device_id=dev.id,
        timestamp=now_cst(),
        cpu="N/A", memory="N/A", uptime="N/A",
        hostname=dev.hostname or dev.ip,
        status=status,
        error=error_msg,
        raw_data=_json.dumps({"Custom Commands": result_data}, ensure_ascii=False),
    )
    db.add(run)
    dev.status = status
    db.commit()


@router.get("")
def list_page(request: Request, db: Session = Depends(get_db)):
    cmds = db.query(CustomCommand).order_by(CustomCommand.device_type, CustomCommand.id).all()
    devices = db.query(Device).order_by(Device.ip).all()
    return templates.TemplateResponse(request, "custom_cmds.html", {
        "cmds": cmds, "platforms": PLATFORM_TYPES, "devices": devices
    })


@router.post("/add")
def add_command(
    request: Request,
    device_type: str = Form(...),
    command: str = Form(...),
    description: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    c = CustomCommand(device_type=device_type, command=command, description=description)
    db.add(c)
    db.commit()
    return RedirectResponse("/custom-commands", status_code=303)


@router.post("/execute")
def execute_command(
    request: Request,
    cmd_id: int = Form(...),
    device_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    cmd = db.query(CustomCommand).filter(CustomCommand.id == cmd_id).first()
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not cmd or not dev:
        return RedirectResponse("/custom-commands", status_code=303)

    result = _ssh_execute(dev, [cmd])
    exec_result = {
        "ip": dev.ip,
        "hostname": dev.hostname or dev.ip,
        "success": result["status"] == "connected",
        "output": list(result["results"].values())[0] if result["results"] else "",
    }

    cmds = db.query(CustomCommand).order_by(CustomCommand.device_type, CustomCommand.id).all()
    devices = db.query(Device).order_by(Device.ip).all()
    return templates.TemplateResponse(request, "custom_cmds.html", {
        "cmds": cmds, "platforms": PLATFORM_TYPES, "devices": devices,
        "exec_result": exec_result, "exec_cmd": cmd.command,
    })


@router.post("/execute-batch")
def execute_batch(
    request: Request,
    cmd_ids: list[int] = Form(...),
    device_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    dev = db.query(Device).filter(Device.id == device_id).first()
    if not dev:
        return RedirectResponse("/custom-commands", status_code=303)

    cmds = db.query(CustomCommand).filter(
        CustomCommand.id.in_(cmd_ids),
        CustomCommand.enabled == True,
    ).all()

    if not cmds:
        return RedirectResponse("/custom-commands", status_code=303)

    result = _ssh_execute(dev, cmds)
    _save_inspection_run(db, dev, result["results"], result["status"], result["error"])

    all_cmds = db.query(CustomCommand).order_by(CustomCommand.device_type, CustomCommand.id).all()
    devices = db.query(Device).order_by(Device.ip).all()
    return templates.TemplateResponse(request, "custom_cmds.html", {
        "cmds": all_cmds, "platforms": PLATFORM_TYPES, "devices": devices,
        "batch_result": {
            "device": dev,
            "results": result["results"],
            "status": result["status"],
            "error": result["error"],
        },
    })


@router.post("/execute-multi")
def execute_multi(
    request: Request,
    cmd_ids: list[int] = Form(...),
    device_ids: list[int] = Form(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    if not cmd_ids or not device_ids:
        return RedirectResponse("/custom-commands", status_code=303)

    cmds = db.query(CustomCommand).filter(
        CustomCommand.id.in_(cmd_ids),
        CustomCommand.enabled == True,
    ).all()
    devices = db.query(Device).filter(Device.id.in_(device_ids)).order_by(Device.ip).all()

    if not cmds or not devices:
        return RedirectResponse("/custom-commands", status_code=303)

    multi_results = []
    for dev in devices:
        result = _ssh_execute(dev, cmds)
        _save_inspection_run(db, dev, result["results"], result["status"], result["error"])

        multi_results.append({
            "ip": dev.ip,
            "hostname": dev.hostname or dev.ip,
            "device_type": dev.device_type,
            "status": result["status"],
            "error": result["error"],
            "results": result["results"],
        })

    all_cmds = db.query(CustomCommand).order_by(CustomCommand.device_type, CustomCommand.id).all()
    devices_all = db.query(Device).order_by(Device.ip).all()
    return templates.TemplateResponse(request, "custom_cmds.html", {
        "cmds": all_cmds, "platforms": PLATFORM_TYPES, "devices": devices_all,
        "multi_results": multi_results,
    })


@router.post("/delete/{cmd_id}")
def delete_command(cmd_id: int, db: Session = Depends(get_db), current_user=Depends(require_auth)):
    c = db.query(CustomCommand).filter(CustomCommand.id == cmd_id).first()
    if c:
        db.delete(c)
        db.commit()
    return RedirectResponse("/custom-commands", status_code=303)


@router.post("/toggle/{cmd_id}")
def toggle_command(cmd_id: int, db: Session = Depends(get_db), current_user=Depends(require_auth)):
    c = db.query(CustomCommand).filter(CustomCommand.id == cmd_id).first()
    if c:
        c.enabled = not c.enabled
        db.commit()
    return RedirectResponse("/custom-commands", status_code=303)
