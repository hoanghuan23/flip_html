import { useCallback, useEffect, useRef, useState } from "react";
import {
  Play,
  Pause,
  Download,
  Film,
  RotateCcw,
  Pencil,
  MessageSquare,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Settings2,
  ArrowUpRight,
  Clock3,
} from "lucide-react";
import { Modal, SectionHeading, Art, timeLabel, errorText } from "./components";
import { api, ApiError, exportVideo } from "./services";
import {
  defaultConfig,
  signature,
  type ExportConfig,
  type ProjectDraft,
  type RenderJob,
} from "./types";
import s from "./Studio.module.css";

const stages: Record<string, string> = {
  queued: "Đang chờ lượt xuất",
  preparing: "Chuẩn bị project HyperFrames",
  checking: "Kiểm tra animation",
  snapshotting: "Kiểm tra khung hình",
  rendering: "Đang render video",
  verifying: "Xác minh MP4",
  complete: "Video đã sẵn sàng",
  failed: "Chưa thể hoàn tất xuất video",
};
const qualities = { draft: "Nháp", looks: "Tiêu chuẩn", delivery: "Cao" };
export default function PreviewPanel({
  project,
  patch,
  notify,
  onEdit,
  onRegenerate,
  previewBusy,
}: {
  project: ProjectDraft;
  patch: (p: Partial<ProjectDraft>) => void;
  notify: (t: string, error?: boolean) => void;
  onEdit: (id: string, chat?: boolean) => void;
  onRegenerate: () => void;
  previewBusy: boolean;
}) {
  const snapshot = project.snapshot;
  const [phaseIndex, setPhaseIndex] = useState(0);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [config, setConfig] = useState<ExportConfig>(defaultConfig);
  const [job, setJob] = useState<RenderJob>();
  const [pollError, setPollError] = useState("");
  const [elapsedNow, setElapsedNow] = useState(Date.now());
  const frameRef = useRef<HTMLIFrameElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const [frameLoaded, setFrameLoaded] = useState(false);
  const [frameError, setFrameError] = useState("");
  const stale = !!snapshot && snapshot.sourceSignature !== signature(project);
  const phase = snapshot?.phases[phaseIndex] || snapshot?.phases[0];
  const activeJob = job?.status === "queued" || job?.status === "running";
  const valid = !!snapshot && !stale && !previewBusy;

  useEffect(() => {
    setPlaying(false);
    setTime(0);
    setPhaseIndex(0);
    setExportOpen(false);
  }, [snapshot?.id, project.id]);
  useEffect(() => {
    setFrameLoaded(false);
    setFrameError("");
  }, [phase?.url]);
  useEffect(() => {
    if (!phase || !playing) return;
    let frame = 0,
      last = performance.now();
    function tick(now: number) {
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      setTime((t) => Math.min(phase!.duration, t + dt));
      frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [phase?.url, phase?.duration, playing]);
  useEffect(() => {
    if (phase && time >= phase.duration) setPlaying(false);
  }, [time, phase]);
  useEffect(() => {
    if (frameLoaded && frameRef.current?.contentWindow)
      frameRef.current.contentWindow.postMessage({ t: time }, "*");
  }, [time, frameLoaded]);

  useEffect(() => {
    setJob(undefined);
    setPollError("");
    if (!project.jobId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const value = await api<RenderJob>(`/api/exports/${project.jobId}`);
        if (stopped) return;
        setJob(value);
        setPollError("");
        if (["queued", "running"].includes(value.status))
          timer = setTimeout(poll, 2000);
      } catch (e) {
        if (stopped) return;
        setPollError(errorText(e));
        if (e instanceof ApiError && e.status === 404) setJob(undefined);
        if (!(e instanceof ApiError && e.status === 404))
          timer = setTimeout(poll, 2000);
      }
    }
    void poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [project.jobId]);
  useEffect(() => {
    if (!activeJob) return;
    setElapsedNow(Date.now());
    const timer = setInterval(() => setElapsedNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [activeJob]);
  useEffect(() => {
    if (job?.status === "succeeded")
      resultRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
  }, [job?.id, job?.status]);

  async function startExport(retry = false) {
    if (!valid || exporting || activeJob) return;
    const selected = retry && job ? job.config : config;
    setExportError("");
    if (!selected.filename.trim() || /[/\\\x00\r\n]/.test(selected.filename)) {
      setExportError("Hãy nhập tên file hợp lệ, không chứa dấu / hoặc \\.");
      return;
    }
    setExporting(true);
    try {
      const value = await exportVideo(snapshot!.id, selected);
      patch({ jobId: value.id, lastExportConfig: selected });
      setJob(value);
      setExportOpen(false);
      setPollError("");
    } catch (e) {
      setExportError(errorText(e));
      notify(errorText(e), true);
      if (e instanceof ApiError && e.status === 404) {
        patch({ snapshot: undefined });
        setExportOpen(false);
      }
    } finally {
      setExporting(false);
    }
  }
  const openExport = useCallback(() => {
    setExportError("");
    setConfig(
      project.lastExportConfig || {
        ...defaultConfig,
        filename:
          project.title === "Dự án chưa đặt tên"
            ? "video-cua-toi"
            : project.title,
      },
    );
    setExportOpen(true);
  }, [project.lastExportConfig, project.title]);
  const choosePhase = (i: number) => {
    setPhaseIndex(i);
    setTime(0);
    setPlaying(false);
  };
  return (
    <section className={s.card} id="xem-truoc">
      <SectionHeading
        number={3}
        title="Nhìn ý tưởng chuyển động"
        subtitle="Duyệt từng cảnh. Khi đã ưng ý, hãy biến nó thành một video hoàn chỉnh."
        action={
          snapshot && (
            <span className={stale ? s.warningBadge : s.successBadge}>
              {stale ? <AlertCircle size={13} /> : <CheckCircle2 size={13} />}
              {stale
                ? "Cần cập nhật preview"
                : `${snapshot.phases.length}/${snapshot.phases.length} phase sẵn sàng`}
            </span>
          )
        }
      />
      {stale && (
        <div className={s.warning}>
          <AlertCircle size={17} />
          <span>
            Kịch bản hoặc phong cách đã thay đổi. Hãy tạo lại animation trước
            khi xuất.
          </span>
          <button
            className={s.textButton}
            onClick={onRegenerate}
            disabled={previewBusy}
          >
            Cập nhật
          </button>
        </div>
      )}
      {!snapshot ? (
        <div className={s.emptyPreview}>
          <div className={s.emptyIcon}>
            <Play size={28} strokeWidth={1.3} />
          </div>
          <h3>Sân khấu đang chờ câu chuyện của bạn</h3>
          <p>Duyệt kịch bản, chọn phong cách rồi bấm “Tạo đồ họa” ở mục 2.</p>
          <span className={s.outlineBadge}>HTML PREVIEW · 1920 × 1080</span>
        </div>
      ) : (
        <>
          <div className={s.playerLayout}>
            <div className={s.phaseList} aria-label="Danh sách phase">
              {snapshot.phases.map((p, i) => (
                <button
                  key={p.id}
                  className={`${s.phaseButton} ${phaseIndex === i ? s.activePhase : ""}`}
                  aria-pressed={phaseIndex === i}
                  onClick={() => choosePhase(i)}
                >
                  <div className={s.phaseThumb}>
                    <Art styleId={project.styleId} />
                    <span>{String(i + 1).padStart(2, "0")}</span>
                  </div>
                  <div>
                    <strong>Phase {i + 1}</strong>
                    <small>{p.name}</small>
                    <span>{p.duration}s</span>
                  </div>
                  {phaseIndex === i && <span className={s.phaseDot} />}
                </button>
              ))}
            </div>
            <div className={s.playerColumn}>
              <div className={s.playerStage}>
                {phase && (
                  <iframe
                    key={phase.url}
                    ref={frameRef}
                    src={phase.url}
                    sandbox="allow-scripts"
                    title={`Xem trước ${phase.name}`}
                    onLoad={() => setFrameLoaded(true)}
                    onError={() =>
                      setFrameError(
                        "Không tải được preview. Hãy tạo lại animation.",
                      )
                    }
                  />
                )}
                {frameError && (
                  <div className={s.playerError}>{frameError}</div>
                )}
                <span className={s.playerBadge}>ANIMATION MINH HỌA</span>
              </div>
              <div className={s.transport}>
                <button
                  className={s.playButton}
                  aria-label={playing ? "Tạm dừng preview" : "Phát preview"}
                  onClick={() => {
                    if (phase && time >= phase.duration) setTime(0);
                    setPlaying(!playing);
                  }}
                  disabled={!frameLoaded}
                >
                  {playing ? (
                    <Pause size={18} fill="currentColor" />
                  ) : (
                    <Play size={18} fill="currentColor" />
                  )}
                </button>
                <input
                  type="range"
                  min="0"
                  max={phase?.duration || 1}
                  step="0.01"
                  value={time}
                  aria-label="Tua preview"
                  onChange={(e) => setTime(Number(e.target.value))}
                />
                <output>
                  {timeLabel(time)}{" "}
                  <span>/ {timeLabel(phase?.duration || 0)}</span>
                </output>
              </div>
              <div className={s.playerActions}>
                <button
                  className={s.secondarySmall}
                  onClick={() => phase && onEdit(phase.id)}
                >
                  <Pencil size={14} /> Sửa phase này
                </button>
                <button
                  className={s.secondarySmall}
                  disabled={previewBusy}
                  onClick={onRegenerate}
                >
                  <RotateCcw size={14} /> Tạo lại animation
                </button>
                <button
                  className={s.secondarySmall}
                  onClick={() => phase && onEdit(phase.id, true)}
                >
                  <MessageSquare size={14} /> Chat với AI
                </button>
              </div>
            </div>
          </div>
          <div className={s.previewDisclaimer}>
            <Film size={14} /> Preview minh họa theo mẫu · Video xuất giữ nguyên
            animation và chữ bạn đang duyệt.
          </div>
        </>
      )}
      <div className={s.exportFooter}>
        <div>
          <strong>Sẵn sàng mang câu chuyện đi xa?</strong>
          <p>Xuất MP4 bằng HyperFrames, xem ngay và tải về thiết bị.</p>
        </div>
        <button
          className={s.primary}
          onClick={openExport}
          disabled={!valid || exporting || activeJob}
        >
          <Download size={18} /> Xuất video <ArrowUpRight size={16} />
        </button>
      </div>
      {pollError && (
        <div className={s.warning} role="alert">
          <AlertCircle size={17} />
          <span>{pollError}</span>
          {!activeJob && (
            <button
              className={s.textButton}
              onClick={() => patch({ jobId: undefined })}
            >
              Đóng
            </button>
          )}
        </div>
      )}
      {job && job.status !== "succeeded" && (
        <div
          className={
            job.status === "failed" ? s.renderFailed : s.renderProgress
          }
          role="status"
        >
          <div className={s.renderIcon}>
            {job.status === "failed" ? (
              <AlertCircle size={23} />
            ) : (
              <Loader2 size={23} className={s.spin} />
            )}
          </div>
          <div className={s.renderText}>
            <strong>{stages[job.stage] || "Đang xử lý"}</strong>
            <p>
              {job.status === "failed"
                ? job.error
                : `${job.config.fps} fps · ${qualities[job.config.quality]}${job.progress != null ? ` · ${Math.round(job.progress)}%` : ""} · ${Math.max(0, Math.floor((elapsedNow - Date.parse(job.startedAt || job.createdAt)) / 1000))} giây đã chạy`}
            </p>
            {activeJob && job.progress != null && (
              <progress
                className={s.renderBar}
                max={100}
                value={job.progress}
                aria-label="Tiến độ xuất video"
              />
            )}
            {activeJob && (
              <div className={s.stageDots}>
                {["preparing", "checking", "rendering", "verifying"].map(
                  (stage, i) => (
                    <span
                      key={stage}
                      className={
                        [
                          "preparing",
                          "checking",
                          "snapshotting",
                          "rendering",
                          "verifying",
                        ].indexOf(job.stage) >= [0, 1, 3, 4][i]
                          ? s.stageDone
                          : ""
                      }
                    />
                  ),
                )}
              </div>
            )}
          </div>
          {job.status === "failed" && (
            <button
              className={s.secondarySmall}
              disabled={!valid || exporting}
              onClick={() => void startExport(true)}
            >
              <RotateCcw size={14} /> Thử lại
            </button>
          )}
        </div>
      )}
      {job?.status === "succeeded" && job.result && (
        <div ref={resultRef} className={s.result}>
          <div className={s.resultHeading}>
            <span className={s.resultIcon}>
              <CheckCircle2 size={23} />
            </span>
            <div>
              <h3>Video hoàn chỉnh</h3>
              <p>
                {job.config.filename} ·{" "}
                {(job.result.bytes / 1024 / 1024).toFixed(1)} MB
              </p>
            </div>
            <span className={s.successBadge}>Đã xuất thành công</span>
          </div>
          {job.snapshotId !== snapshot?.id || stale ? (
            <p className={s.resultNotice}>
              Video thuộc bản preview đã xuất trước đó. Tạo preview mới và xuất
              lại để áp dụng các chỉnh sửa hiện tại.
            </p>
          ) : null}
          <video
            key={job.id}
            controls
            playsInline
            preload="metadata"
            src={job.result.videoUrl}
            onError={() =>
              notify(
                "Không tải được MP4. File có thể đã bị xóa trên máy chủ; hãy xuất lại.",
                true,
              )
            }
          />
          <div className={s.resultFooter}>
            <span>
              {job.width} × {job.height} · {job.config.fps} fps ·{" "}
              {timeLabel(job.duration)} · {qualities[job.config.quality]}
            </span>
            <div className={s.buttonRow}>
              <button
                className={s.secondary}
                disabled={!valid || exporting || activeJob}
                onClick={openExport}
              >
                Xuất bản khác
              </button>
              <a className={s.primary} href={job.result.downloadUrl} download>
                <Download size={17} /> Tải video xuống
              </a>
            </div>
          </div>
        </div>
      )}
      {exportOpen && (
        <Modal
          title="Xuất video của bạn"
          onClose={() => {
            if (!exporting) setExportOpen(false);
          }}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void startExport();
            }}
            className={s.exportForm}
          >
            <div className={s.exportIntro}>
              <span className={s.aiIcon}>
                <Settings2 size={23} />
              </span>
              <p>
                Một bước cuối để ý tưởng thành video.
                <br />
                <strong>
                  {snapshot?.phases.length} cảnh ·{" "}
                  {timeLabel(snapshot?.duration || 0)}
                </strong>
              </p>
            </div>
            <label>
              Tên file
              <input
                autoFocus
                required
                maxLength={120}
                value={config.filename}
                onChange={(e) =>
                  setConfig({ ...config, filename: e.target.value })
                }
              />
              <small>Tự thêm đuôi .mp4 khi tải xuống</small>
            </label>
            <div className={s.configGrid}>
              <label>
                Tốc độ khung hình
                <select
                  value={config.fps}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      fps: Number(e.target.value) as ExportConfig["fps"],
                    })
                  }
                >
                  {[24, 30, 60].map((fps) => (
                    <option key={fps} value={fps}>
                      {fps} fps
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Chất lượng
                <select
                  value={config.quality}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      quality: e.target.value as ExportConfig["quality"],
                    })
                  }
                >
                  {Object.entries(qualities).map(([id, name]) => (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className={s.configSummary}>
              <span>
                Định dạng<strong>MP4</strong>
              </span>
              <span>
                Kích thước<strong>1920 × 1080 · 16:9</strong>
              </span>
              <span>
                Nội dung<strong>Toàn bộ phase</strong>
              </span>
              <span>
                Âm thanh<strong>Không có</strong>
              </span>
            </div>
            <p className={s.configHint}>
              <Clock3 size={15} /> Render trên máy chủ local. FPS và chất lượng
              cao cần thêm thời gian xử lý.
            </p>
            {exportError && (
              <div className={s.warning} role="alert">
                {exportError}
              </div>
            )}
            <div className={s.modalFooter}>
              <button
                type="button"
                className={s.secondary}
                disabled={exporting}
                onClick={() => setExportOpen(false)}
              >
                Để sau
              </button>
              <button
                className={s.primary}
                disabled={exporting || !config.filename.trim()}
              >
                {exporting ? (
                  <Loader2 size={17} className={s.spin} />
                ) : (
                  <Film size={17} />
                )}
                {exporting ? "Đang tạo tác vụ…" : "Bắt đầu xuất"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </section>
  );
}
