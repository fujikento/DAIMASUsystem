"""SQLAlchemyモデル & Pydanticスキーマ"""

from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from api.models.database import Base


# ─── SQLAlchemy ORM Models ───────────────────────────────────────────────────


class Content(Base):
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)           # video / image / shader
    theme = Column(String, nullable=False)           # 曜日テーマ (monday_ocean 等)
    file_path = Column(Text, nullable=False)
    duration = Column(Float, nullable=True)          # 秒
    resolution = Column(String, nullable=True)       # "1920x1080" 等
    created_at = Column(DateTime, server_default=func.now())

    timeline_items = relationship("TimelineItem", back_populates="content")


class Timeline(Base):
    __tablename__ = "timelines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    course_type = Column(String, nullable=False)     # lunch / dinner / special
    day_of_week = Column(String, nullable=False)     # monday, tuesday, ...
    created_at = Column(DateTime, server_default=func.now())

    items = relationship("TimelineItem", back_populates="timeline", cascade="all, delete-orphan")
    playback_logs = relationship("PlaybackLog", back_populates="timeline")


class TimelineItem(Base):
    __tablename__ = "timeline_items"

    id = Column(Integer, primary_key=True, index=True)
    timeline_id = Column(Integer, ForeignKey("timelines.id"), nullable=False)
    content_id = Column(Integer, ForeignKey("contents.id"), nullable=False)
    start_time = Column(Float, nullable=False)       # 秒 (タイムライン内のオフセット)
    duration = Column(Float, nullable=False)
    zone = Column(String, nullable=False)            # wall_left / wall_right / ceiling / table
    transition = Column(String, default="crossfade") # crossfade / cut / fade_black
    sort_order = Column(Integer, default=0)

    timeline = relationship("Timeline", back_populates="items")
    content = relationship("Content", back_populates="timeline_items")


class BirthdayReservation(Base):
    __tablename__ = "birthday_reservations"

    id = Column(Integer, primary_key=True, index=True)
    guest_name = Column(String, nullable=False)
    photo_path = Column(Text, nullable=True)
    character_video_path = Column(Text, nullable=True)
    reservation_date = Column(Date, nullable=False)
    status = Column(String, default="pending")       # pending → processing → ready → played
    created_at = Column(DateTime, server_default=func.now())


class CourseDish(Base):
    __tablename__ = "course_dishes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)             # 表示名（例: 前菜 - 鮮魚のカルパッチョ）
    course_key = Column(String, nullable=False)        # 生成キー (welcome, appetizer, soup, main, dessert, or custom)
    description = Column(Text, nullable=True)          # 料理の説明（AI映像生成のコンテキストに使用）
    day_of_week = Column(String, nullable=False)       # monday, tuesday, ...
    sort_order = Column(Integer, default=0)            # コース内の順番
    prompt_hint = Column(Text, nullable=True)          # 映像生成に使う追加プロンプトヒント
    created_at = Column(DateTime, server_default=func.now())


