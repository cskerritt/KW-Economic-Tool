"""Generic save / export / case-listing routes shared by all modules.

Each module's calculate response embeds the canonical input dict as JSON, so
save and export are stateless: they re-receive the inputs, recompute through the
single shared compute path, and either persist or render a file.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from app.auth import require_user
from app.compute import MODULES, compute, summarize
from app.config import settings
from app.deps import get_store
from app.exporting import export_result
from storage import CaseStore

router = APIRouter(tags=["persistence"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)

_MODULE_LABEL = {
    "earnings": "Economic loss",
    "lcp": "Life care plan",
    "lhhs": "Loss of household services",
}


def _check_module(module: str) -> None:
    if module not in MODULES:
        raise HTTPException(status_code=404, detail="Unknown module")


@router.post("/{module}/save", response_class=HTMLResponse)
def save_case(
    module: str,
    request: Request,
    user: str = Depends(require_user),
    store: CaseStore = Depends(get_store),
    title: str = Form(...),
    inputs_json: str = Form(...),
    case_id: int = Form(0),
):
    _check_module(module)
    inputs = json.loads(inputs_json)
    summary = summarize(module, compute(module, inputs))
    if case_id:
        store.update(case_id, title=title, inputs=inputs, summary=summary)
        saved_id = case_id
    else:
        saved_id = store.save(module, title, inputs, summary)
    return templates.TemplateResponse(
        request,
        "_saved.html",
        {"case_id": saved_id, "title": title, "module": module},
    )


@router.post("/{module}/export")
def export_case(
    module: str,
    user: str = Depends(require_user),
    inputs_json: str = Form(...),
    fmt: str = Form("native"),
):
    _check_module(module)
    inputs = json.loads(inputs_json)
    result = compute(module, inputs)
    content, filename, media_type = export_result(
        module,
        result,
        fmt=fmt,
        inputs=inputs,
        firm=settings.report_firm,
        author=settings.report_author,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/cases", response_class=HTMLResponse)
def list_cases(
    request: Request,
    user: str = Depends(require_user),
    store: CaseStore = Depends(get_store),
):
    cases = store.list()
    return templates.TemplateResponse(
        request,
        "cases.html",
        {"user": user, "cases": cases,
         "labels": _MODULE_LABEL},
    )


@router.post("/cases/{case_id}/delete", response_class=HTMLResponse)
def delete_case(
    case_id: int,
    request: Request,
    user: str = Depends(require_user),
    store: CaseStore = Depends(get_store),
):
    store.delete(case_id)
    cases = store.list()
    return templates.TemplateResponse(
        request,
        "_cases_table.html",
        {"cases": cases, "labels": _MODULE_LABEL},
    )
