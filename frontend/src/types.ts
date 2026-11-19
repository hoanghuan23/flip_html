import {
  defaultCategoryId,
  defaultStyleId,
  isCategoryId,
  restoreStyle,
  styleForCategory,
  type CategoryId,
  type StyleId,
} from "./styleConfig";
export type { CategoryId, StyleId } from "./styleConfig";
export interface Scene {
  id: string;
  name: string;
  narration: string;
  description: string;
  duration: number;
}
export interface ScriptJob {
  id: string;
  projectId: string;
  status: "queued" | "running" | "succeeded" | "rejected" | "failed";
  stage: string;
  error: string | null;
  result: { title: string; scenes: Scene[] } | null;
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
  phases: { id: string; name: string; duration: number; url: string }[];
  sourceSignature: string;
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
  categoryId: CategoryId;
  styleId: StyleId;
  scenes: Scene[];
  messages: ChatMessage[];
  updatedAt: string;
  snapshot?: PreviewSnapshot;
  jobId?: string;
  scriptJobId?: string;
  scriptId?: string;
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
  title: p.title,
  categoryId: p.categoryId,
  styleId: p.styleId,
  scenes: p.scenes,
});
export const signature = (p: ProjectDraft) => JSON.stringify(previewInput(p));
export function sceneValid(s: Scene) {
  return (
    !!s.name.trim() &&
    s.name.length <= 160 &&
    s.narration.length <= 2000 &&
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
  if (
    typeof p.id !== "string" ||
    !p.id ||
    typeof p.title !== "string" ||
    !p.title.trim() ||
    p.title.length > 160 ||
    typeof p.sourceContent !== "string" ||
    !savedStyle ||
    (p.categoryId !== undefined && !isCategoryId(p.categoryId)) ||
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
  const categoryId = p.categoryId ?? defaultCategoryId;
  // Rebuild optional data explicitly; imported files never supply playable URLs.
  return {
    id: p.id,
    title: p.title,
    sourceContent: p.sourceContent,
    scriptId:
      typeof p.scriptId === "string" && /^[a-f0-9]{32}$/.test(p.scriptId)
        ? p.scriptId : undefined,
    categoryId,
    styleId: styleForCategory(categoryId, savedStyle),
    scenes: p.scenes,
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