class DayThemeModel(Base):
    __tablename__ = "day_themes"

    id = Column(Integer, primary_key=True, index=True)
    day_of_week = Column(String, unique=True, nullable=False)  # monday, tuesday, ...
    name_ja = Column(String, nullable=False)
    name_en = Column(String, nullable=False)
    color = Column(String, nullable=False)
    icon = Column(String, nullable=False)
    bg_gradient = Column(String, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PlaybackLog(Base):
    __tablename__ = "playback_logs"

    id = Column(Integer, primary_key=True, index=True)
    timeline_id = Column(Integer, ForeignKey("timelines.id"), nullable=False)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    table_id = Column(String, nullable=True)

    timeline = relationship("Timeline", back_populates="playback_logs")


class ProjectionConfig(Base):
    __tablename__ = "projection_config"

    id = Column(Integer, primary_key=True, index=True)
    pj_width = Column(Integer, nullable=False, default=1920)
    pj_height = Column(Integer, nullable=False, default=1200)
    pj_count = Column(Integer, nullable=False, default=3)
    blend_overlap = Column(Integer, nullable=False, default=120)
    zone_count = Column(Integer, nullable=False, default=4)
    table_width_mm = Column(Integer, nullable=False, default=8120)
    table_height_mm = Column(Integer, nullable=False, default=600)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── Pydantic Response / Request Schemas ─────────────────────────────────────


# Content
class ContentBase(BaseModel):
    name: str
    type: str
    theme: str
    duration: Optional[float] = None
    resolution: Optional[str] = None


class ContentCreate(ContentBase):
    pass


class ContentResponse(ContentBase):
    id: int
    file_path: str
    created_at: datetime

    model_config = {"from_attributes": True}


# Timeline
class TimelineItemBase(BaseModel):
    content_id: int
    start_time: float
    duration: float
    zone: str
    transition: str = "crossfade"
    sort_order: int = 0


class TimelineItemCreate(TimelineItemBase):
    pass


class TimelineItemResponse(TimelineItemBase):
    id: int
    content: Optional[ContentResponse] = None

    model_config = {"from_attributes": True}


class TimelineBase(BaseModel):
    name: str
    course_type: str
    day_of_week: str


class TimelineCreate(TimelineBase):
    pass


class TimelineResponse(TimelineBase):
    id: int
    created_at: datetime
    items: list[TimelineItemResponse] = []

    model_config = {"from_attributes": True}


class TimelineListResponse(TimelineBase):
    """アイテムなしの一覧用"""
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# Birthday
class BirthdayBase(BaseModel):
    guest_name: str
    reservation_date: date


class BirthdayCreate(BirthdayBase):
    pass


class BirthdayResponse(BirthdayBase):
    id: int
    photo_path: Optional[str] = None
    character_video_path: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BirthdayStatusUpdate(BaseModel):
    status: str  # pending / processing / ready / played


# Playback Log
class PlaybackLogResponse(BaseModel):
    id: int
    timeline_id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    table_id: Optional[str] = None

    model_config = {"from_attributes": True}


# DayTheme
class DayThemeBase(BaseModel):
    day_of_week: str
    name_ja: str
    name_en: str
    color: str
    icon: str
    bg_gradient: str


class DayThemeUpdate(BaseModel):
    name_ja: Optional[str] = None
    name_en: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    bg_gradient: Optional[str] = None


class DayThemeResponse(DayThemeBase):
    id: int
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# CourseDish
class CourseDishBase(BaseModel):
    name: str
    course_key: str
    description: Optional[str] = None
    day_of_week: str
    sort_order: int = 0
    prompt_hint: Optional[str] = None


class CourseDishCreate(CourseDishBase):
    pass


class CourseDishResponse(CourseDishBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectionPlayRequest(BaseModel):
    timeline_id: int
    table_id: Optional[str] = None


class ProjectionTriggerRequest(BaseModel):
    data: Optional[dict] = None


class ProjectionStatusResponse(BaseModel):
    state: str          # idle / playing / paused
    timeline_id: Optional[int] = None
    table_id: Optional[str] = None
    elapsed: float = 0.0
    current_content: Optional[str] = None


# ProjectionConfig
class ProjectionConfigResponse(BaseModel):
    id: int
    pj_width: int
    pj_height: int
    pj_count: int
    blend_overlap: int
    zone_count: int
    table_width_mm: int
    table_height_mm: int
    # computed fields
    full_width: int
    full_height: int
    zone_width: int
    zone_height: int
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProjectionConfigUpdate(BaseModel):
    pj_width: Optional[int] = None
    pj_height: Optional[int] = None
    pj_count: Optional[int] = None
    blend_overlap: Optional[int] = None
    zone_count: Optional[int] = None
    table_width_mm: Optional[int] = None
    table_height_mm: Optional[int] = None


# ─── Storyboard ORM Models ────────────────────────────────────────────────────


class Storyboard(Base):
    __tablename__ = "storyboards"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    day_of_week = Column(String, nullable=True)   # Optional — no longer required
    theme = Column(String, nullable=True)          # Optional — no longer required
    mode = Column(String, nullable=False, default="unified")
    provider = Column(String, nullable=False, default="runway")
    status = Column(String, nullable=False, default="draft")
    # Status: draft → script_ready → images_generating → images_ready → video_generating → video_ready
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    scenes = relationship("StoryboardScene", back_populates="storyboard",
                          cascade="all, delete-orphan",
                          order_by="StoryboardScene.sort_order")


class StoryboardScene(Base):
    __tablename__ = "storyboard_scenes"

    id = Column(Integer, primary_key=True, index=True)
    storyboard_id = Column(Integer, ForeignKey("storyboards.id"), nullable=False)
    course_key = Column(String, nullable=False)
    course_dish_id = Column(Integer, ForeignKey("course_dishes.id"), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)

    # 絵コンテ fields — human-readable scene metadata
    scene_title = Column(String, nullable=True)            # e.g. "海底の楽園"
    scene_description_ja = Column(Text, nullable=True)
    mood = Column(String, nullable=True)                   # calm/dramatic/mysterious/joyful/romantic/energetic/serene/festive
    camera_angle = Column(String, nullable=True)           # bird_eye/wide/close_up/medium/pan/dynamic

    prompt = Column(Text, nullable=False)
    prompt_edited = Column(Text, nullable=True)
    extra_prompt = Column(Text, nullable=True)

    duration_seconds = Column(Integer, nullable=False, default=120)
    transition = Column(String, nullable=False, default="crossfade")
    aspect_ratio = Column(String, nullable=False, default="21:9")

    projection_mode = Column(String, default="unified")    # unified / zone / custom
    target_zones = Column(String, nullable=True)           # "1,2,3,4" or "2,3" etc.
    color_tone = Column(String, default="neutral")         # warm / cool / neutral / vivid
    brightness = Column(String, default="normal")          # dark / normal / bright
    animation_speed = Column(String, default="normal")     # slow / normal / fast
    prompt_modifier = Column(Text, nullable=True)          # free-text prompt addition

    image_status = Column(String, default="pending")
    image_path = Column(Text, nullable=True)
    image_job_id = Column(String, nullable=True)

    video_status = Column(String, default="pending")
    video_path = Column(Text, nullable=True)
    video_job_id = Column(String, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    storyboard = relationship("Storyboard", back_populates="scenes")


# ─── Show / ShowCue ORM Models ────────────────────────────────────────────────


class Show(Base):
    __tablename__ = "shows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    storyboard_id = Column(Integer, ForeignKey("storyboards.id"), nullable=True)
    status = Column(String, default="standby")  # standby/running/paused/completed
    current_cue_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    cues = relationship(
        "ShowCue",
        back_populates="show",
        cascade="all, delete-orphan",
        order_by="ShowCue.sort_order",
    )


class ShowCue(Base):
    __tablename__ = "show_cues"

    id = Column(Integer, primary_key=True, index=True)
    show_id = Column(Integer, ForeignKey("shows.id"), nullable=False)
    cue_number = Column(Float, nullable=False)  # 1.0, 1.5, 2.0 etc
    cue_type = Column(String, nullable=False)   # content/transition/trigger/wait
    target_zones = Column(String, default="all")  # "1,2,3,4" or "all"
    content_path = Column(String, nullable=True)
    transition = Column(String, default="crossfade")
    duration_seconds = Column(Float, default=3.0)
    auto_follow = Column(Boolean, default=False)  # 自動で次に進む
    auto_follow_delay = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)

    show = relationship("Show", back_populates="cues")


# ─── Reservation ORM Model ────────────────────────────────────────────────────


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    guest_name = Column(String, nullable=False)
    guest_email = Column(String, nullable=True)
    guest_phone = Column(String, nullable=True)
    party_size = Column(Integer, nullable=False)
    reservation_date = Column(Date, nullable=False)
    time_slot = Column(String, nullable=False)        # "18:00", "19:30", "21:00"
    table_number = Column(Integer, nullable=True)
    status = Column(String, default="confirmed")     # confirmed/checked_in/seated/completed/cancelled
    special_occasion = Column(String, nullable=True)  # birthday/anniversary/etc
    special_requests = Column(Text, nullable=True)
    theme_override = Column(String, nullable=True)   # テーマ変更希望
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── Reservation Pydantic Schemas ─────────────────────────────────────────────


class ReservationCreate(BaseModel):
    guest_name: str
    guest_email: Optional[str] = None
    guest_phone: Optional[str] = None
    party_size: int
    reservation_date: date
    time_slot: str
    table_number: Optional[int] = None
    special_occasion: Optional[str] = None
    special_requests: Optional[str] = None
    theme_override: Optional[str] = None


class ReservationUpdate(BaseModel):
    guest_name: Optional[str] = None
    guest_email: Optional[str] = None
    guest_phone: Optional[str] = None
    party_size: Optional[int] = None
    reservation_date: Optional[date] = None
    time_slot: Optional[str] = None
    table_number: Optional[int] = None
    status: Optional[str] = None
    special_occasion: Optional[str] = None
    special_requests: Optional[str] = None
    theme_override: Optional[str] = None


class ReservationResponse(BaseModel):
    id: int
    guest_name: str
    guest_email: Optional[str] = None
    guest_phone: Optional[str] = None
    party_size: int
    reservation_date: date
    time_slot: str
    table_number: Optional[int] = None
    status: str
    special_occasion: Optional[str] = None
    special_requests: Optional[str] = None
    theme_override: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CalendarDaySummary(BaseModel):
    date: date
    total: int
    confirmed: int
    checked_in: int
    seated: int
    completed: int
    cancelled: int


# ─── AppSetting ORM Model ─────────────────────────────────────────────────────


class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False, default="")
    label = Column(String, nullable=True)        # Display label (e.g., "Gemini API Key")
    category = Column(String, nullable=True)      # e.g., "api_keys", "paths"
    is_secret = Column(Boolean, nullable=False, default=True)  # Mask value in responses
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ─── AppSetting Pydantic Schemas ───────────────────────────────────────────────


class AppSettingResponse(BaseModel):
    id: int
    key: str
    value: str        # Will be masked if is_secret
    label: Optional[str] = None
    category: Optional[str] = None
    is_secret: bool
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class AppSettingUpdate(BaseModel):
    value: str


# ─── Storyboard Pydantic Schemas ──────────────────────────────────────────────


class StoryboardSceneBase(BaseModel):
    course_key: str
    course_dish_id: Optional[int] = None
    sort_order: int = 0
    # 絵コンテ fields
    scene_title: Optional[str] = None
    scene_description_ja: Optional[str] = None
    mood: Optional[str] = None
    camera_angle: Optional[str] = None
    prompt: str
    prompt_edited: Optional[str] = None
    extra_prompt: Optional[str] = None
    duration_seconds: int = 120
    transition: str = "crossfade"
    aspect_ratio: str = "21:9"
    projection_mode: str = "unified"
    target_zones: Optional[str] = None
    color_tone: str = "neutral"
    brightness: str = "normal"
    animation_speed: str = "normal"
    prompt_modifier: Optional[str] = None


class StoryboardSceneResponse(StoryboardSceneBase):
    id: int
    storyboard_id: int
    image_status: str
    image_path: Optional[str] = None
    video_status: str
    video_path: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    projection_mode: str
    target_zones: Optional[str] = None
    color_tone: str
    brightness: str
    animation_speed: str
    prompt_modifier: Optional[str] = None
    model_config = {"from_attributes": True}


class StoryboardSceneUpdate(BaseModel):
    scene_title: Optional[str] = None
    scene_description_ja: Optional[str] = None
    mood: Optional[str] = None
    camera_angle: Optional[str] = None
    prompt_edited: Optional[str] = None
    extra_prompt: Optional[str] = None
    duration_seconds: Optional[int] = None
    transition: Optional[str] = None
    projection_mode: Optional[str] = None
    target_zones: Optional[str] = None
    color_tone: Optional[str] = None
    brightness: Optional[str] = None
    animation_speed: Optional[str] = None
    prompt_modifier: Optional[str] = None
    course_key: Optional[str] = None


class StoryboardSceneCreate(BaseModel):
    course_key: str = "custom"
    scene_title: Optional[str] = None
    scene_description_ja: Optional[str] = None
    mood: Optional[str] = None
    camera_angle: Optional[str] = None
    prompt: Optional[str] = None  # If not provided, auto-generate
    duration_seconds: int = 120
    transition: str = "crossfade"
    projection_mode: str = "unified"
    target_zones: Optional[str] = None
    color_tone: str = "neutral"
    brightness: str = "normal"
    animation_speed: str = "normal"
    prompt_modifier: Optional[str] = None


class StoryboardCreate(BaseModel):
    title: str = "新しい台本"
    day_of_week: Optional[str] = None   # Optional — no theme lock-in
    theme: Optional[str] = None          # Optional — may be set per-scene
    provider: str = "runway"
    auto_generate_scenes: bool = False   # Default: empty storyboard


class StoryboardResponse(BaseModel):
    id: int
    title: str
    day_of_week: Optional[str] = None
    theme: Optional[str] = None
    mode: str
    provider: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    scenes: list[StoryboardSceneResponse] = []
    model_config = {"from_attributes": True}


class StoryboardListResponse(BaseModel):
    id: int
    title: str
    day_of_week: Optional[str] = None
    theme: Optional[str] = None
    mode: str
    provider: str
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Show / ShowCue Pydantic Schemas ──────────────────────────────────────────


class ShowCueBase(BaseModel):
    cue_number: float
    cue_type: str  # content / transition / trigger / wait
    target_zones: str = "all"
    content_path: Optional[str] = None
    transition: str = "crossfade"
    duration_seconds: float = 3.0
    auto_follow: bool = False
    auto_follow_delay: float = 0.0
    notes: Optional[str] = None
    sort_order: int = 0


class ShowCueCreate(ShowCueBase):
    pass


class ShowCueUpdate(BaseModel):
    cue_number: Optional[float] = None
    cue_type: Optional[str] = None
    target_zones: Optional[str] = None
    content_path: Optional[str] = None
    transition: Optional[str] = None
    duration_seconds: Optional[float] = None
    auto_follow: Optional[bool] = None
    auto_follow_delay: Optional[float] = None
    notes: Optional[str] = None
    sort_order: Optional[int] = None


class ShowCueResponse(ShowCueBase):
    id: int
    show_id: int
    model_config = {"from_attributes": True}


class ShowCreate(BaseModel):
    name: str
    storyboard_id: Optional[int] = None


class ShowResponse(BaseModel):
    id: int
    name: str
    storyboard_id: Optional[int] = None
    status: str
    current_cue_id: Optional[int] = None
    created_at: datetime
    cues: list[ShowCueResponse] = []
    model_config = {"from_attributes": True}


class ShowListResponse(BaseModel):
    id: int
    name: str
    storyboard_id: Optional[int] = None
    status: str
    current_cue_id: Optional[int] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class ShowStatusResponse(BaseModel):
    show_id: int
    status: str
    current_cue_id: Optional[int] = None
    current_cue_number: Optional[float] = None
    current_cue_type: Optional[str] = None
    elapsed_in_cue: float = 0.0
    total_cues: int = 0
    completed_cues: int = 0


# ─── Analytics ORM Models ─────────────────────────────────────────────────────


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, index=True)   # session.start, course.served, show.cue, generation.complete, etc
    event_category = Column(String, index=True)  # session/course/show/generation/system
    session_id = Column(Integer, nullable=True)
    storyboard_id = Column(Integer, nullable=True)
    data = Column(Text, nullable=True)         # JSON payload
    timestamp = Column(DateTime, server_default=func.now(), index=True)


