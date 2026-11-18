export type StyleId =
  | "cartoon"
  | "dark"
  | "watercolor"
  | "pixel"
  | "sketch"
  | "flat";
export interface Scene {
  id: string;
  name: string;
  narration: string;
  description: string;
  duration: number;
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
  styleId: StyleId;
  scenes: Scene[];
  messages: ChatMessage[];
  updatedAt: string;
  snapshot?: PreviewSnapshot;
  jobId?: string;
  lastExportConfig?: ExportConfig;
}
export const defaultConfig: ExportConfig = {
  filename: "video-cua-toi",
  fps: 30,
  quality: "delivery",
};
export const styles: {
  id: StyleId;
  name: string;
  description: string;
  colors: string[];
}[] = [
  {
    id: "cartoon",
    name: "Hoạt hình 2D",
    description:
      "Nét vẽ thân thiện, màu sắc ấm áp. Dành cho những câu chuyện và nội dung giải thích dễ hiểu.",
    colors: ["#f4ede3", "#237c83", "#ffd18c"],
  },
  {
    id: "dark",
    name: "Tối giản tối",
    description:
      "Tương phản sâu, màu tím và điểm sáng tinh tế. Một góc nhìn hiện đại, tập trung vào nội dung.",
    colors: ["#111b35", "#4233a7", "#a9a2ff"],
  },
  {
    id: "watercolor",
    name: "Màu nước",
    description:
      "Sắc xanh dịu nhẹ, không gian thoáng và những mảng màu mềm. Phù hợp câu chuyện thiên nhiên.",
    colors: ["#edf5ee", "#81aab4", "#ecd7a8"],
  },
  {
    id: "pixel",
    name: "Pixel art",
    description:
      "Cảm hứng trò chơi cổ điển với sắc xanh tím và những chi tiết hình học vui nhộn.",
    colors: ["#242740", "#5262a5", "#f8be72"],
  },
  {
    id: "sketch",
    name: "Phác thảo giấy",
    description:
      "Tông giấy ấm, nét vẽ mộc mạc. Biến ý tưởng thành một trang sổ tay chuyển động.",
    colors: ["#f2eadc", "#a59b83", "#d0b78a"],
  },
  {
    id: "flat",
    name: "Flat đậm màu",
    description:
      "Mảng màu rõ ràng, cam san hô và vàng nổi bật. Truyền đạt ý tưởng bằng hình khối đơn giản.",
    colors: ["#fff0e8", "#e46f65", "#ffd16d"],
  },
];
export const newProject = (): ProjectDraft => ({
  id: crypto.randomUUID(),
  title: "Dự án chưa đặt tên",
  sourceContent: "",
  styleId: "cartoon",
  scenes: [],
  messages: [],
  updatedAt: new Date().toISOString(),
});
export const previewInput = (p: ProjectDraft) => ({
  projectId: p.id,
  title: p.title,
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
  if (
    typeof p.id !== "string" ||
    !p.id ||
    typeof p.title !== "string" ||
    !p.title.trim() ||
    p.title.length > 160 ||
    typeof p.sourceContent !== "string" ||
    !styles.some((s) => s.id === p.styleId) ||
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
  // Rebuild optional data explicitly; imported files never supply playable URLs.
  return {
    id: p.id,
    title: p.title,
    sourceContent: p.sourceContent,
    styleId: p.styleId,
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
