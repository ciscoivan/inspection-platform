import csv,io,json
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy.orm import Session, joinedload
from ..database import get_db
from ..models import InspectionRun
from ..templating import templates
from ..routers.auth import require_auth

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/api")
def list_runs(device_id: int|None=None, db: Session=Depends(get_db), current_user=Depends(require_auth)):
    q = db.query(InspectionRun).order_by(InspectionRun.timestamp.desc())
    if device_id: q = q.filter(InspectionRun.device_id == device_id)
    return q.limit(100).all()

@router.get("")
def reports_page(request: Request, db: Session=Depends(get_db)):
    runs = db.query(InspectionRun).options(joinedload(InspectionRun.device)).order_by(InspectionRun.timestamp.desc()).limit(50).all()
    return templates.TemplateResponse(request, "reports.html", {"runs": runs})

@router.get("/export/csv")
def export_csv(db: Session=Depends(get_db)):
    runs = db.query(InspectionRun).order_by(InspectionRun.timestamp.desc()).limit(500).all()
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["ID","time","ip","hostname","cpu","mem","uptime","status"])
    for r in runs:
        w.writerow([r.id, str(r.timestamp), r.device.ip if r.device else "?", r.hostname, r.cpu, r.memory, r.uptime, r.status])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=reports.csv"})

@router.delete("/api/{run_id}")
def delete_run(run_id: int, db: Session=Depends(get_db), current_user=Depends(require_auth)):
    r = db.query(InspectionRun).filter(InspectionRun.id == run_id).first()
    if r: db.delete(r); db.commit()
    return {"ok": True}

@router.get("/{run_id}")
def report_detail(run_id: int, request: Request, db: Session=Depends(get_db)):
    run = db.query(InspectionRun).filter(InspectionRun.id == run_id).first()
    if not run: return templates.TemplateResponse(request, "base.html", {})
    raw = json.loads(run.raw_data) if run.raw_data else {}
    return templates.TemplateResponse(request, "report.html", {"run": run, "sections": raw})

@router.get("/{run_id}/export")
def export_html(run_id: int, db: Session=Depends(get_db)):
    run = db.query(InspectionRun).filter(InspectionRun.id == run_id).first()
    if not run: raise HTTPException(404, "not found")
    raw = json.loads(run.raw_data) if run.raw_data else {}
    sh = ""
    for cat, cmds in raw.items():
        sh += f"<details open><summary>{cat}</summary>"
        for desc, out in cmds.items():
            sh += f"<p>{desc}</p><pre>{out}</pre>"
        sh += "</details>"
    html = f"<html><head><meta charset=utf-8><title>report {run.hostname}</title></head><body><h1>Report #{run.id}</h1><p>{run.timestamp} | {run.hostname}</p><p>CPU:{run.cpu} MEM:{run.memory} UP:{run.uptime}</p>{sh}</body></html>"
    return HTMLResponse(content=html, headers={"Content-Disposition": f"attachment; filename=report_{run_id}.html"})
