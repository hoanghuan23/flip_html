import {
  defaultCategoryId,
  defaultStyleId,
  restoreCategory,
  restoreStyle,
  styleForCategory,
  type CategoryId,
  type StyleId,
} from "./styleConfig";
import { numberReferenceImages, validReferenceImages, type ReferenceImage } from "./referenceImages";
export type { CategoryId, StyleId } from "./styleConfig";
export interface Annotation {
  text: string;
  target: string;
  action_index?: number | null;
  cue?: string | null;
}
export interface ScriptReview {
  input_type?: "general_script" | "topic" | "detailed_script" | "legacy";
  research?: {
    status: "sources_reported" | "unverified" | "not_required";
    sources: { title: string; url: string; claims: string[] }[];
    summary?: string;
  };
  warnings?: string[];
}
export interface Scene {
  id: string;
  name: string;
  narration: string;
  description: string;
  duration: number;
  voiceover?: string;
  annotations?: Annotation[];
  duration_status?: "estimated";
}
export interface ScriptJob {
  id: string;
  projectId: string;
  status: "queued" | "running" | "succeeded" | "rejected" | "failed";
  stage: string;
  error: string | null;
  result: ({ title: string; scenes: Scene[] } & ScriptReview) | null;
}
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
}
export interface PreviewSnapshot {
  id: string;
  revision: string;
  projectId: string;
  duration: number;
  width: number;
  height: number;
  phases: { id: string; name: string; duration: number; url: string; audio?: {url: string; duration: number} }[];
  sourceSignature: string;
  scriptId?: string;
  categoryId?: CategoryId;
  styleId?: StyleId;
  renderer?: string;
}
export interface GraphicsJob {
  id: string;
  projectId: string;
  status: "queued" | "running" | "awaiting_confirmation" | "succeeded" | "failed";
  stage: string;
  completed: number;
  total: number;
  error: string | null;
  result: PreviewSnapshot | null;
  sourceSignature?: string;
  confirmed?: boolean;
  previews?: { id: string; name: string; url: string; width: number; height: number; sha256: string }[];
}
export interface ExportConfig {
  filename: string;
  fps: 24 | 30 | 60;
  quality: "draft" | "looks" | "delivery";
}
export interface RenderJob {
  id: string;
  snapshotId: string;
  status: "queued" | "running" | "succeeded" | "failed";
  stage: string;
  createdAt: string;
  startedAt?: string;
  config: ExportConfig;
  duration: number;
  width: number;
  height: number;
  error: string | null;
  progress?: number | null;
  result: { videoUrl: string; downloadUrl: string; bytes: number } | null;
}
export interface ProjectDraft {
  id: string;
  title: string;
  sourceContent: string;
  sourceFilename?: string;
  referenceImages?: ReferenceImage[];
  lastReferenceImageNumber?: number;
  categoryId: CategoryId;
  styleId: StyleId;
  scenes: Scene[];
  scriptReview?: ScriptReview;
  messages: ChatMessage[];
  updatedAt: string;
  snapshot?: PreviewSnapshot;
  jobId?: string;
  scriptJobId?: string;
  scriptId?: string;
  graphicsJobId?: string;
  graphicsPreviewId?: string;
  lastExportConfig?: ExportConfig;
}
export const defaultConfig: ExportConfig = {
  filename: "video-cua-toi",
  fps: 30,
  quality: "delivery",
};
export const newProject = (): ProjectDraft => ({
  id: crypto.randomUUID(),
  title: "Dự án chưa đặt tên",
  sourceContent: "",
  categoryId: defaultCategoryId,
  styleId: styleForCategory(defaultCategoryId, defaultStyleId),
  scenes: [],
  messages: [],
  updatedAt: new Date().toISOString(),
});
export const previewInput = (p: ProjectDraft) => ({
  projectId: p.id,
  scriptId: p.scriptId,
  categoryId: p.categoryId,
  styleId: p.styleId,
});
export const signature = (p: ProjectDraft) => JSON.stringify(previewInput(p));

export function safeSourceUrl(value: unknown): value is string {
  if (typeof value !== "string") return false;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !!url.hostname && !url.username && !url.password;
  } catch { return false; }
}

function annotationsValid(value: unknown): value is Annotation[] {
  return Array.isArray(value) && value.every((note) => note &&
    typeof note.text === "string" && !!note.text.trim() && note.text.length <= 200 &&
    typeof note.target === "string" && !!note.target.trim() &&
    (note.action_index == null || (Number.isSafeInteger(note.action_index) && note.action_index >= 0)) &&
    (note.cue == null || (typeof note.cue === "string" && !!note.cue.trim())));
}

