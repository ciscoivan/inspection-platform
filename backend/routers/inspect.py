import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from netmiko import ConnectHandler
from ..database import get_db, SessionLocal
from ..models import Device, InspectionRun, AlertRule, CustomCommand, now_cst
from ..routers.auth import require_auth
from ..crypto import decrypt_password

router = APIRouter(tags=["inspect"])


# 巡检进度追踪: {run_id: {"total": N, "done": N, "devices": {ip: status}}}
_progress: dict[str, dict] = {}
_progress_lock = threading.Lock()
MAX_WORKERS = 10  # 最多同时巡检 5 台设备


def _inspect_one(dev_id: int, run_id: str):
    """单设备巡检 — 在线程池中执行。"""
    from ..engine.inspector import run_single_device

    db = SessionLocal()
    try:
        dev = db.query(Device).filter(Device.id == dev_id).first()
        if not dev:
            with _progress_lock:
                p = _progress.get(run_id)
                if p is not None:
                    p["done"] += 1
            return

        device_info = {
            "ip": dev.ip, "device_type": dev.device_type,
            "username": dev.username, "password": decrypt_password(dev.password),
            "port": dev.port,
        }

        # 查询该平台的自定义命令
        custom_cmds = (
            db.query(CustomCommand)
            .filter(
                (CustomCommand.device_type == dev.device_type) | (CustomCommand.device_type == "all"),
                CustomCommand.enabled == True,
            )
            .all()
        )

        try:
            result = run_single_device(device_info)
            # 注入自定义命令到巡检结果
            if custom_cmds and result.get("sections"):
                import json as _json
                custom_outputs = {}
                conn = None
                try:
                    conn = ConnectHandler(
                        device_type=dev.device_type, host=dev.ip,
                        username=dev.username, password=decrypt_password(dev.password), port=dev.port,
                        conn_timeout=15, auth_timeout=15, banner_timeout=15,
                    )
                    for c in custom_cmds:
                        try:
                            out = conn.send_command_timing(c.command, read_timeout=30, delay_factor=2)
                            custom_outputs[c.description or c.command] = out
                        except Exception:
                            custom_outputs[c.description or c.command] = "[错误] 命令执行失败"
                except Exception:
                    for c in custom_cmds:
                        custom_outputs[c.description or c.command] = "[错误] SSH 连接失败"
                finally:
                    if conn:
                        try:
                            conn.disconnect()
                        except Exception:
                            pass
                if custom_outputs:
                    result["sections"]["自定义命令"] = custom_outputs
                    result["raw_data"] = _json.dumps(result["sections"], ensure_ascii=False)
        except Exception as e:
            result = {
                "ip": dev.ip, "hostname": "N/A", "cpu": "N/A", "memory": "N/A",
                "uptime": "N/A", "status": "error", "error": str(e),
                "raw_data": "{}", "sections": {},
            }

        run = InspectionRun(
            device_id=dev.id, timestamp=now_cst(),
            cpu=result.get("cpu", "N/A"), memory=result.get("memory", "N/A"),
            uptime=result.get("uptime", "N/A"), hostname=result.get("hostname", "N/A"),
            status=result.get("status", "unknown"), error=result.get("error"),
            raw_data=result.get("raw_data", "{}"),
            config_backup=result.get("config_backup"),
        )
        db.add(run)
        dev.status = result.get("status", "unknown")
        dev.hostname = result.get("hostname", dev.hostname)

        # 告警检查
        rules = db.query(AlertRule).filter(
            (AlertRule.device_id == dev.id) | (AlertRule.device_id.is_(None))
        ).filter(AlertRule.enabled == True).all()

        alerts = []
        for rule in rules:
            try:
                val = float(result.get("cpu", "0").rstrip("%")) if rule.metric == "cpu" \
                    else float(result.get("memory", "0").rstrip("%"))
                if (rule.operator == ">" and val > rule.threshold) or \
                   (rule.operator == ">=" and val >= rule.threshold):
                    alerts.append(f"{rule.metric.upper()} {val}% {rule.operator} {rule.threshold}%")
            except (ValueError, KeyError):
                pass

        db.commit()

        # DB 提交成功后再更新进度
        with _progress_lock:
            p = _progress.get(run_id)
            if p is not None:
                p["done"] += 1
                dev_progress = {
                    "cpu": result.get("cpu", "N/A"),
                    "memory": result.get("memory", "N/A"),
                    "status": result.get("status", "unknown"),
                }
                if alerts:
                    dev_progress["alerts"] = alerts
                p["devices"][dev.ip] = dev_progress

    finally:
        db.close()


def _run_inspection_sync(run_id: str, device_ids: list[int]):
    """批量巡检 — 线程池并发执行, 每设备超时 300s。"""
    workers = min(MAX_WORKERS, len(device_ids))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_inspect_one, did, run_id): did for did in device_ids}
        for f in futures:
            try:
                f.result(timeout=300)  # 5 分钟超时
            except Exception:
                pass  # 超时/异常已在 _inspect_one 内部处理, 这里仅防永久挂起
    # 保留进度 10 秒供前端轮询, 之后清理
    threading.Timer(10, lambda: _progress.pop(run_id, None)).start()


@router.post("/inspect")
def trigger_inspection(
    device_id: int | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_auth),
):
    """触发巡检。device_id=None 表示全量，?device_id=N 表示单设备。"""
    run_id = str(uuid.uuid4())[:8]

    if device_id is not None:
        devices = db.query(Device).filter(Device.id == device_id).all()
    else:
        devices = db.query(Device).all()

    if not devices:
        return {"error": "没有可巡检的设备"}

    device_ids = [d.id for d in devices]
    # 初始化进度
    _progress[run_id] = {
        "total": len(device_ids),
        "done": 0,
        "devices": {d.ip: {"cpu": "...", "memory": "...", "status": "等待中"} for d in devices},
    }

    threading.Thread(target=_run_inspection_sync, args=(run_id, device_ids), daemon=True).start()
    return {"run_id": run_id, "device_count": len(device_ids)}


@router.get("/inspect/status/{run_id}")
def inspect_status(run_id: str, current_user=Depends(require_auth)):
    """轮询巡检进度。"""
    p = _progress.get(run_id)
    if not p:
        return {"done": True, "progress": None}
    # 检查是否全部完成
    all_done = p["done"] >= p["total"]
    return {"done": all_done, "progress": p}
