import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { X, Check, Sparkles, Image as ImageIcon, Expand } from "lucide-react";
import { type StyleId, type CategoryId, type GraphicsJob, type Scene } from "./types";
import { StageUsage } from "./TokenUsage";
import type { TokenUsage } from "./types";
import { getStyle } from "./styleCatalog";
import { categories } from "./styleConfig";
import s from "./Studio.module.css";

export function SectionHeading({
  number,
  title,
  subtitle,
  action,
}: {
  number?: number;
  title: string;
  subtitle: string;
  action?: ReactNode;
}) {
  const Heading = number === undefined ? "h3" : "h2";
  return (
    <div className={s.sectionHeading}>
      <div className={s.headingLeft}>
        {number !== undefined && (
          <span className={s.stepNumber}>
            {number.toString().padStart(2, "0")}
          </span>
        )}
        <div>
          <Heading>{title}</Heading>
          <p>{subtitle}</p>
        </div>
      </div>
      {action}
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
  drawer = false,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  drawer?: boolean;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    dialog
      .querySelector<HTMLInputElement>("input:not([type=file]),textarea,select")
      ?.focus();
    return () => dialog.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className={drawer ? s.drawer : `${s.modal} ${wide ? s.wideModal : ""}`}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          const r = e.currentTarget.getBoundingClientRect();
          if (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          )
            onClose();
        }
      }}
      aria-label={title}
    >
      <div className={s.modalHead}>
        <h2>{title}</h2>
        <button className={s.iconButton} aria-label="Đóng" onClick={onClose}>
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

