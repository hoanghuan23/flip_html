import { useRef, useState, type DragEvent, type ReactNode } from "react";
import {
  UploadCloud,
  FileText,
  X,
  AlignLeft,
  ArrowUpRight,
  Sparkles,
} from "lucide-react";
import { SectionHeading, errorText } from "./components";
import type { ProjectDraft } from "./types";
import ReferenceImages from "./ReferenceImagesPanel";
import SourceTextInput from "./SourceTextInput";
import s from "./Studio.module.css";

export default function InputPanel({
  project,
  patch,
  notify,
  onGenerate,
  busy,
  status,
  statusError,
  children,
}: {
  project: ProjectDraft;
  patch: (p: Partial<ProjectDraft>) => void;
  notify: (t: string, error?: boolean) => void;
  onGenerate: () => void;
  busy: boolean;
  status?: string;
  statusError?: boolean;
  children?: ReactNode;
}) {
  const [tab, setTab] = useState<"text" | "file">("text");
  const [dragging, setDragging] = useState(false);
  const [reading, setReading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  async function read(file?: File) {
    if (!file || busy || reading) return;
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
        "Đã đọc văn bản từ file. Chuyển sang “Nhập văn bản” nếu muốn chỉnh sửa.",
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
      <div
        className={s.tabs}
        role="tablist"
        aria-label="Cách nhập nội dung"
        onKeyDown={(event) => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
            return;
          }
          event.preventDefault();
          let next: "text" | "file" = tab === "text" ? "file" : "text";
          if (event.key === "Home") next = "text";
          if (event.key === "End") next = "file";
          setTab(next);
          document.getElementById(`input-tab-${next}`)?.focus();
        }}
      >
        <button
          id="input-tab-text"
          role="tab"
          aria-selected={tab === "text"}
          tabIndex={tab === "text" ? 0 : -1}
          aria-controls="input-text"
          onClick={() => setTab("text")}
          className={tab === "text" ? s.tabActive : ""}
        >
          <AlignLeft size={16} /> Nhập văn bản
        </button>
        <button
          id="input-tab-file"
          role="tab"
          aria-selected={tab === "file"}
          tabIndex={tab === "file" ? 0 : -1}
          aria-controls="input-file"
          onClick={() => setTab("file")}
          className={tab === "file" ? s.tabActive : ""}
        >
          <UploadCloud size={16} /> Tải tài liệu
        </button>
      </div>
      <div className={s.inputLayout}>
        <div
          id="input-file"
          role="tabpanel"
          aria-labelledby="input-tab-file"
          hidden={tab !== "file"}
          className={`${s.dropzone} ${dragging ? s.dragging : ""} ${tab === "file" ? s.dropzoneActive : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            if (busy) return;
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
            disabled={busy || reading}
            accept=".txt,.docx"
            onChange={(e) => void read(e.target.files?.[0])}
          />
          <button
            className={s.secondary}
            disabled={busy || reading}
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
                disabled={busy}
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
        <div
          id="input-text"
          role="tabpanel"
          aria-labelledby="input-tab-text"
          hidden={tab !== "text"}
          className={s.textInput}
        >
          <label htmlFor="source-text" className={s.fieldLabel}>
            VĂN BẢN ĐẦU VÀO
          </label>
          <SourceTextInput
            key={project.id}
            disabled={busy || reading}
            value={project.sourceContent}
            images={project.referenceImages || []}
            onChange={(sourceContent) => patch({ sourceContent })}
          />
          <div className={s.inputMeta}>
            <span>
              {project.sourceContent.length.toLocaleString("vi")} ký tự
            </span>
            <span>AI tự nhận diện nội dung và ước tính thời lượng</span>
          </div>
        </div>
        <ReferenceImages
          key={project.id}
          projectId={project.id}
          images={project.referenceImages || []}
          lastNumber={project.lastReferenceImageNumber ?? 0}
          onChange={(referenceImages, lastReferenceImageNumber) => patch({ referenceImages, lastReferenceImageNumber })}
          notify={notify}
          disabled={busy || reading}
        />
          <div className={s.inputActions}>
            <button
              className={s.textButton}
              disabled={busy || reading}
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
            <button
              type="button"
              className={s.primary}
              disabled={!project.sourceContent.trim() || busy || reading}
              onClick={onGenerate}
              aria-busy={busy}
            >
              <Sparkles size={17} className={busy ? s.spin : ""} />
              {busy ? "Đang tạo kịch bản…" : "Tạo kịch bản"}
            </button>
          </div>
      </div>
      {status && <p className={s.scriptStatus} role={statusError ? "alert" : "status"}>
        {status}
      </p>}
      {children}
    </section>
  );
}
