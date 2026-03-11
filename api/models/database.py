"""データベースセッション管理"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(DATABASE_DIR, 'dining.db')}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    # Pool settings for concurrent background workers.
    # pool_size=10: allow up to 10 concurrent SQLAlchemy connections (image gen runs
    #   up to 3 parallel workers, each opens its own SessionLocal).
    # max_overflow=5: allow 5 extra connections under burst load before blocking.
    # pool_timeout=30: wait up to 30 s for a connection before raising (instead of 30 s default).
    pool_size=10,
    max_overflow=5,
    pool_timeout=30,
    pool_pre_ping=True,
)

# Enable WAL mode so background worker writes don't block API reads.
# This is applied once per new connection, which is idempotent and safe.
@event.listens_for(engine, "connect")
def _set_wal_mode(dbapi_conn, _connection_record):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA synchronous=NORMAL")
    # busy_timeout=10000: wait up to 10 s when the DB is locked by a concurrent
    # writer (image generation writes status while the API reads storyboard data).
    # Increased from 5 s to handle bursts from parallel image workers.
    dbapi_conn.execute("PRAGMA busy_timeout=10000")
    # cache_size=-32000: 32 MB page cache per connection for faster reads.
    dbapi_conn.execute("PRAGMA cache_size=-32000")
    # temp_store=MEMORY: use RAM for temporary tables (sorting, GROUP BY).
    dbapi_conn.execute("PRAGMA temp_store=MEMORY")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """リクエストごとのDBセッションを提供"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _add_column_if_missing(conn, table: str, column: str, col_type: str) -> None:
    """SQLiteにカラムが存在しない場合のみ ADD COLUMN を実行する（安全なマイグレーション）"""
    try:
        result = conn.execute(text(f"PRAGMA table_info({table})"))
        existing = {row[1] for row in result}
        if column not in existing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
    except Exception as e:
        # カラムが既に存在する場合などは無視
        pass


def init_db():
    """テーブルを作成（新カラムのマイグレーションも実行）"""
    from api.models.schemas import (  # noqa: F401
        Content,
        Timeline,
        TimelineItem,
        BirthdayReservation,
        PlaybackLog,
        CourseDish,
        DayThemeModel,
        ProjectionConfig,
        Storyboard,
        StoryboardScene,
        AppSetting,
        EventLog,
        GenerationMetrics,
        Show,
        ShowCue,
        Reservation,
        TableSession,
        CourseEvent,
    )
    Base.metadata.create_all(bind=engine)

    # ── スキーママイグレーション ─────────────────────────────────
    # 絵コンテ方式への移行: 新カラムを既存DBに追加する
    with engine.connect() as conn:
        # storyboard_scenes: 絵コンテ用新フィールド
        _add_column_if_missing(conn, "storyboard_scenes", "scene_title", "VARCHAR")
        _add_column_if_missing(conn, "storyboard_scenes", "mood", "VARCHAR")
        _add_column_if_missing(conn, "storyboard_scenes", "camera_angle", "VARCHAR")

        # storyboards: style_reference / style_seed for fal.ai consistency
        _add_column_if_missing(conn, "storyboards", "style_reference_path", "TEXT")
        _add_column_if_missing(conn, "storyboards", "style_seed", "INTEGER")

        # storyboards: day_of_week / theme を nullable にする
        # SQLiteは既存カラムのNOT NULL制約を変更できないため、テーブル再作成で対応
        try:
            result = conn.execute(text(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='storyboards'"
            ))
            row = result.fetchone()
            if row and row[0] and "NOT NULL" in row[0]:
                # day_of_weekまたはthemeにNOT NULLが残っている場合にマイグレーション
                needs_migration = False
                for col_check in ["day_of_week", "theme"]:
                    if f'"{col_check}" VARCHAR NOT NULL' in row[0] or f'{col_check} VARCHAR NOT NULL' in row[0]:
                        needs_migration = True
                        break
                if needs_migration:
                    conn.execute(text("ALTER TABLE storyboards RENAME TO _storyboards_old"))
                    conn.execute(text("""
                        CREATE TABLE storyboards (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            title VARCHAR NOT NULL DEFAULT '新しい台本',
                            day_of_week VARCHAR,
                            theme VARCHAR,
                            mode VARCHAR NOT NULL DEFAULT 'unified',
                            provider VARCHAR NOT NULL DEFAULT 'runway',
                            status VARCHAR NOT NULL DEFAULT 'draft',
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.execute(text("""
                        INSERT INTO storyboards (id, title, day_of_week, theme, mode, provider, status, created_at, updated_at)
                        SELECT id, COALESCE(title, '新しい台本'), day_of_week, theme, mode, provider, status, created_at, updated_at
                        FROM _storyboards_old
                    """))
                    conn.execute(text("DROP TABLE _storyboards_old"))
        except Exception as e:
            print(f"[DB Migration] storyboards nullable migration: {e}")

        conn.commit()

    # ── スタートアップリカバリ ─────────────────────────────────
    # サーバーがクラッシュまたは強制終了された場合、生成中のシーンが
    # "generating" 状態のまま残る可能性がある。起動時に "failed" にリセットして
    # UI が無限ローディングにならないようにする。
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "UPDATE storyboard_scenes SET image_status = 'failed' WHERE image_status = 'generating'"
            ))
            img_reset = result.rowcount
            result = conn.execute(text(
                "UPDATE storyboard_scenes SET video_status = 'failed' WHERE video_status = 'generating'"
            ))
            vid_reset = result.rowcount
            # ストーリーボードのステータスも同様にリカバリ
            conn.execute(text(
                "UPDATE storyboards SET status = 'images_ready' WHERE status = 'images_generating'"
            ))
            conn.execute(text(
                "UPDATE storyboards SET status = 'video_ready' WHERE status = 'video_generating'"
            ))
            conn.commit()
            if img_reset or vid_reset:
                import logging
                logging.getLogger(__name__).warning(
                    "[Startup Recovery] Reset %d image(s) and %d video(s) stuck in 'generating' state.",
                    img_reset, vid_reset,
                )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("[Startup Recovery] Failed: %s", e)
