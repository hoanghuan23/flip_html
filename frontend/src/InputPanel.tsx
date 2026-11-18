import { useRef, useState, type DragEvent } from "react";
import {
  UploadCloud,
  FileText,
  X,
  AlignLeft,
  ArrowUpRight,
} from "lucide-react";
import { SectionHeading, errorText } from "./components";
import type { ProjectDraft } from "./types";
import s from "./Studio.module.css";

export default function InputPanel({
  project,
  patch,
  notify,
}: {
  project: ProjectDraft;
  patch: (p: Partial<ProjectDraft>) => void;
  notify: (t: string, error?: boolean) => void;
}) {
  const [tab, setTab] = useState<"text" | "file">("text");
  const [dragging, setDragging] = useState(false);
  const [reading, setReading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  async function read(file?: File) {
    if (!file) return;
    if (!/\.(txt|docx)$/i.test(file.name)) {
      notify("Chọn file .txt hoặc .docx.", true);
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      notify("File vượt quá 5 MB. Hãy chọn file nhỏ hơn.", true);
      return;
    }
    setReading(true);
    try {
      const content = /\.txt$/i.test(file.name)
        ? await file.text()
        : (
            await (
              await import("mammoth")
            ).extractRawText({ arrayBuffer: await file.arrayBuffer() })
          ).value;
      if (!content.trim()) throw new Error("File không có văn bản để sử dụng.");
      patch({ sourceContent: content, sourceFilename: file.name });
      notify(
        "Đã đọc văn bản từ file. Bạn có thể chỉnh sửa trước khi tiếp tục.",
      );
    } catch (e) {
      notify(`Không thể đọc tài liệu. ${errorText(e)}`, true);
    } finally {
      setReading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }
  function drop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    void read(e.dataTransfer.files[0]);
  }
  return (
    <section className={s.card} id="noi-dung">
      <SectionHeading
        number={1}
        title="Bắt đầu từ ý tưởng của bạn"
        subtitle="Một bài viết, một câu chuyện, hay đơn giản là điều bạn muốn chia sẻ."
      />
      <div className={s.tabs} role="group" aria-label="Cách nhập nội dung">
        <button
          aria-pressed={tab === "text"}
          aria-controls="input-text"
          onClick={() => {
            setTab("text");
            document.getElementById("source-text")?.focus();
          }}
          className={tab === "text" ? s.tabActive : ""}
        >
          <AlignLeft size={16} /> Nhập văn bản
        </button>
        <button
          aria-pressed={tab === "file"}
          aria-controls="input-file"
          onClick={() => {
            setTab("file");
            fileRef.current?.click();
          }}
          className={tab === "file" ? s.tabActive : ""}
        >
          <UploadCloud size={16} /> Tải tài liệu
        </button>
      </div>
      <div className={s.inputLayout}>
        <div
          id="input-file"
          className={`${s.dropzone} ${dragging ? s.dragging : ""} ${tab === "file" ? s.dropzoneActive : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={drop}
        >
          <div className={s.uploadIcon}>
            <UploadCloud size={26} strokeWidth={1.5} />
          </div>
          <strong>
            {reading ? "Đang đọc tài liệu…" : "Thả câu chuyện vào đây"}
          </strong>
          <p>
            Kéo thả tài liệu của bạn
            <br />
            hoặc chọn từ thiết bị
          </p>
          <input
            ref={fileRef}
            hidden
            type="file"
            accept=".txt,.docx"
            onChange={(e) => void read(e.target.files?.[0])}
          />
          <button
            className={s.secondary}
            disabled={reading}
            onClick={() => fileRef.current?.click()}
          >
            Chọn file <ArrowUpRight size={15} />
          </button>
          <small>.TXT, .DOCX · tối đa 5 MB</small>
          {project.sourceFilename && (
            <div className={s.fileChip}>
              <FileText size={15} />
              <span>{project.sourceFilename}</span>
              <button
                aria-label="Xóa tài liệu và văn bản"
                onClick={() =>
                  patch({ sourceFilename: undefined, sourceContent: "" })
                }
              >
                <X size={14} />
              </button>
            </div>
          )}
        </div>
        <div id="input-text" className={s.textInput}>
          <label htmlFor="source-text" className={s.fieldLabel}>
            VĂN BẢN ĐẦU VÀO
          </label>
          <textarea
            id="source-text"
            value={project.sourceContent}
            onChange={(e) => patch({ sourceContent: e.target.value })}
            placeholder="Dán bài viết, kể một câu chuyện hoặc viết ý tưởng của bạn ở đây…"
          />
          <div className={s.inputMeta}>
            <span>
              {project.sourceContent.length.toLocaleString("vi")} ký tự
            </span>
            <span>Thời lượng theo kịch bản</span>
          </div>
          <button
            className={s.textButton}
            onClick={() =>
              patch({
                sourceContent:
                  "Bão nhiệt đới hình thành như thế nào? Hãy giải thích vai trò của nước biển ấm, hơi ẩm và gió trong quá trình một cụm mây dông phát triển thành bão.",
                sourceFilename: undefined,
              })
            }
          >
            Thử với nội dung mẫu: Bão nhiệt đới <ArrowUpRight size={13} />
          </button>
        </div>
      </div>
    </section>
  );
}