class GenerationMetrics(Base):
    __tablename__ = "generation_metrics"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False)          # gemini/imagen/runway/etc
    model = Column(String, nullable=False)
    generation_type = Column(String, nullable=False)   # image/video/animation
    scene_id = Column(Integer, nullable=True)
    prompt_length = Column(Integer, nullable=True)
    api_duration_ms = Column(Integer, nullable=True)
    total_duration_ms = Column(Integer, nullable=True)
    output_size_bytes = Column(Integer, nullable=True)
    status = Column(String, nullable=False)            # success/failed
    error_message = Column(Text, nullable=True)
    cost_estimate = Column(Float, nullable=True)
    timestamp = Column(DateTime, server_default=func.now(), index=True)


# ─── Analytics Pydantic Schemas ───────────────────────────────────────────────


class EventLogCreate(BaseModel):
    event_type: str
    event_category: str
    session_id: Optional[int] = None
    storyboard_id: Optional[int] = None
    data: Optional[dict] = None


class EventLogResponse(BaseModel):
    id: int
    event_type: str
    event_category: str
    session_id: Optional[int] = None
    storyboard_id: Optional[int] = None
    data: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class GenerationMetricsCreate(BaseModel):
    provider: str
    model: str
    generation_type: str
    scene_id: Optional[int] = None
    prompt_length: Optional[int] = None
    api_duration_ms: Optional[int] = None
    total_duration_ms: Optional[int] = None
    output_size_bytes: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    cost_estimate: Optional[float] = None


