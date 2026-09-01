"""FastAPI entry point for the SAT-SA API."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.models import Alert
from app.routers import analytics, ingestion

ALLOWED_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://localhost:3000",
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create all tables on startup if they don't already exist."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="SAT-SA API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health(db: Session = Depends(get_db)) -> dict[str, object]:
    """Report API liveness and the current number of ingested alerts."""
    alert_count = db.scalar(select(func.count()).select_from(Alert))
    return {"status": "ok", "alert_count": alert_count}


app.include_router(ingestion.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
