import { useCallback, useEffect, useRef, useState } from "react";
import {
  Aperture,
  FolderOpen,
  Check,
  Plus,
  Upload,
  Pencil,
  Trash2,
  ArrowRight,
  Sparkles,
  X,
  CircleHelp,
} from "lucide-react";
import { useStudio } from "./store";
import {
  newProject,
  parseDraft,
  type ProjectDraft,
  type PreviewSnapshot,
  type ScriptJob,
} from "./types";
import { api, ApiError, createScriptJob, getScriptJob, scriptStages } from "./services";
import { Modal, errorText } from "./components";
import InputPanel from "./InputPanel";
import { StylePicker } from "./components";
import { styleForCategory } from "./styleConfig";
import ScenePanel from "./ScenePanel";
import PreviewPanel from "./PreviewPanel";
import s from "./Studio.module.css";
import { useGraphicsJobs } from "./useGraphicsJobs";
import { useExportJobs } from "./useExportJobs";

export default function App() {
  const { state, dispatch, saveStatus } = useStudio();
  const project = state.projects.find((p) => p.id === state.activeId)!;
  const [toast, setToast] = useState<{ text: string; error: boolean }>();
  const notify = useCallback(
    (text: string, error = false) => setToast({ text, error }),
    [],
  );
  const patch = useCallback(
    (value: Partial<ProjectDraft>) =>
      dispatch({ type: "patch", id: project.id, patch: value }),
    [dispatch, project.id],
  );
  const [projectsOpen, setProjectsOpen] = useState(false);
  const [startingScripts, setStartingScripts] = useState<string[]>([]);
  const startingRef = useRef(new Set<string>());
  const [scriptJobs, setScriptJobs] = useState<Record<string, ScriptJob>>({});
  const [scriptErrors, setScriptErrors] = useState<Record<string, string>>({});
  const stateRef = useRef(state);
  stateRef.current = state;
  const scriptBusy = startingScripts.includes(project.id) || !!project.scriptJobId;
  const scriptStatus = scriptErrors[project.id] || (project.scriptJobId
    ? scriptStages[scriptJobs[project.scriptJobId]?.stage] || "Đang theo dõi tác vụ AI…"
    : startingScripts.includes(project.id) ? "Đang gửi yêu cầu…" : undefined);
  const pendingScripts = JSON.stringify(state.projects
    .filter((p) => p.scriptJobId)
    .map((p) => ({ projectId: p.id, jobId: p.scriptJobId! })));
  const graphics = useGraphicsJobs(notify);
  const exporting = useExportJobs();
  const previewBusy = graphics.busy;
  const [selectedId, setSelectedId] = useState("");
  const [deleteId, setDeleteId] = useState<string>();
  const [renameId, setRenameId] = useState<string>();
  const [renameText, setRenameText] = useState("");
  const [regenerateOpen, setRegenerateOpen] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);
  const scriptScrollRef = useRef<string | null>(null);

  useEffect(() => {
    if (scriptScrollRef.current !== project.id || !project.scenes.length) return;
    scriptScrollRef.current = null;
    document
      .getElementById("kich-ban")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [project.id, project.scenes]);

  useEffect(() => {
    if (!toast || toast.error) return;
    const timer = setTimeout(() => setToast(undefined), 6500);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    setSelectedId("");
  }, [project.id]);
  useEffect(() => {
    if (!project.snapshot) return;
    let cancelled = false;
    api<PreviewSnapshot>(`/api/previews/${project.snapshot.id}`).catch((e) => {
      if (!cancelled && e instanceof ApiError && e.status === 404) {
        patch({ snapshot: undefined });
        notify(
          "Preview không còn trên máy chủ. Hãy tạo lại animation trước khi xuất.",
          true,
        );
      }
    });
    return () => {
      cancelled = true;
    };
  }, [project.id, project.snapshot?.id, patch, notify]);

  useEffect(() => {
    const pending: { projectId: string; jobId: string }[] = JSON.parse(pendingScripts);
    if (!pending.length) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      await Promise.all(pending.map(async ({ projectId, jobId }) => {
        try {
          const job = await getScriptJob(jobId);
          if (cancelled) return;
          const current = stateRef.current.projects.find((p) => p.id === projectId);
          if (!current || current.scriptJobId !== jobId) return;
          setScriptJobs((jobs) => ({ ...jobs, [jobId]: job }));
          setScriptErrors((errors) => ({ ...errors, [projectId]: "" }));
          if (job.status === "succeeded" && job.result) {
            scriptScrollRef.current = projectId;
            dispatch({ type: "patch", id: projectId, patch: {
              scenes: job.result.scenes, scriptId: job.id, scriptJobId: undefined,
              messages: [],
              ...(current.title === "Dự án chưa đặt tên" ? { title: job.result.title } : {}),
            } });
            if (stateRef.current.activeId === projectId) {
              setSelectedId(job.result.scenes[0]?.id || "");
              notify("Kịch bản đã sẵn sàng. Bản JSON chi tiết đã được lưu trên máy chủ.");
            }
          } else if (job.status === "rejected" || job.status === "failed") {
            const message = job.error || "Không thể tạo kịch bản. Hãy thử lại.";
            dispatch({ type: "patch", id: projectId, patch: { scriptJobId: undefined } });
            setScriptErrors((errors) => ({ ...errors, [projectId]: message }));
            if (stateRef.current.activeId === projectId) notify(message, true);
          }
        } catch (error) {
          if (cancelled) return;
          const missing = error instanceof ApiError && error.status === 404;
          if (missing) dispatch({ type: "patch", id: projectId, patch: { scriptJobId: undefined } });
          setScriptErrors((errors) => ({ ...errors, [projectId]: missing
            ? errorText(error)
            : "Tạm mất kết nối máy chủ. Đang tự kết nối lại để theo dõi kịch bản…" }));
        }
      }));
      if (!cancelled) timer = setTimeout(() => void poll(), 1500);
    }
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [pendingScripts, dispatch, notify]);

  async function createScript() {
    if (!project.sourceContent.trim() || scriptBusy || previewBusy || startingRef.current.has(project.id)) return;
    setRegenerateOpen(false);
    const id = project.id;
    startingRef.current.add(id);
    setStartingScripts((ids) => [...ids, id]);
    setScriptErrors((errors) => ({ ...errors, [id]: "" }));
    try {
      const job = await createScriptJob(id, project.sourceContent, project.referenceImages);
      setScriptJobs((jobs) => ({ ...jobs, [job.id]: job }));
      dispatch({ type: "patch", id, patch: { scriptJobId: job.id } });
    } catch (error) {
      const message = errorText(error);
      setScriptErrors((errors) => ({ ...errors, [id]: message }));
      if (stateRef.current.activeId === id) notify(message, true);
    } finally {
      startingRef.current.delete(id);
      setStartingScripts((ids) => ids.filter((item) => item !== id));
    }
  }
  async function importDraft(file?: File) {
    if (!file) return;
    try {
      if (file.size > 5 * 1024 * 1024)
        throw new Error("File JSON tối đa 5 MB.");
      const data = JSON.parse(await file.text());
      if (data.version !== 1)
        throw new Error("Phiên bản bản nháp chưa được hỗ trợ.");
      const imported = parseDraft(data.project);
      dispatch({
        type: "add",
        project: {
          ...imported,
          id: crypto.randomUUID(),
          snapshot: undefined,
          jobId: undefined,
        },
      });
      setProjectsOpen(false);
      notify("Đã nhập bản nháp. Tạo animation để xem và xuất video.");
    } catch (e) {
      notify(errorText(e), true);
    } finally {
      if (importRef.current) importRef.current.value = "";
    }
  }
  return (
    <>
      <header className={s.header}>
        <a href="#" className={s.brand} aria-label="AI Video Studio trang đầu">
          <span className={s.brandMark}>
            <Aperture size={23} />
          </span>
          <span>
            video<span className={s.brandLight}>studio</span>
            <small>AI</small>
          </span>
        </a>
        <nav className={s.nav} aria-label="Các bước tạo video">
          {[
            ["noi-dung", "Nội dung & kịch bản"],
            ["phong-cach", "Phong cách"],
            ["xem-truoc", "Xem trước & xuất"],
          ].map(([id, label], i) => (
            <a href={`#${id}`} key={id}>
              <span>{i + 1}</span>
              {label}
            </a>
          ))}
        </nav>
        <button className={s.secondary} onClick={() => setProjectsOpen(true)}>
          <FolderOpen size={16} /> Dự án của tôi
        </button>
      </header>
      <main className={s.main}>
        <div className={s.breadcrumb}>
          KHÔNG GIAN SÁNG TẠO <span>/</span> DỰ ÁN MỚI
        </div>
        <div className={s.pageIntro}>
          <div>
            <div className={s.eyebrow}>
              <span /> TỪ Ý TƯỞNG ĐẾN CHUYỂN ĐỘNG
            </div>
            <h1>
              Câu chuyện của bạn.
              <br />
              <span>Thêm một chiều chuyển động.</span>
            </h1>
            <p>
              Viết điều bạn nghĩ. Chọn cách bạn kể. Phần còn lại, cùng làm nhé.
            </p>
          </div>
          <div className={s.introNote}>
            <span className={s.noteSpark}>
              <Sparkles size={22} />
            </span>
            <strong>
              Một không gian,
              <br />
              từ ý tưởng đến video.
            </strong>
            <span>
              3 bước đơn giản để bắt đầu <ArrowRight size={15} />
            </span>
          </div>
        </div>
        <div className={s.projectBar}>
          <div>
            <span className={s.projectDot} />
            <input
              aria-label="Tên dự án"
              maxLength={160}
              value={project.title}
              onChange={(e) => patch({ title: e.target.value })}
              onBlur={() => {
                if (!project.title.trim())
                  patch({ title: "Dự án chưa đặt tên" });
              }}
            />
            <Pencil size={13} />
          </div>
          <span className={s.saveStatus}>
            <Check size={13} />
            {saveStatus}
          </span>
        </div>
        <InputPanel
          key={project.id}
          project={project}
          patch={patch}
          notify={notify}
          busy={scriptBusy || previewBusy}
          status={scriptStatus}
          statusError={!!scriptErrors[project.id]}
          onGenerate={() =>
            project.scenes.length
              ? setRegenerateOpen(true)
              : void createScript()
          }
        >
          {project.scenes.length > 0 && (
            <ScenePanel
              project={project}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          )}
        </InputPanel>
        <StylePicker
          categoryId={project.categoryId}
          onCategoryChange={(categoryId) =>
            patch({
              categoryId,
              styleId: styleForCategory(categoryId, project.styleId),
            })
          }
          value={project.styleId}
          onChange={(styleId) => patch({ styleId })}
          busy={previewBusy}
          canGenerate={!!project.scriptId && !scriptBusy}
          hasScript={!!project.scriptId}
          status={graphics.status}
          statusError={graphics.error}
          onGenerate={() => void graphics.create()}
        />
        <PreviewPanel
          project={project}
          exporting={exporting}
          previewBusy={previewBusy}
          status={graphics.status}
        />
        <footer className={s.pageFooter}>
          <span>
            <Aperture size={17} /> videostudio <small>AI</small>
          </span>
          <p>Được tạo từ ý tưởng. Được chuyển động bởi HyperFrames.</p>
          <span>
            <CircleHelp size={14} /> Local workspace · Kịch bản AI
          </span>
        </footer>
      </main>
      {toast && (
        <div
          role={toast.error ? "alert" : "status"}
          className={`${s.toast} ${toast.error ? s.toastError : ""}`}
        >
          {toast.error ? <CircleHelp size={18} /> : <Check size={18} />}
          <span>{toast.text}</span>
          <button
            aria-label="Đóng thông báo"
            onClick={() => setToast(undefined)}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {regenerateOpen && (
        <Modal
          title="Tạo lại kịch bản?"
          onClose={() => setRegenerateOpen(false)}
        >
          <p className={s.confirmCopy}>
            Bảng hiện tại chỉ được thay khi AI tạo thành công kịch bản mới.
            File JSON chi tiết của mỗi lần tạo được lưu riêng trên máy chủ.
          </p>
          <div className={s.modalFooter}>
            <button
              className={s.secondary}
              onClick={() => setRegenerateOpen(false)}
            >
              Giữ bản hiện tại
            </button>
            <button className={s.primary} onClick={() => void createScript()}>
              Tạo lại
            </button>
          </div>
        </Modal>
      )}
      {projectsOpen && (
        <Modal
          title="Dự án của tôi"
          drawer
          onClose={() => {
            setProjectsOpen(false);
            setDeleteId(undefined);
            setRenameId(undefined);
          }}
        >
          <p className={s.drawerSub}>
            Những câu chuyện đang chờ bạn kể tiếp.
            <br />
            Bản nháp được lưu trên trình duyệt này.
          </p>
          <button
            className={`${s.primary} ${s.fullWidth}`}
            onClick={() => {
              dispatch({ type: "add", project: newProject() });
              setProjectsOpen(false);
            }}
          >
            <Plus size={17} /> Bắt đầu dự án mới
          </button>
          <div className={s.projectList}>
            {state.projects.map((p) => (
              <div
                key={p.id}
                className={`${s.projectItem} ${p.id === project.id ? s.currentProject : ""}`}
              >
                {renameId === p.id ? (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      if (renameText.trim()) {
                        dispatch({
                          type: "patch",
                          id: p.id,
                          patch: { title: renameText.trim() },
                        });
                        setRenameId(undefined);
                      }
                    }}
                    className={s.renameForm}
                  >
                    <input
                      autoFocus
                      required
                      maxLength={160}
                      aria-label="Tên dự án mới"
                      value={renameText}
                      onChange={(e) => setRenameText(e.target.value)}
                    />
                    <button className={s.iconButton} aria-label="Lưu tên">
                      <Check size={16} />
                    </button>
                    <button
                      type="button"
                      className={s.iconButton}
                      aria-label="Hủy đổi tên"
                      onClick={() => setRenameId(undefined)}
                    >
                      <X size={16} />
                    </button>
                  </form>
                ) : (
                  <button
                    className={s.projectOpen}
                    onClick={() => {
                      dispatch({ type: "open", id: p.id });
                      setProjectsOpen(false);
                    }}
                  >
                    <strong>{p.title}</strong>
                    <small>
                      {p.scenes.length} cảnh ·{" "}
                      {new Date(p.updatedAt).toLocaleDateString("vi-VN")}
                      {p.id === project.id ? " · Đang mở" : ""}
                    </small>
                  </button>
                )}
                <div className={s.buttonRow}>
                  {deleteId === p.id ? (
                    <>
                      <span className={s.deleteHint}>Xóa bản nháp?</span>
                      <button
                        className={s.deleteButton}
                        aria-label="Xác nhận xóa dự án"
                        onClick={() => {
                          dispatch({ type: "delete", id: p.id });
                          setDeleteId(undefined);
                        }}
                      >
                        <Check size={16} />
                      </button>
                      <button
                        className={s.iconButton}
                        aria-label="Hủy xóa"
                        onClick={() => setDeleteId(undefined)}
                      >
                        <X size={16} />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        className={s.iconButton}
                        aria-label={`Đổi tên ${p.title}`}
                        onClick={() => {
                          setRenameId(p.id);
                          setRenameText(p.title);
                        }}
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        className={s.iconButton}
                        aria-label={`Xóa ${p.title}`}
                        onClick={() => setDeleteId(p.id)}
                      >
                        <Trash2 size={15} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className={s.draftActions}>
            <button
              className={s.secondary}
              onClick={() => importRef.current?.click()}
            >
              <Upload size={16} /> Nhập bản nháp JSON
            </button>
            <input
              hidden
              ref={importRef}
              type="file"
              accept=".json,application/json"
              onChange={(e) => void importDraft(e.target.files?.[0])}
            />
          </div>
        </Modal>
      )}
    </>
  );
}
