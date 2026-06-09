"""
Configuration push module.
Push configuration commands to network devices via SSH.
Supports text input and file upload. Uses netmiko send_config_set.
"""
from fastapi import APIRouter, Depends, Request, Form, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Device
from ..routers.auth import require_auth
from ..crypto import decrypt_password
from ..templating import templates

router = APIRouter(prefix="/config-push", tags=["config-push"])

MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB

def _save_push_run(db: Session, dev: Device, commands: list[str], output: str, success: bool, error: str | None):
    """Save config push result as an inspection run."""
    import json as _json
    from ..models import InspectionRun, now_cst

    run = InspectionRun(
        device_id=dev.id,
        timestamp=now_cst(),
        cpu="N/A", memory="N/A", uptime="N/A",
        hostname=dev.hostname or dev.ip,
        status="connected" if success else "error",
        error=error,
        raw_data=_json.dumps({
            "Config Push": {
                "Commands": "\n".join(commands),
                "Output": output,
                "Success": success,
            }
        }, ensure_ascii=False),
    )
    db.add(run)
    db.commit()

def _push_to_device(dev: Device, commands: list[str]) -> dict:
    """Push configuration commands to a single device.
    Uses netmiko send_config_set which auto-enters config mode.
    Returns {"success": bool, "output": str, "error": str|None}
    """
    result = {
        "ip": dev.ip,
        "hostname": dev.hostname or dev.ip,
        "device_type": dev.device_type,
        "success": False,
        "output": "",
        "error": None,
    }
    conn = None
    try:
        from netmiko import ConnectHandler
        from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException

        conn = ConnectHandler(
            device_type=dev.device_type,
            host=dev.ip,
            username=dev.username,
            password=decrypt_password(dev.password),
            port=dev.port,
            conn_timeout=15,
            auth_timeout=15,
            banner_timeout=15,
        )
        output = conn.send_config_set(commands, read_timeout=60, delay_factor=2)
        result["success"] = True
        result["output"] = output

    except NetmikoTimeoutException:
        result["error"] = "Connection timeout - device unreachable or SSH port not open"
    except NetmikoAuthenticationException:
        result["error"] = "Authentication failed - wrong username or password"
    except Exception as e:
        result["error"] = str(e)
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass

    return result


@router.get("")
def config_push_page(request: Request, db: Session = Depends(get_db),
                     current_user=Depends(require_auth)):
    """Render the config push page with device list."""
    devices = db.query(Device).order_by(Device.ip).all()
    return templates.TemplateResponse(request, "config_push.html", {
        "devices": devices,
        "mode": "input",
    })


@router.post("/preview")
async def config_push_preview(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
    device_ids: list[int] = Form(...),
    config_commands: str = Form(default=""),
    config_file: UploadFile | None = None,
):
    """Preview: parse commands and show confirmation page."""
    commands_text = config_commands

    # If a file was uploaded, read it
    if config_file and config_file.filename:
        content = await config_file.read()
        if len(content) > MAX_FILE_SIZE:
            devices = db.query(Device).order_by(Device.ip).all()
            return templates.TemplateResponse(request, "config_push.html", {
                "devices": devices,
                "mode": "input",
                "error": f"File too large (max {MAX_FILE_SIZE // 1024 // 1024}MB)",
            })
        commands_text = content.decode("utf-8", errors="replace")

    if not commands_text.strip():
        devices = db.query(Device).order_by(Device.ip).all()
        return templates.TemplateResponse(request, "config_push.html", {
            "devices": devices,
            "mode": "input",
            "error": "Please enter configuration commands or upload a file",
        })

    if not device_ids:
        devices = db.query(Device).order_by(Device.ip).all()
        return templates.TemplateResponse(request, "config_push.html", {
            "devices": devices,
            "mode": "input",
            "error": "Please select at least one device",
        })

    # Parse commands - split by newlines, strip blanks, skip comments
    commands = [line.rstrip() for line in commands_text.splitlines()
                if line.strip() and not line.strip().startswith("#")]

    if not commands:
        devices = db.query(Device).order_by(Device.ip).all()
        return templates.TemplateResponse(request, "config_push.html", {
            "devices": devices,
            "mode": "input",
            "error": "No valid commands found (empty after parsing)",
        })

    # Load selected devices
    selected_devices = db.query(Device).filter(Device.id.in_(device_ids)).order_by(Device.ip).all()

    if not selected_devices:
        devices = db.query(Device).order_by(Device.ip).all()
        return templates.TemplateResponse(request, "config_push.html", {
            "devices": devices,
            "mode": "input",
            "error": "No valid devices selected",
        })

    return templates.TemplateResponse(request, "config_push.html", {
        "devices": db.query(Device).order_by(Device.ip).all(),
        "mode": "preview",
        "selected_devices": selected_devices,
        "commands": commands,
        "commands_text": commands_text,  # raw text for hidden form field
        "device_ids": ",".join(str(did) for did in device_ids),
    })


@router.post("/execute")
async def config_push_execute(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
    device_ids_str: str = Form(...),
    commands_text: str = Form(...),
):
    """Execute config push on selected devices."""
    # Parse device IDs
    try:
        device_ids = [int(x.strip()) for x in device_ids_str.split(",") if x.strip()]
    except ValueError:
        return templates.TemplateResponse(request, "config_push.html", {
            "devices": db.query(Device).order_by(Device.ip).all(),
            "mode": "input",
            "error": "Invalid device selection",
        })

    if not device_ids:
        return templates.TemplateResponse(request, "config_push.html", {
            "devices": db.query(Device).order_by(Device.ip).all(),
            "mode": "input",
            "error": "No devices selected",
        })

    # Parse commands
    commands = [line.rstrip() for line in commands_text.splitlines()
                if line.strip() and not line.strip().startswith("#")]

    if not commands:
        return templates.TemplateResponse(request, "config_push.html", {
            "devices": db.query(Device).order_by(Device.ip).all(),
            "mode": "input",
            "error": "No valid commands",
        })

    # Load devices
    selected_devices = db.query(Device).filter(Device.id.in_(device_ids)).order_by(Device.ip).all()

    if not selected_devices:
        return templates.TemplateResponse(request, "config_push.html", {
            "devices": db.query(Device).order_by(Device.ip).all(),
            "mode": "input",
            "error": "Devices not found",
        })

    # Execute push sequentially
    results = []
    for dev in selected_devices:
        r = _push_to_device(dev, commands)
        results.append(r)
        _save_push_run(db, dev, commands, r["output"], r["success"], r.get("error"))

    success_count = sum(1 for r in results if r["success"])
    fail_count = len(results) - success_count

    return templates.TemplateResponse(request, "config_push.html", {
        "devices": db.query(Device).order_by(Device.ip).all(),
        "mode": "result",
        "results": results,
        "commands": commands,
        "success_count": success_count,
        "fail_count": fail_count,
        "total": len(results),
    })
