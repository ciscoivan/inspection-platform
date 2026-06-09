import difflib
from fastapi import APIRouter, Request, Form, UploadFile
from fastapi.responses import HTMLResponse
from ..templating import templates

router = APIRouter(prefix="/config-compare", tags=["config-compare"])


@router.get("")
def compare_page(request: Request):
    return templates.TemplateResponse(request, "config_compare.html", {})


@router.post("")
async def compare_configs(
    request: Request,
    config_a: str = Form(default=""),
    config_b: str = Form(default=""),
    file_a: UploadFile | None = None,
    file_b: UploadFile | None = None,
):
    """比较上传或粘贴的两份配置。"""
    # 优先使用上传文件, 否则使用粘贴文本
    if file_a and file_a.filename:
        config_a = (await file_a.read()).decode("utf-8", errors="replace")
    if file_b and file_b.filename:
        config_b = (await file_b.read()).decode("utf-8", errors="replace")

    if not config_a or not config_b:
        return templates.TemplateResponse(request, "config_compare.html", {"error": "请上传或粘贴两份配置内容"})

    # 生成 unified diff
    a_lines = config_a.splitlines(keepends=True)
    b_lines = config_b.splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        a_lines, b_lines,
        fromfile="配置 A", tofile="配置 B",
        lineterm=""
    ))

    # 生成 HTML 并排对比
    differ = difflib.HtmlDiff(wrapcolumn=90, tabsize=4)
    html_diff = differ.make_table(
        a_lines, b_lines,
        fromdesc="配置 A", todesc="配置 B",
        context=True, numlines=3
    )

    return templates.TemplateResponse(request, "config_compare.html", {"diff": diff,
        "html_diff": html_diff,
        "lines_a": len(a_lines),
        "lines_b": len(b_lines),
        "lines_diff": sum(1 for d in diff if d.startswith(("-", "+")) and not d.startswith(("---", "+++")))})
