import { useState } from "react";
import { AlertCircle, CheckCircle2, Download, Film, LoaderCircle } from "lucide-react";
import { Modal } from "./components";
import { defaultConfig, signature, type ExportConfig, type ProjectDraft } from "./types";
import type { useExportJobs } from "./useExportJobs";
import s from "./Studio.module.css";

const stages: Record<string, string> = {
  queued: "Đang chờ xuất video…",
  preparing: "Đang chuẩn bị các phase…",
  checking: "Đang kiểm tra animation…",
  snapshotting: "Đang kiểm tra khung hình…",
  rendering: "Đang xuất MP4…",
  verifying: "Đang xác minh video…",
};

export default function ExportControls({ project, disabled, exporting }: {
  project: ProjectDraft;
  disabled: boolean;
  exporting: ReturnType<typeof useExportJobs>;
}) {
  const [open, setOpen] = useState(false);
  const [config, setConfig] = useState<ExportConfig>(defaultConfig);
  const [videoError, setVideoError] = useState(false);
  const snapshot = project.snapshot;
  const { job, busy, error, starting } = exporting;
  const stale = !!snapshot && snapshot.sourceSignature !== signature(project);
  const blocked = disabled || !snapshot || stale || busy;
  const result = job?.status === "succeeded" ? job.result : null;

  function openExport() {
    setConfig(project.lastExportConfig || {
      ...defaultConfig, filename: project.title.replace(/[/\\\x00\r\n]/g, "-").slice(0, 116),
    });
    setOpen(true);
  }

  return <>
    <div className={s.exportFooter}>
      <div><strong>Sẵn sàng mang câu chuyện đi xa?</strong><p>
        {stale ? "Cập nhật đồ họa theo kịch bản và phong cách mới trước khi xuất."
          : snapshot ? `Ghép toàn bộ ${snapshot.phases.length} phase thành một MP4 · ${snapshot.duration}s · Không âm thanh.`
          : "Tạo đồ họa để xuất toàn bộ phase thành video MP4."}
      </p></div>
      <button className={s.primary} disabled={blocked} onClick={openExport}>
        <Download size={18} /> {busy ? "Đang xuất video…" : "Xuất video"}
      </button>
    </div>
    {busy && <div className={s.renderProgress} role="status" aria-live="polite">
      <span className={s.renderIcon}><LoaderCircle size={24} className={s.spin} /></span>
      <div className={s.renderText}><strong>{stages[job?.stage || "queued"] || "Đang theo dõi xuất video…"}
        {typeof job?.progress === "number" ? ` ${Math.round(job.progress)}%` : ""}</strong>
        <p>Bạn có thể tiếp tục xem phase hoặc chuyển dự án. Video vẫn được xuất trên máy chủ.</p>
        <progress className={s.renderBar} max={100} value={job?.progress ?? undefined} aria-label="Tiến độ xuất video" />
      </div>
    </div>}
    {(error || job?.status === "failed") && <div className={s.renderFailed} role="alert">
      <span className={s.renderIcon}><AlertCircle size={24} /></span>
      <div className={s.renderText}><strong>{busy ? "Đang kết nối lại" : "Chưa thể xuất video"}</strong>
        <p>{error || job?.error || "Không thể hoàn tất xuất video. Hãy thử lại."}</p></div>
      {!busy && <button className={s.secondary} disabled={blocked} onClick={openExport}>Thử xuất lại</button>}
    </div>}
    {result && job && <div className={s.result}>
      <div className={s.resultHeading}>
        <CheckCircle2 className={s.resultIcon} size={25} />
        <div><h3>Video đã sẵn sàng</h3><p>{job.config.filename}</p></div>
      </div>
      {job.snapshotId !== snapshot?.id && <p className={s.resultNotice}>Video này được xuất từ bản preview trước của dự án.</p>}
      <video key={job.id} controls preload="metadata" src={result.videoUrl} aria-label="Video MP4 đã xuất"
        onError={() => setVideoError(true)} onLoadedMetadata={() => setVideoError(false)} />
      {videoError && <p className={s.resultNotice} role="alert">Không tải được video. Hãy thử tải MP4 hoặc xuất lại.</p>}
      <div className={s.resultFooter}>
        <span>{job.width} × {job.height} · {job.config.fps} FPS · {job.duration}s · {(result.bytes / 1024 / 1024).toFixed(1)} MB</span>
        <a className={s.primary} href={result.downloadUrl} download={job.config.filename}><Download size={17} /> Tải MP4</a>
      </div>
    </div>}
    {open && snapshot && <Modal title="Xuất video MP4" onClose={() => setOpen(false)}>
      <form className={s.exportForm} onSubmit={async (event) => {
        event.preventDefault();
        if (await exporting.create(config)) setOpen(false);
      }}>
        <div className={s.exportIntro}><Film size={23} /><p>Xuất toàn bộ {snapshot.phases.length} phase theo đúng thứ tự.<br />
          {snapshot.width} × {snapshot.height} · {snapshot.duration}s · Không âm thanh</p></div>
        <label>Tên file<input required maxLength={120} value={config.filename}
          pattern={String.raw`[^\/\\\r\n]+`} title="Tên file không chứa dấu / hoặc \\."
          onChange={(event) => setConfig({ ...config, filename: event.target.value })} /></label>
        <div className={s.configGrid}>
          <label>Tốc độ khung hình<select value={config.fps} onChange={(event) => setConfig({ ...config, fps: Number(event.target.value) as ExportConfig["fps"] })}>
            <option value={24}>24 FPS</option><option value={30}>30 FPS</option><option value={60}>60 FPS</option>
          </select></label>
          <label>Chất lượng<select value={config.quality} onChange={(event) => setConfig({ ...config, quality: event.target.value as ExportConfig["quality"] })}>
            <option value="draft">Bản nháp · Nhanh</option><option value="looks">Tiêu chuẩn</option><option value="delivery">Cao</option>
          </select></label>
        </div>
        {error && <p className={s.resultNotice} role="alert">{error}</p>}
        <div className={s.modalFooter}>
          <button type="button" className={s.secondary} onClick={() => setOpen(false)}>Đóng</button>
          <button type="submit" className={s.primary} disabled={blocked || !config.filename.trim()}>
            <Download size={17} /> {starting ? "Đang gửi yêu cầu…" : "Bắt đầu xuất"}
          </button>
        </div>
      </form>
    </Modal>}
  </>;
}