function reviewValid(value: unknown): value is ScriptReview {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const review = value as ScriptReview;
  const research = review.research;
  return (review.input_type === undefined || ["general_script", "topic", "detailed_script", "legacy"].includes(review.input_type)) &&
    (review.warnings === undefined || (Array.isArray(review.warnings) && review.warnings.every((w) => typeof w === "string" && !!w.trim()))) &&
    (research === undefined || (!!research &&
      ["sources_reported", "unverified", "not_required"].includes(research.status) &&
      (research.summary === undefined || typeof research.summary === "string") &&
      Array.isArray(research.sources) &&
      (research.status === "sources_reported" ? research.sources.length > 0 : research.sources.length === 0) &&
      research.sources.every((source) => source && typeof source.title === "string" && !!source.title.trim() &&
        safeSourceUrl(source.url) && Array.isArray(source.claims) && source.claims.length > 0 &&
        source.claims.every((claim) => typeof claim === "string" && !!claim.trim()))));
}

export function sceneValid(s: Scene) {
  return (
    !!s.name.trim() &&
    s.name.length <= 160 &&
    s.narration.length <= 2000 &&
    (s.voiceover === undefined || (typeof s.voiceover === "string" && s.voiceover.length <= 10000)) &&
    (s.annotations === undefined || (annotationsValid(s.annotations) && s.annotations.every((note) =>
      !note.cue || !!s.voiceover?.includes(note.cue)))) &&
    (s.duration_status === undefined || s.duration_status === "estimated") &&
    s.description.length <= 3000 &&
    Number.isFinite(s.duration) &&
    s.duration > 0 &&
    s.duration <= 120
  );
}
export function parseDraft(value: unknown): ProjectDraft {
  if (!value || typeof value !== "object")
    throw new Error("Bản nháp không hợp lệ.");
  const p = value as ProjectDraft;
  const savedStyle = restoreStyle(p.styleId);
  const categoryId = p.categoryId === undefined ? defaultCategoryId : restoreCategory(p.categoryId);
  if (
    typeof p.id !== "string" ||
    !p.id ||
    typeof p.title !== "string" ||
    !p.title.trim() ||
    p.title.length > 160 ||
    typeof p.sourceContent !== "string" ||
    (p.scriptReview !== undefined && !reviewValid(p.scriptReview)) ||
    (p.referenceImages !== undefined && !validReferenceImages(p.referenceImages)) ||
    (p.lastReferenceImageNumber !== undefined &&
      (!Number.isSafeInteger(p.lastReferenceImageNumber) || p.lastReferenceImageNumber < 0)) ||
    !savedStyle ||
    !categoryId ||
    !Array.isArray(p.scenes) ||
    p.scenes.length > 100 ||
    !Array.isArray(p.messages) ||
    !p.messages.every(
      (m) =>
        m &&
        typeof m.id === "string" &&
        ["user", "assistant"].includes(m.role) &&
        typeof m.text === "string",
    ) ||
    !p.scenes.every(
      (s) =>
        s &&
        typeof s.id === "string" &&
        !!s.id &&
        s.id.length <= 100 &&
        typeof s.name === "string" &&
        typeof s.narration === "string" &&
        typeof s.description === "string" &&
        sceneValid(s),
    ) ||
    new Set(p.scenes.map((s) => s.id)).size !== p.scenes.length ||
    p.scenes.reduce((n, s) => n + s.duration, 0) > 1800
  )
    throw new Error("File JSON không đúng định dạng bản nháp AI Video Studio.");
  const referenceImages = p.referenceImages && numberReferenceImages(p.referenceImages);
  // Rebuild optional data explicitly; imported files never supply playable URLs.
  return {
    id: p.id,
    title: p.title,
    sourceContent: p.sourceContent,
    referenceImages: referenceImages?.map(({ id, name, dataUrl, number, kind, serverId }) => ({
      id, name, dataUrl, number, ...(kind ? { kind } : {}), ...(serverId ? { serverId } : {}),
    })),
    lastReferenceImageNumber: Math.max(p.lastReferenceImageNumber ?? 0,
      ...(referenceImages ?? []).map((image) => image.number)),
    scriptId:
      typeof p.scriptId === "string" && /^[a-f0-9]{32}$/.test(p.scriptId)
        ? p.scriptId : undefined,
    categoryId,
    styleId: styleForCategory(categoryId, savedStyle),
    scenes: p.scenes,
    scriptReview: p.scriptReview,
    messages: p.messages,
    updatedAt: new Date().toISOString(),
    sourceFilename:
      typeof p.sourceFilename === "string" ? p.sourceFilename : undefined,
    lastExportConfig:
      p.lastExportConfig &&
      typeof p.lastExportConfig.filename === "string" &&
      [24, 30, 60].includes(p.lastExportConfig.fps) &&
      ["draft", "looks", "delivery"].includes(p.lastExportConfig.quality)
        ? {
            filename: p.lastExportConfig.filename,
            fps: p.lastExportConfig.fps,
            quality: p.lastExportConfig.quality,
          }
        : undefined,
  };
}
