"""Local legacy-style credit union servicing console."""

from __future__ import annotations

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.data import MEMBERS

app = FastAPI(title="Community Credit Union")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def landing(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/console", response_class=HTMLResponse)
def console(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "member_detail.html", {"member": None})


@app.post("/lookup", response_class=HTMLResponse)
def lookup(request: Request, member_number: str = Form(...)) -> HTMLResponse:
    number = member_number.strip()
    if number == "40000":
        # Deterministic blocker used by the handoff demo.
        return templates.TemplateResponse(request, "member_detail.html", {"blocker": True, "member": None})
    if number == "30000":
        # A known transient condition; the retry demo can submit again.
        return templates.TemplateResponse(request, "member_detail.html", {"transient": True, "member": None})
    if number == "20001":
        return templates.TemplateResponse(request, "member_detail.html", {"outcome": "PERMISSION_DENIED", "member": None})
    if number == "99999" or number not in MEMBERS:
        return templates.TemplateResponse(request, "member_detail.html", {"outcome": "MEMBER_NOT_FOUND", "member": None})
    member = MEMBERS[number]
    outcome = "NO_SAVINGS_ACCOUNT" if member.savings is None else None
    return templates.TemplateResponse(request, "member_detail.html", {"member": member, "outcome": outcome})