class GenerationMetricsResponse(BaseModel):
    id: int
    provider: str
    model: str
    generation_type: str
    scene_id: Optional[int] = None
    prompt_length: Optional[int] = None
    api_duration_ms: Optional[int] = None
    total_duration_ms: Optional[int] = None
    output_size_bytes: Optional[int] = None
    status: str
    error_message: Optional[str] = None
    cost_estimate: Optional[float] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class DashboardSummary(BaseModel):
    date: str
    total_sessions: int
    total_generations: int
    generation_success_rate: float
    avg_image_duration_ms: Optional[float]
    avg_video_duration_ms: Optional[float]
    total_cost_estimate: float
    event_counts_by_category: dict


class ProviderStats(BaseModel):
    provider: str
    generation_type: str
    total_count: int
    success_count: int
    success_rate: float
    avg_api_duration_ms: Optional[float]
    avg_total_duration_ms: Optional[float]
    total_cost_estimate: float


class ThemeStats(BaseModel):
    day_of_week: Optional[str]
    storyboard_count: int
    scene_count: int
    image_ready_count: int
    video_ready_count: int


# ─── TableSession / CourseEvent ORM Models ───────────────────────────────────


class TableSession(Base):
    __tablename__ = "table_sessions"

    id = Column(Integer, primary_key=True, index=True)
    table_number = Column(Integer, default=1)
    guest_count = Column(Integer, nullable=False)
    storyboard_id = Column(Integer, ForeignKey("storyboards.id"), nullable=True)
    show_id = Column(Integer, nullable=True)  # ショーコントロールと連携
    status = Column(String, default="seated")  # seated/dining/dessert/completed
    current_course = Column(String, nullable=True)  # welcome/appetizer/soup/main/dessert
    course_started_at = Column(DateTime, nullable=True)
    special_requests = Column(Text, nullable=True)  # JSON: アレルギー等
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    events = relationship(
        "CourseEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="CourseEvent.timestamp",
    )


