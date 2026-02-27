const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// --- Types ---

export interface Content {
  id: number;
  name: string;
  type: string;
  theme: string;
  file_path: string;
  duration: number | null;
  resolution: string | null;
  created_at: string;
}

export interface TimelineItem {
  id: number;
  content_id: number;
  start_time: number;
  duration: number;
  zone: string;
  transition: string;
  sort_order: number;
  content?: Content;
}

export interface Timeline {
  id: number;
  name: string;
  course_type: string;
  day_of_week: string;
  created_at: string;
  items: TimelineItem[];
}

export interface TimelineListItem {
  id: number;
  name: string;
  course_type: string;
  day_of_week: string;
  created_at: string;
}

export interface Birthday {
  id: number;
  guest_name: string;
  photo_path: string | null;
  character_video_path: string | null;
  reservation_date: string;
  status: string;
  created_at: string;
}

export interface ProjectionStatus {
  state: string;
  timeline_id: number | null;
  table_id: string | null;
  elapsed: number;
  current_content: string | null;
}

// --- Fetch helper ---

// Generation endpoints (image/video) take 30-120 seconds.
// Status-polling and quick CRUD use the short timeout.
const GENERATION_PATHS = [
  "/generate-images",
  "/generate-videos",
  "/generate-image",
  "/generate-video",
  "/generate-script",
  "/api/generation/video",
  "/api/generation/animation",
];

function _timeoutMs(path: string): number {
  const isGeneration = GENERATION_PATHS.some((p) => path.includes(p));
  // Generation calls: 120 s. All others: 15 s (was 5 s — too short for DB + OSC round-trips).
  return isGeneration ? 120_000 : 15_000;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), _timeoutMs(path));

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`API Error ${res.status}: ${text}`);
    }
    return res.json();
  } finally {
    clearTimeout(timeout);
  }
}

// --- Content ---

export async function fetchContents(): Promise<Content[]> {
  return apiFetch("/api/contents");
}

export async function fetchContentsByTheme(
  dayOfWeek: string
): Promise<Content[]> {
  return apiFetch(`/api/contents/themes/${dayOfWeek}`);
}

