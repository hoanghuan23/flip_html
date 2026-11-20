export interface ReferenceImage {
  id: string;
  name: string;
  dataUrl: string;
}

export const MAX_IMAGE_FILE_BYTES = 5 * 1024 * 1024;
// Keep browser drafts small even when the source photos are large.
const MAX_PREVIEW_BYTES = 256 * 1024;
const IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export function validReferenceImages(value: unknown): value is ReferenceImage[] {
  return Array.isArray(value) &&
    value.every((image) => image && typeof image.id === "string" &&
      image.id.length > 0 && image.id.length <= 100 &&
      typeof image.name === "string" && image.name.length > 0 && image.name.length <= 255 &&
      typeof image.dataUrl === "string" && image.dataUrl.length <= MAX_PREVIEW_BYTES * 4 / 3 + 100 &&
      /^data:image\/(?:jpeg|png|webp);base64,[A-Za-z0-9+/]+={0,2}$/.test(image.dataUrl)) &&
    new Set(value.map((image) => image.id)).size === value.length;
}

export async function readReferenceImage(file: File): Promise<ReferenceImage> {
  if (!IMAGE_TYPES.has(file.type)) {
    throw new Error(`${file.name}: chỉ hỗ trợ ảnh JPG, PNG hoặc WEBP.`);
  }
  if (file.size > MAX_IMAGE_FILE_BYTES) {
    throw new Error(`${file.name}: ảnh vượt quá 5 MB.`);
  }
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    const scale = Math.min(1, 1280 / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Không thể đọc ảnh trên trình duyệt này.");
    let dataUrl = "";
    for (let attempt = 0; attempt < 5; attempt++) {
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      dataUrl = canvas.toDataURL("image/webp", 0.82);
      if (dataUrl.length <= MAX_PREVIEW_BYTES * 4 / 3) break;
      canvas.width = Math.max(1, Math.round(canvas.width * 0.75));
      canvas.height = Math.max(1, Math.round(canvas.height * 0.75));
    }
    const result = { id: crypto.randomUUID(), name: file.name.slice(0, 255), dataUrl };
    if (!validReferenceImages([result])) throw new Error("Ảnh quá phức tạp để lưu bản nháp.");
    return result;
  } catch (error) {
    throw new Error(`Không thể đọc ${file.name}. ${error instanceof Error ? error.message : "Hãy chọn ảnh khác."}`);
  } finally {
    URL.revokeObjectURL(url);
  }
}