function PhaseStillPreviews({ scenes, job, busy }: { scenes: Scene[]; job?: GraphicsJob; busy: boolean }) {
  const [openedId, setOpenedId] = useState<string>();
  const previews = job?.previews ?? [];
  const opened = previews.find((phase) => phase.id === openedId);
  const generating = busy && !job?.confirmed;
  useEffect(() => setOpenedId(undefined), [job?.id]);
  return <div className={s.phaseStills}>
    <div className={s.phaseStillsHeading}>
      <div>
        <h3>Preview các phase</h3>
        <p>Ảnh tĩnh do AI tạo. Bấm vào ảnh để xem lớn, sau đó xác nhận để dựng animation.</p>
      </div>
      <span role="status">{previews.length}/{scenes.length} ảnh sẵn sàng</span>
    </div>
    <div className={s.phaseStillsGrid} aria-label="Preview tĩnh các phase">
      {scenes.map((scene, index) => {
        const preview = previews.find((phase) => phase.id === scene.id);
        const creating = generating && index === previews.length;
        return <button key={scene.id} type="button" className={s.phaseStillCard}
          disabled={!preview} onClick={() => setOpenedId(scene.id)}
          aria-label={preview ? `Phóng to preview Phase ${index + 1}: ${scene.name}` : `Phase ${index + 1}: ${creating ? "Đang tạo" : "Chưa có preview"}`}>
          <span className={s.phaseStillImage}>
            {preview ? <><img src={preview.url} alt={`Preview tĩnh ${scene.name}`} loading="lazy" /><Expand size={16} className={s.phaseStillExpand} /></> :
              <span className={s.phaseStillPlaceholder}>
                {creating ? <Sparkles size={22} className={s.spin} /> : <ImageIcon size={22} />}
                <small>{creating ? "Đang tạo…" : generating ? "Đang chờ" : "Chưa tạo"}</small>
              </span>}
          </span>
          <span className={s.phaseStillCaption}><strong>Phase {index + 1}</strong><span>{scene.name}</span></span>
        </button>;
      })}
    </div>
    {opened && <Modal wide title={`Phase ${scenes.findIndex((scene) => scene.id === opened.id) + 1} · ${opened.name}`} onClose={() => setOpenedId(undefined)}>
      <img className={s.phaseStillFull} src={opened.url} alt={`Preview tĩnh ${opened.name}`} />
    </Modal>}
  </div>;
}
export function StylePicker({
  categoryId,
  onCategoryChange,
  value,
  onChange,
  onGenerate,
  busy,
  canGenerate,
  hasScript,
  status,
  statusError,
  scenes,
  graphicsJob,
  readyToConfirm,
  usage,
}: {
  categoryId: CategoryId;
  onCategoryChange: (id: CategoryId) => void;
  value: StyleId;
  onChange: (id: StyleId) => void;
  onGenerate: () => void;
  busy: boolean;
  canGenerate: boolean;
  hasScript: boolean;
  status?: string;
  statusError?: boolean;
  scenes: Scene[];
  graphicsJob?: GraphicsJob;
  readyToConfirm: boolean;
  usage?: TokenUsage;
}) {
  const category = categories.find((p) => p.id === categoryId);
  const availableStyles = [...new Set(category?.allowedStyles ?? [])].map(getStyle);
  return (
    <section className={s.card} id="phong-cach">
      <SectionHeading
        number={2}
        title="Nhóm chủ đề & phong cách đồ họa"
        subtitle="Chọn phong cách, duyệt ảnh tĩnh từng phase rồi xác nhận để tạo animation."
      />
      <div className={s.categorySection}>
        <p className={s.fieldLabel} id="category-heading">
          Nhóm chủ đề
        </p>
        <div
          className={s.categoryList}
          role="group"
          aria-labelledby="category-heading"
        >
          {categories.map((item) => (
            <button
              key={item.id}
              className={`${s.categoryButton} ${item.id === categoryId ? s.activeCategory : ""}`}
              disabled={busy}
              aria-pressed={item.id === categoryId}
              onClick={() => onCategoryChange(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
      <div className={s.styleLayout}>
        <div className={s.styleList}>
          <p className={s.styleHeading}>
            {categoryId === "all_styles"
              ? (category?.label ?? "Chưa có cấu hình")
              : `Phong cách cho “${(category?.label ?? "Chưa có cấu hình")}”`} ({availableStyles.length} lựa chọn)
          </p>
          {!availableStyles.length && (
            <p className={s.scriptStatus}>
              Chưa có cấu hình phong cách.
            </p>
          )}
          <div className={s.styleGrid}>
            {availableStyles.map((style) => (
              <button
                key={style.id}
                className={`${s.styleCard} ${style.id === value ? s.selected : ""}`}
                disabled={busy}
                aria-pressed={style.id === value}
                onClick={() => onChange(style.id)}
              >
                <span>
                  {style.name}
                  {style.id === value && <Check size={16} />}
                </span>
                <p className={s.styleDescription}>{style.description}</p>
              </button>
            ))}
          </div>
        </div>
        <div className={s.stylePreview} />
      </div>
      {hasScript && scenes.length > 0 && <PhaseStillPreviews scenes={scenes} job={graphicsJob} busy={busy} />}
      {!hasScript && <p className={s.scriptStatus}>Hoàn tất tạo kịch bản ở mục 1 để tạo đồ họa.</p>}
      {status && <p className={s.scriptStatus} role={statusError ? "alert" : "status"}>{status}</p>}
      <StageUsage label="Preview phong cách đồ họa" usage={usage} />
      <div className={`${s.sectionFooter} ${s.styleFooter}`}>
        <button
          className={s.primary}
          disabled={!canGenerate || busy || !(category?.allowedStyles ?? []).includes(value)}
          onClick={onGenerate}
        >
          <Sparkles size={17} className={busy ? s.spin : ""} />
          {busy ? (graphicsJob?.confirmed ? "Đang tạo hoàn chỉnh…" : "Đang tạo đồ họa…") :
            readyToConfirm ? "Xác nhận và tạo hoàn chỉnh" : "Tạo đồ họa"}
        </button>
      </div>
    </section>
  );
}
export function timeLabel(seconds: number) {
  return `${Math.floor(seconds / 60)}:${Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0")}`;
}
export function errorText(error: unknown) {
  return error instanceof Error ? error.message : "Đã có lỗi. Hãy thử lại.";
}
