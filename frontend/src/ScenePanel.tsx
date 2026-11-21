import { useId, useState } from "react";
import { ChevronDown, ChevronUp, Clock3, MessageSquare, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { SectionHeading } from "./components";
import { safeSourceUrl, signature, type ProjectDraft } from "./types";
import s from "./Studio.module.css";

export default function ScenePanel({ project, selectedId, onSelect }: {
  project: ProjectDraft;
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const contentId = useId();
  const resolved = project.snapshot?.sourceSignature === signature(project) ? project.snapshot : undefined;
  const durationOf = (id: string, fallback: number) => resolved?.phases.find(p => p.id === id)?.duration ?? fallback;
  const total = project.scenes.reduce((sum, scene) => sum + durationOf(scene.id, scene.duration), 0);
  const estimated = !resolved && project.scenes.some(scene => scene.voiceover || scene.duration_status === "estimated");
  const research = project.scriptReview?.research;
  const warnings = project.scriptReview?.warnings ?? [];
  const readonlyNote = "Phiên bản hiện tại chỉ hỗ trợ xem kịch bản.";
  return (
    <section className={s.embeddedScript} id="kich-ban">
      <SectionHeading
        title="Dựng kịch bản từ câu chuyện của bạn"
        subtitle="Đọc nội dung và hình ảnh dự kiến của từng cảnh."
        action={<div className={s.scriptHeadingActions}>
          <button className={s.secondary} disabled title={readonlyNote}>
            <MessageSquare size={16} /> Chat với AI
          </button>
          <button
            type="button"
            className={s.scriptToggle}
            aria-label={expanded ? "Thu gọn kịch bản" : "Mở rộng kịch bản"}
            title={expanded ? "Thu gọn kịch bản" : "Mở rộng kịch bản"}
            aria-expanded={expanded}
            aria-controls={contentId}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </button>
        </div>}
      />
      <div id={contentId} hidden={!expanded}>
        <div className={s.demoNote}>
          <Sparkles size={15} />
          <span>{project.scriptId
            ? "Kịch bản đã được AI phân tích. Bảng dưới đây trích từ bản JSON chi tiết. "
            : "Đang xem kịch bản từ bản nháp đã lưu. "}
            {readonlyNote}
          </span>
        </div>
        {(warnings.length > 0 || (research && research.status !== "not_required")) && (
          <details className={s.scriptReview}>
            <summary>Nguồn tham khảo và cảnh báo{warnings.length > 0 ? ` (${warnings.length})` : ""}</summary>
            {warnings.length > 0 && <ul>{warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}
            {research?.status === "unverified" && <p>Nội dung chưa được kiểm chứng bằng nguồn web.</p>}
            {research?.status === "sources_reported" && <>
              <p>Nguồn do AI cung cấp, chưa được hệ thống xác minh độc lập.</p>
              <ul>{research.sources.map((source, index) => <li key={index}>
                {safeSourceUrl(source.url)
                  ? <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a>
                  : <span>{source.title}</span>}
                <ul>{source.claims.map((claim, i) => <li key={i}>{claim}</li>)}</ul>
              </li>)}</ul>
            </>}
          </details>
        )}
        <div className={s.scriptLayout}>
          <div className={s.sceneList}>
            <div className={s.tableHeading}>
              <span>CẢNH</span><span>THUYẾT MINH &amp; HÌNH ẢNH</span><span>{estimated ? "ƯỚC TÍNH" : "GIÂY"}</span><span />
            </div>
            {project.scenes.map((scene, index) => (
              <div key={scene.id} className={`${s.sceneRow} ${selectedId === scene.id ? s.activeRow : ""}`}>
                <button className={s.sceneNumber}
                  aria-label={`Chọn cảnh ${index + 1}: ${scene.name}`}
                  aria-pressed={selectedId === scene.id}
                  onClick={() => onSelect(scene.id)}>
                  {String(index + 1).padStart(2, "0")}
                </button>
                <div className={s.sceneCopy}>
                  <strong>{scene.name}</strong>
                  <p>{scene.voiceover || scene.narration}</p>
                  <small>{scene.description}</small>
                  {!!scene.annotations?.length && <div className={s.sceneAnnotations}>
                    <span>Chú giải trên màn hình</span>
                    <ul>{scene.annotations.map((note, i) => <li key={i}>{note.text}</li>)}</ul>
                  </div>}
                </div>
                <span className={s.duration}>{Number(durationOf(scene.id, scene.duration).toFixed(2))}s</span>
                <div className={s.rowActions}>
                  <button className={s.iconButton} disabled title={readonlyNote} aria-label={`Sửa cảnh ${index + 1}`}><Pencil size={16} /></button>
                  <button className={s.iconButton} disabled title={readonlyNote} aria-label={`Xóa cảnh ${index + 1}`}><Trash2 size={16} /></button>
                </div>
              </div>
            ))}
            <div className={s.tableFooter}>
              <button className={s.textButton} disabled title={readonlyNote}><Plus size={16} /> Thêm cảnh</button>
              <span><Clock3 size={14} /> {estimated ? "Ước tính " : ""}{Number(total.toFixed(2))} giây · {project.scenes.length} cảnh</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
