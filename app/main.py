from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
import os
from app.db import engine, Base

from app.api import orders as orders_router

app = FastAPI(title="OrderOps API (Rewrite)")

FRONTEND_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "").split(",") if o.strip()]
FRONTEND_REGEX = os.getenv("FRONTEND_ORIGIN_REGEX") or None
if not FRONTEND_ORIGINS and not FRONTEND_REGEX:
    FRONTEND_ORIGINS = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_origin_regex=FRONTEND_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_files_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "files"))
os.makedirs(_files_dir, exist_ok=True)
app.mount("/files", StaticFiles(directory=_files_dir), name="files")

@app.on_event("startup")
def on_startup():
    # Create all tables (no migrations necessary for empty DB)
    Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(orders_router.router)
