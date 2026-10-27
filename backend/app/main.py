from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.responses import FileResponse

app = FastAPI(title="Project Management MVP")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
FRONTEND_DIR = STATIC_DIR / "frontend"
FRONTEND_INDEX_FILE = FRONTEND_DIR / "index.html"
FALLBACK_INDEX_FILE = STATIC_DIR / "index.html"


def _safe_file(base_dir: Path, relative_path: str) -> Path | None:
    candidate = (base_dir / relative_path).resolve()
    if not str(candidate).startswith(str(base_dir.resolve())):
        return None
    return candidate if candidate.is_file() else None


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from FastAPI"}


@app.get("/")
def root() -> FileResponse:
    if FRONTEND_INDEX_FILE.exists():
        return FileResponse(FRONTEND_INDEX_FILE)
    return FileResponse(FALLBACK_INDEX_FILE)


@app.get("/{file_path:path}")
def static_files(file_path: str) -> FileResponse:
    if file_path.startswith("api/"):
        raise HTTPException(status_code=404)

    frontend_file = _safe_file(FRONTEND_DIR, file_path)
    if frontend_file:
        return FileResponse(frontend_file)

    fallback_file = _safe_file(STATIC_DIR, file_path)
    if fallback_file:
        return FileResponse(fallback_file)

    if FRONTEND_INDEX_FILE.exists():
        return FileResponse(FRONTEND_INDEX_FILE)

    raise HTTPException(status_code=404)
