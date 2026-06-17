from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router
from backend.app.core.config import get_settings
from backend.app.core.job_store import JobStore

settings = get_settings()
JobStore(settings)

app = FastAPI(title="AI 3D Service MVP", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://0.0.0.0:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://0.0.0.0:8080",
    ],
    # Local dev runs through a static frontend on 8080, Vite on 5173,
    # and sometimes via a LAN IP or 0.0.0.0 binding. Allow those browser
    # origins so demo-example fetches and viewer asset loads do not fail.
    allow_origin_regex=r"^https?://("
    r"localhost|127\.0\.0\.1|0\.0\.0\.0|"
    r"10(?:\.\d{1,3}){3}|"
    r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2}|"
    r"192\.168(?:\.\d{1,3}){2}"
    r")(?::\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.mount("/storage", StaticFiles(directory=settings.storage_root), name="storage")
app.mount("/assets", StaticFiles(directory=settings.project_root / "assets"), name="assets")


def _prismscan_html() -> FileResponse:
    html_path = settings.project_root / "frontend" / "prismscan-v2.html"
    return FileResponse(
        html_path,
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/")
def home() -> FileResponse:
    return _prismscan_html()


@app.get("/prismscan-v2.html")
def prismscan_v2() -> FileResponse:
    return _prismscan_html()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
