import { useEffect, useRef, useState } from "react";
import { Play, Pause, Film, RotateCcw, Pencil, MessageSquare,
  CheckCircle2, AlertCircle, Trash2 } from "lucide-react";
import { SectionHeading, timeLabel } from "./components";
import { signature, type ProjectDraft } from "./types";
import s from "./Studio.module.css";
import ExportControls from "./ExportControls";
import type { useExportJobs } from "./useExportJobs";

export default function PreviewPanel({ project, previewBusy, status, exporting }: {
  project: ProjectDraft;
  previewBusy: boolean;
  status?: string;
  exporting: ReturnType<typeof useExportJobs>;
}) {
  const snapshot = project.snapshot;
  const [phaseIndex, setPhaseIndex] = useState(0);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [frameLoaded, setFrameLoaded] = useState(false);
  const [frameError, setFrameError] = useState("");
  const frameRef = useRef<HTMLIFrameElement>(null);
  const stale = !!snapshot && snapshot.sourceSignature !== signature(project);
  const phase = snapshot?.phases[phaseIndex] || snapshot?.phases[0];
  const aiPreview = snapshot?.renderer?.startsWith("image-motion-");
  const readonlyNote = "Chỉnh sửa phase chưa được hỗ trợ.";

  useEffect(() => {
    setPlaying(false); setTime(0); setPhaseIndex(0);
  }, [snapshot?.id, project.id]);
  useEffect(() => {
    setFrameLoaded(false); setFrameError("");
  }, [phase?.url]);
  useEffect(() => {
    if (!phase || !playing) return;
    let frame = 0, last = performance.now();
    function tick(now: number) {
      const delta = Math.min((now - last) / 1000, .1);
      last = now;
      setTime((value) => Math.min(phase!.duration, value + delta));
      frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [phase?.url, phase?.duration, playing]);
  useEffect(() => {
    if (phase && time >= phase.duration) setPlaying(false);
  }, [time, phase]);
  useEffect(() => {
    if (frameLoaded) frameRef.current?.contentWindow?.postMessage({ t: time }, "*");
  }, [time, frameLoaded]);

  function choosePhase(index: number) {
    setPhaseIndex(index); setTime(0); setPlaying(false);
  }

  return (
    <section className={s.card} id="xem-truoc">
      <SectionHeading number={3} title="Nhìn ý tưởng chuyển động"
        subtitle="Xem từng cảnh rồi xuất toàn bộ phase thành video MP4."
        action={snapshot && <span className={stale ? s.warningBadge : s.successBadge}>
          {stale ? <AlertCircle size={13} /> : <CheckCircle2 size={13} />}
          {stale ? "Cần cập nhật preview" : `${snapshot.phases.length}/${snapshot.phases.length} phase sẵn sàng`}
        </span>}
      />
      {previewBusy && <p className={s.scriptStatus} role="status">{status || "Đang tạo đồ họa…"} Toàn bộ phase sẽ xuất hiện khi hoàn tất.</p>}
      {stale && <div className={s.warning}>
        <AlertCircle size={17} />
        <span>Kịch bản hoặc phong cách đã thay đổi. Bấm “Tạo đồ họa” ở mục 2 để cập nhật.</span>
        <button className={s.textButton} disabled title="Tạo đồ họa được thực hiện ở mục 2.">Cập nhật</button>
      </div>}
      {!snapshot ? <div className={s.emptyPreview}>
        <div className={s.emptyIcon}><Play size={28} strokeWidth={1.3} /></div>
        <h3>Sân khấu đang chờ câu chuyện của bạn</h3>
        <p>Duyệt kịch bản, chọn phong cách rồi bấm “Tạo đồ họa” ở mục 2.</p>
        <span className={s.outlineBadge}>HTML PREVIEW · 1920 × 1080</span>
      </div> : <>
        <div className={s.playerLayout}>
          <div className={s.phaseList} aria-label="Danh sách phase">
            {snapshot.phases.map((item, index) => <button key={item.id}
              className={`${s.phaseButton} ${phaseIndex === index ? s.activePhase : ""}`}
              aria-pressed={phaseIndex === index} onClick={() => choosePhase(index)}>
              <div className={s.phaseThumb}><Film size={24} /><span>{String(index + 1).padStart(2, "0")}</span></div>
              <div><strong>Phase {index + 1}</strong><small>{item.name}</small><span>{item.duration}s</span></div>
              {phaseIndex === index && <span className={s.phaseDot} />}
            </button>)}
          </div>
          <div className={s.playerColumn}>
            <div className={s.playerStage}>
              {phase && <iframe key={phase.url} ref={frameRef} src={phase.url} sandbox="allow-scripts"
                title={`Xem trước ${phase.name}`} onLoad={() => setFrameLoaded(true)}
                onError={() => setFrameError("Không tải được animation. Hãy tạo lại đồ họa ở mục 2.")} />}
              {frameError && <div className={s.playerError}>{frameError}</div>}
              <span className={s.playerBadge}>{aiPreview ? "ANIMATION AI" : "PREVIEW ĐÃ LƯU"}</span>
            </div>
            <div className={s.transport}>
              <button className={s.playButton} aria-label={playing ? "Tạm dừng preview" : "Phát preview"}
                disabled={!frameLoaded} onClick={() => {
                  if (phase && time >= phase.duration) setTime(0);
                  setPlaying(!playing);
                }}>{playing ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}</button>
              <input type="range" min="0" max={phase?.duration || 1} step="0.01" value={time}
                disabled={!frameLoaded} aria-label="Tua preview" onChange={(event) => setTime(Number(event.target.value))} />
              <output>{timeLabel(time)} <span>/ {timeLabel(phase?.duration || 0)}</span></output>
            </div>
            <div className={s.playerActions}>
              <button className={s.secondarySmall} disabled title={readonlyNote}><Pencil size={14} /> Sửa phase này</button>
              <button className={s.secondarySmall} disabled title={readonlyNote}><Trash2 size={14} /> Xóa phase này</button>
              <button className={s.secondarySmall} disabled title="Bấm Tạo đồ họa ở mục 2."><RotateCcw size={14} /> Tạo lại animation</button>
              <button className={s.secondarySmall} disabled title={readonlyNote}><MessageSquare size={14} /> Chat với AI</button>
            </div>
          </div>
        </div>
        <div className={s.previewDisclaimer}><Film size={14} />
          {aiPreview ? "Hình ảnh và animation được AI tạo từ kịch bản và phong cách đã chọn. " : "Preview từ phiên bản trước. "}
          Video xuất giữ nguyên animation và thời lượng từng phase, không có âm thanh.
        </div>
      </>}
      <ExportControls key={project.id} project={project} disabled={previewBusy || !!project.scriptJobId} exporting={exporting} />
    </section>
  );
}
