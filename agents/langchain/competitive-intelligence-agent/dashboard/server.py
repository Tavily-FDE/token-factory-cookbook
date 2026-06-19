"""FastAPI dashboard server for competitive-intelligence fact ledgers.

Read-only web review board over `output/companies/<uuid>/facts.yaml` and its
sibling `company.json` / `verification-queue.md`. Phosphor-on-black aesthetic
inherited from `facts_viewer.py`.

Run:
    uv run python -m dashboard.server
    # or
    uv run uvicorn dashboard.server:app --reload --port 8000

API:
    GET /                                 → dashboard SPA
    GET /api/health                       → {status: ok}
    GET /api/companies                    → [{uuid, name, date_researched, fact_count}]
    GET /api/companies/{uuid}             → {uuid, name, date_researched, facts: [...]}
    GET /api/companies/{uuid}/verification-queue  → markdown text
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent          # agent root
OUTPUT_DIR = ROOT / "output"
COMPANIES_DIR = OUTPUT_DIR / "companies"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="CI Dashboard", version="0.1.0")


# ---------------------------------------------------------------------------
# Data loaders — mirrored from facts_viewer.py
# ---------------------------------------------------------------------------

def _load_company_directory(cdir: Path) -> dict[str, Any]:
    facts_path = cdir / "facts.yaml"
    company_path = cdir / "company.json"
    if not facts_path.exists():
        raise FileNotFoundError(f"no facts.yaml in {cdir}")

    with facts_path.open("r", encoding="utf-8") as f:
        facts = yaml.safe_load(f) or []
    facts = [f for f in facts if isinstance(f, dict)]

    name = cdir.name
    uuid = cdir.name
    date_researched = ""
    research_status = ""
    scope = ""
    if company_path.exists():
        try:
            meta = json.loads(company_path.read_text(encoding="utf-8"))
            name = meta.get("name", name)
            uuid = meta.get("uuid", uuid)
            date_researched = meta.get("date_researched", "")
            research_status = meta.get("research_status", "")
            scope = meta.get("scope", "")
        except Exception:  # noqa: BLE001
            pass

    company_slug = name.lower()
    return {
        "uuid": uuid,
        "name": name,
        "slug": company_slug,
        "scope": scope,
        "date_researched": date_researched,
        "research_status": research_status,
        "fact_count": len(facts),
        "facts": facts,
    }


def _list_companies() -> list[dict[str, Any]]:
    """Lightweight index — no fact payloads."""
    out: list[dict[str, Any]] = []
    if not COMPANIES_DIR.exists():
        return out
    for cdir in sorted(COMPANIES_DIR.iterdir()):
        if not cdir.is_dir():
            continue
        try:
            data = _load_company_directory(cdir)
        except FileNotFoundError:
            continue
        out.append({
            "uuid": data["uuid"],
            "name": data["name"],
            "slug": data["slug"],
            "date_researched": data["date_researched"],
            "fact_count": data["fact_count"],
        })
    return out


def _company_uuids() -> set[str]:
    return {c["uuid"] for c in _list_companies()}


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/companies")
def list_companies() -> list[dict[str, Any]]:
    return _list_companies()


@app.get("/api/companies/{uuid}")
def get_company(uuid: str) -> dict[str, Any]:
    cdir = COMPANIES_DIR / uuid
    if not cdir.is_dir():
        raise HTTPException(status_code=404, detail=f"unknown company uuid: {uuid}")
    try:
        return _load_company_directory(cdir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/companies/{uuid}/verification-queue", response_class=PlainTextResponse)
def get_verification_queue(uuid: str) -> str:
    cdir = COMPANIES_DIR / uuid
    vq_path = cdir / "verification-queue.md"
    if not vq_path.exists():
        raise HTTPException(status_code=404, detail="no verification-queue.md for this company")
    return vq_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Static SPA — index.html served at root, assets from /static
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=500, detail="dashboard/static/index.html missing")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "dashboard.server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(Path(__file__).resolve().parent)],
    )