export async function createContent(formData: FormData): Promise<Content> {
  const res = await fetch(`${API_BASE}/api/contents`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}

export async function deleteContent(id: number): Promise<void> {
  await apiFetch(`/api/contents/${id}`, { method: "DELETE" });
}

// --- Timeline ---

export async function fetchTimelines(): Promise<TimelineListItem[]> {
  return apiFetch("/api/timelines");
}

export async function fetchTimeline(id: number): Promise<Timeline> {
  return apiFetch(`/api/timelines/${id}`);
}

export async function createTimeline(data: {
  name: string;
  course_type: string;
  day_of_week: string;
}): Promise<Timeline> {
  return apiFetch("/api/timelines", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTimelineItems(
  timelineId: number,
  items: Omit<TimelineItem, "id" | "content">[]
): Promise<Timeline> {
  return apiFetch(`/api/timelines/${timelineId}/items`, {
    method: "PUT",
    body: JSON.stringify(items),
  });
}

export async function deleteTimeline(id: number): Promise<void> {
  await apiFetch(`/api/timelines/${id}`, { method: "DELETE" });
}

// --- Birthday ---

export async function fetchBirthdays(): Promise<Birthday[]> {
  return apiFetch("/api/birthdays");
}

export async function createBirthday(formData: FormData): Promise<Birthday> {
  const res = await fetch(`${API_BASE}/api/birthdays`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Birthday creation failed: ${res.status}`);
  return res.json();
}

export async function updateBirthdayStatus(
  id: number,
  status: string
): Promise<Birthday> {
  return apiFetch(`/api/birthdays/${id}/status`, {
    method: "PUT",
    body: JSON.stringify({ status }),
  });
}

// --- Projection Control ---

export async function playProjection(
  timelineId: number,
  tableId?: string
): Promise<ProjectionStatus> {
  return apiFetch("/api/projection/play", {
    method: "POST",
    body: JSON.stringify({ timeline_id: timelineId, table_id: tableId }),
  });
}

export async function pauseProjection(): Promise<ProjectionStatus> {
  return apiFetch("/api/projection/pause", { method: "POST" });
}

export async function stopProjection(): Promise<ProjectionStatus> {
  return apiFetch("/api/projection/stop", { method: "POST" });
}

export async function triggerEvent(
  event: string,
  data?: Record<string, unknown>
): Promise<ProjectionStatus> {
  return apiFetch(`/api/projection/trigger/${event}`, {
    method: "POST",
    body: JSON.stringify({ data }),
  });
}

export async function getProjectionStatus(): Promise<ProjectionStatus> {
  return apiFetch("/api/projection/status");
}

// --- Day Themes ---

export interface DayThemeData {
  id: number;
  day_of_week: string;
  name_ja: string;
  name_en: string;
  color: string;
  icon: string;
  bg_gradient: string;
  updated_at: string | null;
}

export async function fetchThemes(): Promise<DayThemeData[]> {
  return apiFetch("/api/themes");
}

export async function fetchTheme(dayOfWeek: string): Promise<DayThemeData> {
  return apiFetch(`/api/themes/${dayOfWeek}`);
}

export async function updateTheme(
  dayOfWeek: string,
  data: {
    name_ja?: string;
    name_en?: string;
    color?: string;
    icon?: string;
    bg_gradient?: string;
  }
): Promise<DayThemeData> {
  return apiFetch(`/api/themes/${dayOfWeek}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function resetThemes(): Promise<DayThemeData[]> {
  return apiFetch("/api/themes/reset", { method: "POST" });
}

// --- Course Dishes ---

export interface CourseDish {
  id: number;
  name: string;
  course_key: string;
  description: string | null;
  day_of_week: string;
  sort_order: number;
  prompt_hint: string | null;
  created_at: string;
}

export async function fetchCourses(dayOfWeek?: string): Promise<CourseDish[]> {
  const params = dayOfWeek ? `?day_of_week=${dayOfWeek}` : "";
  return apiFetch(`/api/courses${params}`);
}

export async function createCourse(data: {
  name: string;
  course_key: string;
  description?: string;
  day_of_week: string;
  sort_order: number;
  prompt_hint?: string;
}): Promise<CourseDish> {
  return apiFetch("/api/courses", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateCourse(
  id: number,
  data: {
    name: string;
    course_key: string;
    description?: string;
    day_of_week: string;
    sort_order: number;
    prompt_hint?: string;
  }
): Promise<CourseDish> {
  return apiFetch(`/api/courses/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteCourse(id: number): Promise<void> {
  await apiFetch(`/api/courses/${id}`, { method: "DELETE" });
}

export async function generateFromCourses(params: {
  day: string;
  mode: string;
  provider?: string;
}): Promise<JobStatus> {
  return apiFetch("/api/generation/video/from-courses", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

// --- Table Spec ---

export interface TableSpec {
  id: number;
  pj_width: number;
  pj_height: number;
  pj_count: number;
  blend_overlap: number;
  zone_count: number;
  table_width_mm: number;
  table_height_mm: number;
  full_width: number;
  full_height: number;
  zone_width: number;
  zone_height: number;
  updated_at: string | null;
}

export async function fetchTableSpec(): Promise<TableSpec> {
  return apiFetch("/api/generation/table-spec");
}

export async function updateTableSpec(data: {
  pj_width?: number;
  pj_height?: number;
  pj_count?: number;
  blend_overlap?: number;
  zone_count?: number;
  table_width_mm?: number;
  table_height_mm?: number;
}): Promise<TableSpec> {
  return apiFetch("/api/generation/table-spec", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// --- Generation ---

export interface GenerationThemes {
  themes: string[];
  courses: string[];
  modes: string[];
  providers: string[];
  day_to_theme: Record<string, string>;
  table_spec: {
    full_width: number;
    full_height: number;
    zone_width: number;
    zone_height: number;
    zone_count: number;
    table_width_mm: number;
    table_height_mm: number;
  };
}

export interface PromptPreview {
  theme: string;
  course: string;
  mode: string;
  aspect_ratio: string;
  prompt: string;
}

export interface JobStatus {
  job_id: string;
  status: string;
  message: string;
  output_path?: string;
}

export interface AnimationTemplate {
  name: string;
  description: string;
  duration: number;
}

export async function fetchGenerationThemes(): Promise<GenerationThemes> {
  return apiFetch("/api/generation/themes");
}

export async function previewPrompt(params: {
  theme: string;
  course: string;
  mode: string;
}): Promise<PromptPreview> {
  return apiFetch("/api/generation/prompt-preview", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function generateVideo(params: {
  theme: string;
  course: string;
  mode: string;
  provider?: string;
  zone_id?: number;
}): Promise<JobStatus> {
  return apiFetch("/api/generation/video", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function generateBatch(params: {
  day: string;
  mode: string;
  provider?: string;
}): Promise<JobStatus> {
  return apiFetch("/api/generation/video/batch", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function compositeStitch(params: {
  left_path: string;
  right_path: string;
  output_path?: string;
}): Promise<JobStatus> {
  return apiFetch("/api/generation/composite/stitch", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function compositeZoneFit(params: {
  input_path: string;
  output_path?: string;
}): Promise<JobStatus> {
  return apiFetch("/api/generation/composite/zone-fit", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function compositeSplit(params: {
  input_path: string;
  output_dir?: string;
}): Promise<JobStatus> {
  return apiFetch("/api/generation/composite/split", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function fetchCompositeInfo(): Promise<Record<string, unknown>> {
  return apiFetch("/api/generation/composite/info");
}

export async function fetchAnimationTemplates(): Promise<
  Record<string, AnimationTemplate>
> {
  return apiFetch("/api/generation/animation/templates");
}

export async function generateAnimation(params: {
  photo_path: string;
  guest_name?: string;
  template_id: string;
  zone_id: number;
  provider?: string;
}): Promise<JobStatus> {
  return apiFetch("/api/generation/animation", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function fetchJobs(): Promise<Record<string, Record<string, unknown>>> {
  return apiFetch("/api/generation/jobs");
}

export async function animateBirthday(
  reservationId: number,
  params: { template_id: string; zone_id: number; provider?: string }
): Promise<Birthday> {
  return apiFetch(`/api/birthdays/${reservationId}/animate`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function fetchBirthdayTemplates(): Promise<
  Record<string, AnimationTemplate>
> {
  return apiFetch("/api/birthdays/templates");
}

// --- Scene Presets ---

export interface ScenePreset {
  id: string;
  category: string;
  name_ja: string;
  name_en: string;
  description_ja: string;
  prompt_en: string;
  mood: string;
  camera_angle: string;
  color_tone: string;
  suggested_duration: number;
  suggested_transition: string;
  tags: string[];
}

export async function fetchScenePresets(
  category?: string,
  search?: string
): Promise<{ presets: ScenePreset[] }> {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (search) params.set("search", search);
  const query = params.toString();
  return apiFetch(`/api/storyboards/scene-presets${query ? `?${query}` : ""}`);
}

// --- Storyboard ---

export interface StoryboardScene {
  id: number;
  storyboard_id: number;
  course_key: string;
  course_dish_id: number | null;
  sort_order: number;
  // 絵コンテ fields
  scene_title: string | null;
  scene_description_ja: string | null;
  mood: string | null;
  camera_angle: string | null;
  prompt: string;
  prompt_edited: string | null;
  extra_prompt: string | null;
  duration_seconds: number;
  transition: string;
  aspect_ratio: string;
  image_status: string;
  image_path: string | null;
  video_status: string;
  video_path: string | null;
  created_at: string;
  updated_at: string | null;
  projection_mode: string;
  target_zones: string | null;
  color_tone: string;
  brightness: string;
  animation_speed: string;
  prompt_modifier: string | null;
}

export interface StoryboardData {
  id: number;
  title: string;
  day_of_week: string | null;
  theme: string | null;
  mode: string;
  provider: string;
  status: string;
  created_at: string;
  updated_at: string | null;
  scenes: StoryboardScene[];
}

export interface StoryboardListItem {
  id: number;
  title: string;
  day_of_week: string | null;
  theme: string | null;
  mode: string;
  provider: string;
  status: string;
  created_at: string;
}

export async function createStoryboard(data: {
  title?: string;
  day_of_week?: string;
  theme?: string;
  provider?: string;
  auto_generate_scenes?: boolean;
}): Promise<StoryboardData> {
  return apiFetch("/api/storyboards", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function fetchStoryboards(): Promise<StoryboardListItem[]> {
  return apiFetch("/api/storyboards");
}

export async function fetchStoryboard(id: number): Promise<StoryboardData> {
  return apiFetch(`/api/storyboards/${id}`);
}

export async function deleteStoryboard(id: number): Promise<void> {
  await apiFetch(`/api/storyboards/${id}`, { method: "DELETE" });
}

export interface DishConcept {
  name: string;
  concept: string;
}

export async function generateScript(
  storyboardId: number,
  params: {
    concept?: string;
    mode: "full_course" | "per_dish";
    dishes?: DishConcept[];
  }
): Promise<StoryboardData> {
  return apiFetch(`/api/storyboards/${storyboardId}/generate-script`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export async function updateStoryboard(
  id: number,
  data: {
    title?: string;
    day_of_week?: string;
    theme?: string;
    provider?: string;
  }
): Promise<StoryboardData> {
  return apiFetch(`/api/storyboards/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function updateScene(
  storyboardId: number,
  sceneId: number,
  data: {
    scene_title?: string | null;
    prompt_edited?: string;
    scene_description_ja?: string;
    mood?: string | null;
    camera_angle?: string | null;
    duration_seconds?: number;
    transition?: string;
    projection_mode?: string;
    target_zones?: string | null;
    color_tone?: string;
    brightness?: string;
    animation_speed?: string;
    prompt_modifier?: string | null;
    course_key?: string;
  }
): Promise<StoryboardScene> {
  return apiFetch(`/api/storyboards/${storyboardId}/scenes/${sceneId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function addScene(
  storyboardId: number,
  data: {
    course_key?: string;
    scene_title?: string;
    scene_description_ja?: string;
    mood?: string;
    camera_angle?: string;
    duration_seconds?: number;
    transition?: string;
    projection_mode?: string;
    target_zones?: string;
    color_tone?: string;
    brightness?: string;
    animation_speed?: string;
    prompt_modifier?: string;
    // Integrated course fields
    course_name?: string;
    course_description?: string;
    prompt_hint?: string;
    save_course?: boolean;
  }
): Promise<StoryboardData> {
  return apiFetch(`/api/storyboards/${storyboardId}/scenes`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateSceneCourse(
  storyboardId: number,
  sceneId: number,
  courseData: {
    course_name?: string;
    course_description?: string;
    prompt_hint?: string;
    course_key?: string;
    day_of_week?: string;
    sort_order?: number;
  }
): Promise<{ scene: StoryboardScene; course: CourseDish | null }> {
  return apiFetch(`/api/storyboards/${storyboardId}/scenes/${sceneId}/course`, {
    method: "PUT",
    body: JSON.stringify(courseData),
  });
}

export async function deleteScene(
  storyboardId: number,
  sceneId: number
): Promise<StoryboardData> {
  return apiFetch(`/api/storyboards/${storyboardId}/scenes/${sceneId}`, {
    method: "DELETE",
  });
}

export async function reorderScenes(
  storyboardId: number,
  sceneIds: number[]
): Promise<StoryboardData> {
  return apiFetch(`/api/storyboards/${storyboardId}/scenes/reorder`, {
    method: "PUT",
    body: JSON.stringify({ scene_ids: sceneIds }),
  });
}

export async function generateStoryboardImages(
  storyboardId: number,
  provider?: string
): Promise<JobStatus> {
  return apiFetch(`/api/storyboards/${storyboardId}/generate-images`, {
    method: "POST",
    body: JSON.stringify({ provider }),
  });
}

export async function regenerateSceneImage(
  storyboardId: number,
  sceneId: number,
  provider?: string
): Promise<JobStatus> {
  return apiFetch(`/api/storyboards/${storyboardId}/scenes/${sceneId}/generate-image`, {
    method: "POST",
    body: JSON.stringify({ provider }),
  });
}

export async function approveStoryboardImages(storyboardId: number): Promise<StoryboardData> {
  return apiFetch(`/api/storyboards/${storyboardId}/approve-images`, {
    method: "POST",
  });
}

export async function generateStoryboardVideos(storyboardId: number): Promise<JobStatus> {
  return apiFetch(`/api/storyboards/${storyboardId}/generate-videos`, {
    method: "POST",
  });
}

export async function regenerateSceneVideo(
  storyboardId: number,
  sceneId: number
): Promise<JobStatus> {
  return apiFetch(`/api/storyboards/${storyboardId}/scenes/${sceneId}/generate-video`, {
    method: "POST",
  });
}

export interface GenerationStatus {
  // Backend returns "generating" while active, "idle" when done (batch complete or no job running).
  // "complete" and "failed" are NOT returned by /generation-status — they exist only in /jobs/{id}.
  status: "generating" | "idle";
  total_scenes: number;
  completed_scenes: number;
  elapsed_seconds: number | null;
  avg_seconds_per_scene: number | null;
  estimated_remaining_seconds: number | null;
}

export async function fetchGenerationStatus(storyboardId: number): Promise<GenerationStatus> {
  return apiFetch(`/api/storyboards/${storyboardId}/generation-status`);
}

export async function fetchScenesStatus(storyboardId: number): Promise<{
  scenes: Array<{
    id: number;
    image_status: string;
    image_path: string | null;
    video_status: string;
    video_path: string | null;
  }>;
}> {
  return apiFetch(`/api/storyboards/${storyboardId}/scenes/status`);
}

// --- Settings ---

export interface AppSetting {
  id: number;
  key: string;
  value: string;
  label: string | null;
  category: string | null;
  is_secret: boolean;
  updated_at: string | null;
}

export async function fetchSettings(): Promise<AppSetting[]> {
  return apiFetch("/api/settings");
}

export async function updateSetting(key: string, value: string): Promise<AppSetting> {
  return apiFetch(`/api/settings/${key}`, {
    method: "PUT",
    body: JSON.stringify({ value }),
  });
}

// --- Reservations ---

export interface Reservation {
  id: number;
  guest_name: string;
  guest_email: string | null;
  guest_phone: string | null;
  party_size: number;
  reservation_date: string;
  time_slot: string;
  table_number: number | null;
  status: string;
  special_occasion: string | null;
  special_requests: string | null;
  theme_override: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface CalendarDaySummary {
  date: string;
  total: number;
  confirmed: number;
  checked_in: number;
  seated: number;
  completed: number;
  cancelled: number;
}

export interface ReservationCreate {
  guest_name: string;
  guest_email?: string;
  guest_phone?: string;
  party_size: number;
  reservation_date: string;
  time_slot: string;
  table_number?: number;
  special_occasion?: string;
  special_requests?: string;
  theme_override?: string;
}

export async function fetchReservations(params?: {
  reservation_date?: string;
  status?: string;
}): Promise<Reservation[]> {
  const query = new URLSearchParams();
  if (params?.reservation_date) query.set("reservation_date", params.reservation_date);
  if (params?.status) query.set("status", params.status);
  const qs = query.toString() ? `?${query.toString()}` : "";
  return apiFetch(`/api/reservations${qs}`);
}

export async function fetchTodayReservations(): Promise<Reservation[]> {
  return apiFetch("/api/reservations/today");
}

export async function fetchCalendar(year: number, month: number): Promise<CalendarDaySummary[]> {
  return apiFetch(`/api/reservations/calendar?year=${year}&month=${month}`);
}

export async function fetchReservation(id: number): Promise<Reservation> {
  return apiFetch(`/api/reservations/${id}`);
}

export async function createReservation(data: ReservationCreate): Promise<Reservation> {
  return apiFetch("/api/reservations", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateReservation(
  id: number,
  data: Partial<ReservationCreate & { status: string }>
): Promise<Reservation> {
  return apiFetch(`/api/reservations/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function cancelReservation(id: number): Promise<Reservation> {
  return apiFetch(`/api/reservations/${id}`, { method: "DELETE" });
}

export async function checkInReservation(id: number): Promise<Reservation> {
  return apiFetch(`/api/reservations/${id}/check-in`, { method: "POST" });
}

// --- Storyboard SSE ---

/**
 * SSEイベントの型定義
 * バックエンドからプッシュされるイベントを表す
 */
export type StoryboardEvent =
  | {
      type: "scene_updated";
      storyboard_id: number;
      scene_id: number;
      image_status?: string;
      image_path?: string | null;
      video_status?: string;
      video_path?: string | null;
    }
  | { type: "storyboard_updated"; storyboard_id: number; status: string }
  | { type: "connected" };

/**
 * ストーリーボードのSSEイベントを購読する
 * EventSourceのauto-reconnect機能により、接続が切れても自動再接続される
 * @returns クリーンアップ関数（コンポーネントのアンマウント時に呼び出すこと）
 */
export function subscribeToStoryboardEvents(
  onEvent: (event: StoryboardEvent) => void
): () => void {
  const url = `${API_BASE}/api/storyboards/events/stream`;
  const eventSource = new EventSource(url);

  eventSource.addEventListener("scene_updated", (e: MessageEvent) => {
    try {
      onEvent({ type: "scene_updated", ...JSON.parse(e.data) });
    } catch {
      // JSONパースエラーは無視
    }
  });

  eventSource.addEventListener("storyboard_updated", (e: MessageEvent) => {
    try {
      onEvent({ type: "storyboard_updated", ...JSON.parse(e.data) });
    } catch {
      // JSONパースエラーは無視
    }
  });

  eventSource.addEventListener("connected", () => {
    onEvent({ type: "connected" });
  });

  eventSource.onerror = () => {
    // EventSourceは接続が切れると自動的に再接続する
    console.warn("[SSE] ストーリーボードSSE接続が切れました。自動再接続中...");
  };

  // アンマウント時にEventSourceを閉じるクリーンアップ関数を返す
  return () => eventSource.close();
}

// --- WebSocket ---

export function createProjectionWebSocket(
  onMessage: (status: ProjectionStatus) => void,
  onError?: (event: Event) => void,
  onClose?: (event: CloseEvent) => void
): WebSocket {
  const wsUrl = API_BASE.replace(/^http/, "ws") + "/api/projection/ws";
  const ws = new WebSocket(wsUrl);
  ws.onmessage = (event) => {
    try {
      const status = JSON.parse(event.data) as ProjectionStatus;
      onMessage(status);
    } catch {
      // ignore malformed frames
    }
  };
  ws.onerror = onError ?? ((e) => console.error("[ProjectionWS] error", e));
  ws.onclose = onClose ?? ((e) => console.warn("[ProjectionWS] closed", e.code, e.reason));
  return ws;
}

// --- Show Control ---

export interface ShowCue {
  id: number;
  show_id: number;
  cue_number: number;
  cue_type: string; // content / transition / trigger / wait
  target_zones: string;
  content_path: string | null;
  transition: string;
  duration_seconds: number;
  auto_follow: boolean;
  auto_follow_delay: number;
  notes: string | null;
  sort_order: number;
}

export interface ShowData {
  id: number;
  name: string;
  storyboard_id: number | null;
  status: string; // standby / running / paused / completed
  current_cue_id: number | null;
  created_at: string;
  cues: ShowCue[];
}

export interface ShowListItem {
  id: number;
  name: string;
  storyboard_id: number | null;
  status: string;
  current_cue_id: number | null;
  created_at: string;
}

export interface ShowStatus {
  show_id: number;
  status: string;
  current_cue_id: number | null;
  current_cue_number: number | null;
  current_cue_type: string | null;
  elapsed_in_cue: number;
  total_cues: number;
  completed_cues: number;
}

export async function fetchShows(): Promise<ShowListItem[]> {
  return apiFetch("/api/shows");
}

export async function fetchShow(id: number): Promise<ShowData> {
  return apiFetch(`/api/shows/${id}`);
}

export async function createShow(data: {
  name: string;
  storyboard_id?: number;
}): Promise<ShowData> {
  return apiFetch("/api/shows", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function startShow(id: number): Promise<ShowStatus> {
  return apiFetch(`/api/shows/${id}/start`, { method: "POST" });
}

export async function goNextCue(id: number): Promise<ShowStatus> {
  return apiFetch(`/api/shows/${id}/go`, { method: "POST" });
}

export async function gotoCue(showId: number, cueId: number): Promise<ShowStatus> {
  return apiFetch(`/api/shows/${showId}/goto/${cueId}`, { method: "POST" });
}

export async function pauseShow(id: number): Promise<ShowStatus> {
  return apiFetch(`/api/shows/${id}/pause`, { method: "POST" });
}

export async function stopShow(id: number): Promise<ShowStatus> {
  return apiFetch(`/api/shows/${id}/stop`, { method: "POST" });
}

export async function getShowStatus(id: number): Promise<ShowStatus> {
  return apiFetch(`/api/shows/${id}/status`);
}

export async function addShowCue(
  showId: number,
  data: Omit<ShowCue, "id" | "show_id">
): Promise<ShowCue> {
  return apiFetch(`/api/shows/${showId}/cues`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateShowCue(
  showId: number,
  cueId: number,
  data: Partial<Omit<ShowCue, "id" | "show_id">>
): Promise<ShowCue> {
  return apiFetch(`/api/shows/${showId}/cues/${cueId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export interface ShowWsMessage {
  channel: "status" | "alert" | "sync";
  data?: ShowStatus;
  level?: string;
  message?: string;
}

export function createShowWebSocket(
  onMessage: (msg: ShowWsMessage) => void,
  onError?: (event: Event) => void,
  onClose?: (event: CloseEvent) => void
): WebSocket {
  const wsUrl = API_BASE.replace(/^http/, "ws") + "/api/shows/ws";
  const ws = new WebSocket(wsUrl);
  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data) as ShowWsMessage;
      onMessage(msg);
    } catch {
      // ignore malformed frames
    }
  };
  ws.onerror = onError ?? ((e) => console.error("[ShowWS] error", e));
  ws.onclose = onClose ?? ((e) => console.warn("[ShowWS] closed", e.code, e.reason));
  return ws;
}

// --- Table Sessions ---

export interface TableSession {
  id: number;
  table_number: number;
  guest_count: number;
  storyboard_id: number | null;
  show_id: number | null;
  status: string; // seated / dining / dessert / completed
  current_course: string | null;
  course_started_at: string | null;
  special_requests: string | null; // JSON string
  started_at: string | null;
  completed_at: string | null;
}

export interface CourseEvent {
  id: number;
  session_id: number;
  course_key: string;
  event_type: string; // prepared / served / eaten / cleared
  timestamp: string | null;
  notes: string | null;
}

export interface SessionTimeline {
  session: TableSession;
  events: CourseEvent[];
}

export interface TableSessionCreate {
  table_number?: number;
  guest_count: number;
  storyboard_id?: number;
  show_id?: number;
  special_requests?: string;
}

export async function createTableSession(
  data: TableSessionCreate
): Promise<TableSession> {
  return apiFetch("/api/sessions", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function fetchTableSessions(
  status?: string
): Promise<TableSession[]> {
  const qs = status ? `?status=${status}` : "";
  return apiFetch(`/api/sessions${qs}`);
}

export async function fetchTableSession(id: number): Promise<TableSession> {
  return apiFetch(`/api/sessions/${id}`);
}

export async function serveCourse(
  sessionId: number,
  courseKey: string,
  notes?: string
): Promise<TableSession> {
  return apiFetch(`/api/sessions/${sessionId}/course/${courseKey}/serve`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
}

export async function clearCourse(
  sessionId: number,
  courseKey: string,
  notes?: string
): Promise<TableSession> {
  return apiFetch(`/api/sessions/${sessionId}/course/${courseKey}/clear`, {
    method: "POST",
    body: JSON.stringify({ notes }),
  });
}

export async function completeTableSession(
  sessionId: number
): Promise<TableSession> {
  return apiFetch(`/api/sessions/${sessionId}/complete`, { method: "POST" });
}

export async function fetchSessionTimeline(
  sessionId: number
): Promise<SessionTimeline> {
  return apiFetch(`/api/sessions/${sessionId}/timeline`);
}

// --- Character Generation ---

export interface CharacterTemplate {
  name: string;
  category: string;
  description: string;
  duration: number;
}

export interface CharacterJobStatus {
  job_id: string;
  status: string;
  job_type: string;
  guest_name: string;
  output_path: string | null;
  error: string | null;
  message: string;
}

export interface CharacterTemplatePreview {
  id: string;
  name: string;
  category: string;
  description: string;
  duration: number;
  composite_position: { x: number; y: number; scale: number };
  text_position: { x: number; y: number; anchor: string } | null;
  preview_url: string;
  thumbnail_url: string;
}

export async function fetchCharacterTemplates(
  category?: string
): Promise<Record<string, CharacterTemplate>> {
  const qs = category ? `?category=${category}` : "";
  return apiFetch(`/api/characters/templates${qs}`);
}

export async function fetchCharacterTemplatePreview(
  templateId: string
): Promise<CharacterTemplatePreview> {
  return apiFetch(`/api/characters/templates/${templateId}/preview`);
}

export async function createCharacterAvatar(
  formData: FormData
): Promise<CharacterJobStatus> {
  const res = await fetch(`${API_BASE}/api/characters/avatar`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Avatar creation failed: ${res.status}`);
  return res.json();
}

export async function createCharacterAnimation(
  formData: FormData
): Promise<CharacterJobStatus> {
  const res = await fetch(`${API_BASE}/api/characters/animation`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Animation creation failed: ${res.status}`);
  return res.json();
}

export async function createCharacterMemorial(
  formData: FormData
): Promise<CharacterJobStatus> {
  const res = await fetch(`${API_BASE}/api/characters/memorial`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Memorial creation failed: ${res.status}`);
  return res.json();
}

export async function fetchCharacterJobStatus(
  jobId: string
): Promise<CharacterJobStatus> {
  return apiFetch(`/api/characters/jobs/${jobId}`);
}

// --- Analytics ---

export interface DashboardSummary {
  date: string;
  total_sessions: number;
  total_generations: number;
  generation_success_rate: number;
  avg_image_duration_ms: number | null;
  avg_video_duration_ms: number | null;
  total_cost_estimate: number;
  event_counts_by_category: Record<string, number>;
}

export interface ProviderStats {
  provider: string;
  generation_type: string;
  total_count: number;
  success_count: number;
  success_rate: number;
  avg_api_duration_ms: number | null;
  avg_total_duration_ms: number | null;
  total_cost_estimate: number;
}

export interface GenerationStatsResponse {
  days: number;
  providers: ProviderStats[];
}

export interface CostDataPoint {
  date: string;
  provider: string;
  cost_estimate: number;
  generation_count: number;
}

export interface CostStatsResponse {
  days: number;
  data: CostDataPoint[];
}

export interface ThemeUsageStats {
  day_of_week: string;
  storyboard_count: number;
  scene_count: number;
  image_ready_count: number;
  video_ready_count: number;
}

export interface EventLogEntry {
  id: number;
  event_type: string;
  event_category: string;
  session_id: number | null;
  storyboard_id: number | null;
  data: string | null;
  timestamp: string;
}

export interface SessionDataPoint {
  date: string;
  sessions: number;
  avg_duration_minutes: number | null;
}

export interface SessionStatsResponse {
  period: string;
  days: number;
  data: SessionDataPoint[];
}

export interface HealthStatus {
  status: string;
  db_connected: boolean;
  recent_events_5min: number;
  last_generation_error: {
    provider: string;
    error: string;
    timestamp: string;
  } | null;
  checked_at: string;
}

export async function fetchAnalyticsDashboard(): Promise<DashboardSummary> {
  return apiFetch("/api/analytics/dashboard");
}

export async function fetchAnalyticsSessions(
  period: string = "daily",
  days: number = 7
): Promise<SessionStatsResponse> {
  return apiFetch(`/api/analytics/sessions?period=${period}&days=${days}`);
}

export async function fetchAnalyticsGeneration(
  days: number = 7
): Promise<GenerationStatsResponse> {
  return apiFetch(`/api/analytics/generation?days=${days}`);
}

export async function fetchAnalyticsCosts(
  days: number = 30
): Promise<CostStatsResponse> {
  return apiFetch(`/api/analytics/generation/costs?days=${days}`);
}

export async function fetchAnalyticsThemes(): Promise<{ themes: ThemeUsageStats[] }> {
  return apiFetch("/api/analytics/themes");
}

export async function fetchAnalyticsEvents(params?: {
  event_type?: string;
  category?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
}): Promise<EventLogEntry[]> {
  const q = new URLSearchParams();
  if (params?.event_type) q.set("event_type", params.event_type);
  if (params?.category) q.set("category", params.category);
  if (params?.date_from) q.set("date_from", params.date_from);
  if (params?.date_to) q.set("date_to", params.date_to);
  if (params?.limit !== undefined) q.set("limit", String(params.limit));
  const qs = q.toString() ? `?${q.toString()}` : "";
  return apiFetch(`/api/analytics/events${qs}`);
}

export async function postAnalyticsEvent(data: {
  event_type: string;
  event_category: string;
  session_id?: number;
  storyboard_id?: number;
  data?: Record<string, unknown>;
}): Promise<EventLogEntry> {
  return apiFetch("/api/analytics/events", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function fetchAnalyticsHealth(): Promise<HealthStatus> {
  return apiFetch("/api/analytics/health");
}

// --- GenerationMetric (individual record) ---

export interface GenerationMetric {
  id: number;
  provider: string;
  model: string;
  generation_type: string;
  api_duration_ms: number;
  total_duration_ms: number;
  status: string;
  timestamp: string;
}

export async function fetchGenerationMetrics(params?: {
  provider?: string;
  days?: number;
}): Promise<GenerationMetric[]> {
  const q = new URLSearchParams();
  if (params?.provider) q.set("provider", params.provider);
  if (params?.days !== undefined) q.set("days", String(params.days));
  const qs = q.toString() ? `?${q.toString()}` : "";
  return apiFetch(`/api/analytics/generation/metrics${qs}`);
}

// --- Convenience aliases (for components expecting shortened names) ---

/** @alias fetchShows */
export const getShows = fetchShows;

/** @alias fetchShow */
export const getShow = fetchShow;

/** @alias fetchTableSessions */
export const getSessions = fetchTableSessions;

/** @alias completeTableSession */
export const completeSession = completeTableSession;

/** @alias fetchReservations */
export const getReservations = fetchReservations;

/** @alias fetchAnalyticsDashboard */
export const getAnalyticsDashboard = fetchAnalyticsDashboard;

/** @alias fetchGenerationMetrics */
export const getGenerationMetrics = fetchGenerationMetrics;

/** @alias fetchCharacterTemplates */
export const getCharacterTemplates = fetchCharacterTemplates;

/** @alias createCharacterAvatar */
export const generateAvatar = createCharacterAvatar;