class CourseEvent(Base):
    __tablename__ = "course_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("table_sessions.id"), nullable=False)
    course_key = Column(String, nullable=False)
    event_type = Column(String, nullable=False)  # prepared/served/eaten/cleared
    timestamp = Column(DateTime, server_default=func.now())
    notes = Column(Text, nullable=True)  # JSON: メモ・写真パス等

    session = relationship("TableSession", back_populates="events")


# ─── TableSession / CourseEvent Pydantic Schemas ──────────────────────────────


class TableSessionCreate(BaseModel):
    table_number: int = 1
    guest_count: int
    storyboard_id: Optional[int] = None
    show_id: Optional[int] = None
    special_requests: Optional[str] = None  # JSON string


class TableSessionResponse(BaseModel):
    id: int
    table_number: int
    guest_count: int
    storyboard_id: Optional[int] = None
    show_id: Optional[int] = None
    status: str
    current_course: Optional[str] = None
    course_started_at: Optional[datetime] = None
    special_requests: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CourseEventResponse(BaseModel):
    id: int
    session_id: int
    course_key: str
    event_type: str
    timestamp: Optional[datetime] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class CourseServeRequest(BaseModel):
    notes: Optional[str] = None  # JSON: 任意のメモ


class SessionTimelineResponse(BaseModel):
    session: TableSessionResponse
    events: List[CourseEventResponse]
