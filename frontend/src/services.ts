import type {
  ProjectDraft,
  ScriptJob,
  GraphicsJob,
  ExportConfig,
  RenderJob,
} from "./types";
import type { ReferenceImage } from "./referenceImages";
import { numberReferenceImages } from "./referenceImages";
import { previewInput } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(
      path,
      body === undefined
        ? undefined
        : {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
    );
  } catch {
    throw new Error(
      "Không kết nối được máy chủ. Hãy kiểm tra API Python đang chạy và thử lại.",
    );
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    throw new ApiError(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => d.msg).join(" · ")
          : "Máy chủ không thể xử lý yêu cầu. Hãy thử lại.",
      response.status,
    );
  }
  return data as T;
}

export const createScriptJob = (projectId: string, content: string, images: ReferenceImage[] = []) =>
  api<ScriptJob>("/api/scripts", { projectId, content,
    ...(images.length ? {referenceImages: numberReferenceImages(images)} : {}) });
export const getScriptJob = (id: string) => api<ScriptJob>(`/api/scripts/${id}`);
export const scriptStages: Record<string, string> = {
  queued: "Đang chờ tạo kịch bản…",
  validating: "AI đang kiểm tra nội dung…",
  generating: "AI đang tạo kịch bản…",
  saving: "Đang lưu kịch bản…",
};
export const createGraphicsJob = (p: ProjectDraft) =>
  api<GraphicsJob>("/api/graphics", previewInput(p));
export const getGraphicsJob = (id: string) => api<GraphicsJob>(`/api/graphics/${id}`);
export const exportVideo = (snapshotId: string, config: ExportConfig) =>
  api<RenderJob>("/api/exports", { snapshotId, config });
export const getRenderJob = (id: string) => api<RenderJob>(`/api/exports/${id}`);
