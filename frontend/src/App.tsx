import { useCallback, useEffect, useRef, useState } from "react";
import {
  Aperture,
  FolderOpen,
  Check,
  Plus,
  Download,
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
} from "./types";
import { api, ApiError, generatePreview, videoService } from "./services";
import { Modal, errorText } from "./components";
import InputPanel from "./InputPanel";
import { StylePicker } from "./components";
import ScenePanel from "./ScenePanel";
import PreviewPanel from "./PreviewPanel";
import s from "./Studio.module.css";

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
  const [scriptBusy, setScriptBusy] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [selectedId, setSelectedId] = useState("");
  const [editRequest, setEditRequest] = useState<{
    id: string;
    chat?: boolean;
    key: number;
  }>();
  const [deleteId, setDeleteId] = useState<string>();
  const [renameId, setRenameId] = useState<string>();
  const [renameText, setRenameText] = useState("");
  const [regenerateOpen, setRegenerateOpen] = useState(false);
  const importRef = useRef<HTMLInputElement>(null);

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

  async function createScript() {
    if (!project.sourceContent.trim() || scriptBusy) return;
    setRegenerateOpen(false);
    setScriptBusy(true);
    const id = project.id;
    try {
      const scenes = await videoService.generateScript(project.sourceContent);
      dispatch({
        type: "patch",
        id,
        patch: {
          scenes,
          messages: [],
          ...(project.title === "Dự án chưa đặt tên"
            ? { title: "Bão nhiệt đới hình thành như thế nào?" }
            : {}),
        },
      });
      setSelectedId(scenes[0].id);
      notify("Kịch bản mẫu đã sẵn sàng. Bạn có thể sửa từng cảnh.");
      document
        .getElementById("kich-ban")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      notify(errorText(e), true);
    } finally {
      setScriptBusy(false);
    }
  }
  async function buildPreview() {
    if (!project.scenes.length || previewBusy) return;
    setPreviewBusy(true);
    const current = project;
    try {
      const snapshot = await generatePreview(current);
      dispatch({ type: "patch", id: current.id, patch: { snapshot } });
      notify("Preview đã sẵn sàng. Hãy duyệt từng phase trước khi xuất video.");
      document
        .getElementById("xem-truoc")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (e) {
      notify(errorText(e), true);
    } finally {
      setPreviewBusy(false);
    }
  }
  function exportDraft() {
    const blob = new Blob([JSON.stringify({ version: 1, project }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${project.title.replace(/[/\\]/g, "-")}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
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
  function editPhase(id: string, chat?: boolean) {
    setSelectedId(id);
    document
      .getElementById("kich-ban")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
    setEditRequest({ id, chat, key: Date.now() });
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
            ["noi-dung", "Nội dung"],
            ["phong-cach", "Phong cách"],
            ["kich-ban", "Kịch bản"],
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
              4 bước đơn giản để bắt đầu <ArrowRight size={15} />
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
        />
        <StylePicker
          value={project.styleId}
          onChange={(styleId) => patch({ styleId })}
          busy={scriptBusy}
          canGenerate={!!project.sourceContent.trim()}
          onGenerate={() =>
            project.scenes.length
              ? setRegenerateOpen(true)
              : void createScript()
          }
        />
        <ScenePanel
          project={project}
          patch={patch}
          selectedId={selectedId}
          onSelect={setSelectedId}
          editRequest={editRequest}
          notify={notify}
          onPreview={() => void buildPreview()}
          previewBusy={previewBusy}
        />
        <PreviewPanel
          project={project}
          patch={patch}
          notify={notify}
          onEdit={editPhase}
          onRegenerate={() => void buildPreview()}
          previewBusy={previewBusy}
        />
        <footer className={s.pageFooter}>
          <span>
            <Aperture size={17} /> videostudio <small>AI</small>
          </span>
          <p>Được tạo từ ý tưởng. Được chuyển động bởi HyperFrames.</p>
          <span>
            <CircleHelp size={14} /> Local workspace · AI demo
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
          title="Tạo lại kịch bản mẫu?"
          onClose={() => setRegenerateOpen(false)}
        >
          <p className={s.confirmCopy}>
            Các cảnh và cuộc trò chuyện hiện tại sẽ được thay bằng bộ kịch bản
            mẫu. Bạn có thể tải JSON trước để giữ bản chỉnh sửa.
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
            <button className={s.secondary} onClick={exportDraft}>
              <Download size={16} /> Tải JSON dự án đang mở
            </button>
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
