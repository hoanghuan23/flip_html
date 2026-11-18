import { useEffect, useRef, useState } from "react";
import {
  Plus,
  Pencil,
  Trash2,
  Check,
  MessageSquare,
  Send,
  Sparkles,
  Film,
  Clock3,
  X,
} from "lucide-react";
import { SectionHeading, errorText } from "./components";
import { sceneValid, type ProjectDraft, type Scene } from "./types";
import { videoService } from "./services";
import s from "./Studio.module.css";

export default function ScenePanel({
  project,
  patch,
  selectedId,
  onSelect,
  editRequest,
  notify,
  onPreview,
  previewBusy,
}: {
  project: ProjectDraft;
  patch: (p: Partial<ProjectDraft>) => void;
  selectedId: string;
  onSelect: (id: string) => void;
  notify: (t: string, error?: boolean) => void;
  onPreview: () => void;
  previewBusy: boolean;
  editRequest?: { id: string; chat?: boolean; key: number };
}) {
  const [editing, setEditing] = useState<Scene | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState(false);
  const [deleteId, setDeleteId] = useState<string>();
  const chatRef = useRef<HTMLElement>(null);
  const selected =
    project.scenes.find((scene) => scene.id === selectedId) ||
    project.scenes[0];
  useEffect(() => {
    setEditing(null);
    setDeleteId(undefined);
    setInstruction("");
    setChatOpen(false);
  }, [project.id]);
  useEffect(() => {
    if (!chatOpen || !chatRef.current) return;
    const panel = chatRef.current;
    const previous = document.activeElement as HTMLElement | null;
    const compact = window.matchMedia("(max-width: 850px)").matches;
    if (compact) {
      panel.setAttribute("role", "dialog");
      panel.setAttribute("aria-modal", "true");
      panel.querySelector<HTMLInputElement>("input")?.focus();
    }
    const keydown = (event: KeyboardEvent) => {
      if (
        event.key === "Escape" &&
        (compact || panel.contains(document.activeElement))
      ) {
        event.preventDefault();
        setChatOpen(false);
      }
      if (!compact || event.key !== "Tab") return;
      const controls = [
        ...panel.querySelectorAll<HTMLElement>(
          "button:not(:disabled),input:not(:disabled)",
        ),
      ];
      const first = controls[0],
        last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      panel.removeAttribute("role");
      panel.removeAttribute("aria-modal");
      if (compact && previous?.isConnected) previous.focus();
    };
  }, [chatOpen]);
  useEffect(() => {
    if (!editRequest) return;
    const scene = project.scenes.find((p) => p.id === editRequest.id);
    if (scene) {
      if (editRequest.chat) setChatOpen(true);
      else setEditing({ ...scene });
    }
  }, [editRequest]);
  function save() {
    if (!editing || !sceneValid(editing)) {
      notify(
        "Tên cảnh không được trống; thời lượng phải lớn hơn 0 và không quá 120 giây.",
        true,
      );
      return;
    }
    const scenes = project.scenes.map((p) =>
      p.id === editing.id ? editing : p,
    );
    if (scenes.reduce((t, p) => t + p.duration, 0) > 1800) {
      notify("Tổng thời lượng tối đa là 30 phút.", true);
      return;
    }
    patch({ scenes });
    setEditing(null);
  }
  async function send(text: string) {
    if (!selected || !text.trim() || busy) return;
    if (editing) {
      notify("Hãy lưu hoặc hủy cảnh đang sửa trước khi nhờ trợ lý.", true);
      return;
    }
    setBusy(true);
    setInstruction("");
    const messages = [
      ...project.messages,
      { id: crypto.randomUUID(), role: "user" as const, text: text.trim() },
    ];
    patch({ messages });
    try {
      const result = await videoService.reviseScript(selected, text);
      patch({
        messages: [
          ...messages,
          { id: crypto.randomUUID(), role: "assistant", text: result.reply },
        ],
        ...(result.scene
          ? {
              scenes: project.scenes.map((p) =>
                p.id === selected.id ? result.scene! : p,
              ),
            }
          : {}),
      });
    } catch (e) {
      notify(errorText(e), true);
    } finally {
      setBusy(false);
    }
  }
  const total = project.scenes.reduce((n, p) => n + p.duration, 0);
  return (
    <section className={s.card} id="kich-ban">
      <SectionHeading
        number={3}
        title="Câu chuyện bắt đầu thành hình"
        subtitle="Đọc lại, tinh chỉnh từng cảnh, rồi sẵn sàng cho những chuyển động."
        action={
          <button
            className={s.secondary}
            onClick={() => setChatOpen(!chatOpen)}
            aria-expanded={chatOpen}
          >
            <MessageSquare size={16} /> Chat với AI
          </button>
        }
      />
      <div className={s.demoNote}>
        <Sparkles size={15} />
        <span>
          <strong>Trợ lý đang ở chế độ demo.</strong> Kịch bản mẫu về bão nhiệt
          đới; nội dung nhập chưa được AI phân tích thật.
        </span>
      </div>
      {!project.scenes.length ? (
        <div className={s.empty}>
          <div className={s.emptyIcon}>
            <Film size={28} strokeWidth={1.3} />
          </div>
          <h3>Mỗi câu chuyện hay đều có một khởi đầu</h3>
          <p>
            Nhập nội dung và chọn “AI tạo kịch bản” ở bước 2.
            <br />
            Các cảnh của bạn sẽ xuất hiện ở đây.
          </p>
        </div>
      ) : (
        <>
          <div className={`${s.scriptLayout} ${chatOpen ? s.chatVisible : ""}`}>
            <div className={s.sceneList}>
              <div className={s.tableHeading}>
                <span>CẢNH</span>
                <span>CHỮ GIẢI THÍCH & HÌNH ẢNH</span>
                <span>GIÂY</span>
                <span />
              </div>
              {project.scenes.map((scene, i) => (
                <div
                  key={scene.id}
                  className={`${s.sceneRow} ${selected?.id === scene.id ? s.activeRow : ""}`}
                >
                  <button
                    className={s.sceneNumber}
                    aria-label={`Chọn cảnh ${i + 1}: ${scene.name}`}
                    aria-pressed={selected?.id === scene.id}
                    onClick={() => onSelect(scene.id)}
                  >
                    {String(i + 1).padStart(2, "0")}
                  </button>
                  {editing?.id === scene.id ? (
                    <div className={s.sceneFields}>
                      <label>
                        Tên cảnh
                        <input
                          value={editing.name}
                          maxLength={160}
                          onChange={(e) =>
                            setEditing({ ...editing, name: e.target.value })
                          }
                        />
                      </label>
                      <label>
                        Chữ giải thích
                        <textarea
                          maxLength={2000}
                          value={editing.narration}
                          onChange={(e) =>
                            setEditing({
                              ...editing,
                              narration: e.target.value,
                            })
                          }
                        />
                      </label>
                      <label>
                        Mô tả hình ảnh
                        <textarea
                          maxLength={3000}
                          value={editing.description}
                          onChange={(e) =>
                            setEditing({
                              ...editing,
                              description: e.target.value,
                            })
                          }
                        />
                      </label>
                      <label>
                        Thời lượng (giây)
                        <input
                          type="number"
                          min="0.1"
                          max="120"
                          step="0.1"
                          value={
                            Number.isNaN(editing.duration)
                              ? ""
                              : editing.duration
                          }
                          onChange={(e) =>
                            setEditing({
                              ...editing,
                              duration: e.target.valueAsNumber,
                            })
                          }
                        />
                      </label>
                      <div className={s.buttonRow}>
                        <button className={s.primarySmall} onClick={save}>
                          <Check size={14} /> Lưu cảnh
                        </button>
                        <button
                          className={s.secondarySmall}
                          onClick={() => setEditing(null)}
                        >
                          Hủy
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className={s.sceneCopy}>
                      <strong>{scene.name}</strong>
                      <p>{scene.narration}</p>
                      <small>{scene.description}</small>
                    </div>
                  )}
                  <span className={s.duration}>{scene.duration}s</span>
                  <div className={s.rowActions}>
                    {deleteId === scene.id ? (
                      <>
                        <button
                          className={s.deleteButton}
                          aria-label="Xác nhận xóa cảnh"
                          onClick={() => {
                            patch({
                              scenes: project.scenes.filter(
                                (p) => p.id !== scene.id,
                              ),
                            });
                            setDeleteId(undefined);
                            if (editing?.id === scene.id) setEditing(null);
                          }}
                        >
                          <Check size={16} />
                        </button>
                        <button
                          className={s.iconButton}
                          aria-label="Hủy xóa cảnh"
                          onClick={() => setDeleteId(undefined)}
                        >
                          <X size={15} />
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          className={s.iconButton}
                          disabled={busy}
                          aria-label={`Sửa cảnh ${i + 1}`}
                          onClick={() => {
                            onSelect(scene.id);
                            setEditing({ ...scene });
                          }}
                        >
                          <Pencil size={15} />
                        </button>
                        <button
                          className={s.iconButton}
                          disabled={busy}
                          aria-label={`Xóa cảnh ${i + 1}`}
                          onClick={() => setDeleteId(scene.id)}
                        >
                          <Trash2 size={15} />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
              <div className={s.tableFooter}>
                <button
                  className={s.textButton}
                  disabled={project.scenes.length >= 100 || busy || !!editing}
                  onClick={() => {
                    const scene = {
                      id: crypto.randomUUID(),
                      name: "Cảnh mới",
                      narration: "",
                      description: "",
                      duration: 5,
                    };
                    if (total + 5 > 1800) {
                      notify("Tổng thời lượng tối đa là 30 phút.", true);
                      return;
                    }
                    patch({ scenes: [...project.scenes, scene] });
                    onSelect(scene.id);
                    setEditing(scene);
                  }}
                >
                  <Plus size={16} /> Thêm cảnh
                </button>
                <span>
                  <Clock3 size={14} /> {total.toLocaleString("vi")} giây ·{" "}
                  {project.scenes.length} cảnh
                </span>
              </div>
            </div>
            {chatOpen && (
              <>
                <button
                  className={s.chatBackdrop}
                  aria-label="Đóng chat"
                  onClick={() => setChatOpen(false)}
                />
                <aside
                  ref={chatRef}
                  className={s.chatPanel}
                  aria-label="Trợ lý chỉnh kịch bản"
                >
                  <div className={s.chatHead}>
                    <span className={s.aiIcon}>
                      <Sparkles size={17} />
                    </span>
                    <div>
                      <strong>Đồng tác giả AI</strong>
                      <small>
                        Chỉnh sửa mẫu · {selected?.name || "Chọn một cảnh"}
                      </small>
                    </div>
                    <button
                      className={s.iconButton}
                      aria-label="Đóng chat"
                      onClick={() => setChatOpen(false)}
                    >
                      <X size={16} />
                    </button>
                  </div>
                  <div className={s.messages} aria-live="polite">
                    {!project.messages.length && (
                      <div className={s.assistantMessage}>
                        Chọn một cảnh trong bảng, rồi cho mình biết bạn muốn
                        thay đổi điều gì nhé.
                      </div>
                    )}
                    {project.messages.map((message) => (
                      <div
                        key={message.id}
                        className={
                          message.role === "user"
                            ? s.userMessage
                            : s.assistantMessage
                        }
                      >
                        {message.text}
                      </div>
                    ))}
                    {busy && (
                      <div className={s.assistantMessage}>
                        Đang chỉnh nội dung mẫu…
                      </div>
                    )}
                  </div>
                  <div className={s.chatSuggestions}>
                    {[
                      "Rút ngắn cảnh",
                      "Đổi giọng vui hơn",
                      "Viết lại chữ giải thích",
                    ].map((text) => (
                      <button
                        key={text}
                        disabled={busy}
                        onClick={() => void send(text)}
                      >
                        {text}
                      </button>
                    ))}
                  </div>
                  <form
                    className={s.chatForm}
                    onSubmit={(e) => {
                      e.preventDefault();
                      void send(instruction);
                    }}
                  >
                    <input
                      aria-label="Yêu cầu chỉnh sửa"
                      placeholder="Cùng chỉnh lại một chút…"
                      value={instruction}
                      maxLength={1000}
                      onChange={(e) => setInstruction(e.target.value)}
                      disabled={busy}
                    />
                    <button
                      className={s.primarySmall}
                      aria-label="Gửi yêu cầu"
                      disabled={busy || !instruction.trim()}
                    >
                      <Send size={16} />
                    </button>
                  </form>
                </aside>
              </>
            )}
          </div>
          <div className={s.sectionFooter}>
            <span className={s.muted}>
              Chữ giải thích hiển thị trên màn hình · chưa có giọng đọc
            </span>
            <button
              className={s.primary}
              disabled={previewBusy || !!editing || busy}
              onClick={onPreview}
            >
              <Film size={17} />
              {previewBusy ? "Đang tạo preview…" : "Đồng ý & tạo animation"}
              <span aria-hidden="true">↗</span>
            </button>
          </div>
        </>
      )}
    </section>
  );
}
