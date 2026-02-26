"""イマーシブダイニング プロジェクションシステム – FastAPI エントリーポイント"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.models.database import init_db
from api.routers import content, timeline, birthday, projection, generation, course, theme, storyboard, settings, character
from api.routers import show_control, reservation, analytics, table_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """起動時にDBを初期化"""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Immersive Dining Projection API",
    description="プロジェクションマッピングを使ったイマーシブダイニング体験の制御API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration.
# allow_origins=["*"] with allow_credentials=True is rejected by browsers
# (the spec forbids wildcard + credentials). Use explicit origin list instead.
# The frontend runs on port 3001 in development; add more origins as needed.
_CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
app.include_router(content.router)
app.include_router(timeline.router)
app.include_router(birthday.router)
app.include_router(projection.router)
app.include_router(generation.router)
app.include_router(course.router)
app.include_router(theme.router)
app.include_router(storyboard.router)
app.include_router(settings.router)
app.include_router(character.router)
app.include_router(show_control.router)
app.include_router(reservation.router)
app.include_router(analytics.router)
app.include_router(table_session.router)

# プレビュー画像の静的ファイル配信
_previews_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "touchdesigner", "content", "previews",
)
os.makedirs(_previews_dir, exist_ok=True)
app.mount("/static/previews", StaticFiles(directory=_previews_dir), name="previews")


@app.get("/")
def root():
    return {"message": "Immersive Dining Projection API", "version": "0.1.0"}
