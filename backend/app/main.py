from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI(title="Project Management MVP Backend")

STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_HTML_PATH = STATIC_DIR / "index.html"


@app.get("/api/health")
def get_health() -> dict[str, str]:
    return {"status": "ok", "service": "pm-backend"}


@app.get("/")
def get_index() -> FileResponse:
    return FileResponse(INDEX_HTML_PATH)
