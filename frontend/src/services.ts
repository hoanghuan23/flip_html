import type {
  ProjectDraft,
  Scene,
  PreviewSnapshot,
  ExportConfig,
  RenderJob,
} from "./types";
import { previewInput, signature } from "./types";

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

// Replace this service when the Python AI endpoints become available.
export interface VideoService {
  generateScript(content: string): Promise<Scene[]>;
  reviseScript(
    scene: Scene,
    instruction: string,
  ): Promise<{ scene?: Scene; reply: string }>;
}
export class MockVideoService implements VideoService {
  async generateScript(_content: string): Promise<Scene[]> {
    await new Promise((resolve) => setTimeout(resolve, 650));
    return [
      [
        "Bão bắt đầu từ đâu?",
        "Một cụm mây dông trên biển có thể phát triển thành bão nhiệt đới.",
        "Đại dương xanh, nắng ấm và những cụm mây đầu tiên.",
        6,
      ],
      [
        "Đại dương tiếp năng lượng",
        "Nước biển ấm cung cấp nhiệt và hơi ẩm cho hệ dông.",
        "Hơi ẩm bốc lên từ mặt biển, di chuyển về phía đám mây.",
        8,
      ],
      [
        "Mây dông lớn dần",
        "Không khí ẩm đi lên, lạnh đi rồi ngưng tụ thành các giọt mây.",
        "Các đám mây tụ lại, giọt nước xuất hiện và chuyển động xuống dưới.",
        8,
      ],
      [
        "Gió hội tụ về tâm",
        "Chênh lệch áp suất thúc đẩy không khí xung quanh đi về vùng áp thấp.",
        "Những dòng khí chuyển động quanh hệ mây đang phát triển.",
        8,
      ],
      [
        "Vòng tiếp sức của tự nhiên",
        "Khi điều kiện thuận lợi kéo dài, hệ dông có thể mạnh lên thành bão.",
        "Toàn cảnh biển và mây; kết thúc bằng lời nhắc theo dõi dự báo thời tiết.",
        6,
      ],
    ].map(([name, narration, description, duration]) => ({
      id: crypto.randomUUID(),
      name: String(name),
      narration: String(narration),
      description: String(description),
      duration: Number(duration),
    }));
  }
  async reviseScript(scene: Scene, instruction: string) {
    await new Promise((resolve) => setTimeout(resolve, 400));
    if (/rút ngắn|ngắn hơn|giảm thời lượng/i.test(instruction)) {
      const duration = Math.max(
        0.1,
        Math.round(scene.duration * 0.7 * 10) / 10,
      );
      return {
        scene: { ...scene, duration },
        reply: `Đã giảm thời lượng “${scene.name}” còn ${duration} giây. Đây là chỉnh sửa mẫu; bạn có thể sửa tiếp trong bảng.`,
      };
    }
    if (/vui|viết lại|giải thích/i.test(instruction)) {
      const narration = /vui/i.test(instruction)
        ? `Cùng khám phá nhé! ${scene.narration.replace(/^Cùng khám phá nhé! /, "")}`
        : `Hãy cùng tìm hiểu: ${scene.name.toLocaleLowerCase("vi")}.`;
      return {
        scene: { ...scene, narration },
        reply: `Đã cập nhật chữ giải thích cho “${scene.name}” bằng nội dung mẫu.`,
      };
    }
    return {
      reply:
        "Trợ lý demo hỗ trợ: “Rút ngắn cảnh”, “Đổi giọng vui hơn” hoặc “Viết lại chữ giải thích”. Hãy chọn một cảnh rồi thử nhé.",
    };
  }
}
export const videoService: VideoService = new MockVideoService();
export async function generatePreview(
  p: ProjectDraft,
): Promise<PreviewSnapshot> {
  return {
    ...(await api<PreviewSnapshot>("/api/previews", previewInput(p))),
    sourceSignature: signature(p),
  };
}
export const exportVideo = (snapshotId: string, config: ExportConfig) =>
  api<RenderJob>("/api/exports", { snapshotId, config });
