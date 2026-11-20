import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type CSSProperties,
} from "react";
import { X, Check, Sparkles } from "lucide-react";
import { type StyleId, type CategoryId } from "./types";
import { getStyle } from "./styleCatalog";
import { categories } from "./styleConfig";
import { api } from "./services";
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
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  drawer?: boolean;
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
      className={drawer ? s.drawer : s.modal}
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
export function Art({
  styleId,
  large = false,
}: {
  styleId: StyleId;
  large?: boolean;
}) {
  const style = getStyle(styleId);
  return (
    <div
      className={`${s.art} ${large ? s.artLarge : ""} ${s[styleId] || ""}`}
      style={
        {
          "--art-bg": style.colors[0],
          "--art-sea": style.colors[1],
          "--art-sun": style.colors[2],
        } as CSSProperties
      }
      aria-hidden="true"
    >
      <span className={s.artGrid} />
      <span className={s.artSun} />
      <span className={s.artCloud} />
      <span className={s.artHillBack} />
      <span className={s.artHill} />
      <span className={s.artWave} />
      {large && (
        <div className={s.artLabel}>
          <span>Ý TƯỞNG ĐANG CHUYỂN ĐỘNG</span>
          <strong>
            Mỗi ý tưởng,
            <br />
            một thế giới mới.
          </strong>
          <span>MINH HỌA PHONG CÁCH</span>
        </div>
      )}
    </div>
  );
}
function StyleSample({ styleId, name }: { styleId: StyleId; name: string }) {
  const [demo, setDemo] = useState<{ styleId: StyleId; url: string }>();
  useEffect(() => {
    let cancelled = false;
    setDemo(undefined);
    api<{ url: string | null }>(`/api/styles/${styleId}/preview`)
      .then(({ url }) => {
        if (!cancelled && url) setDemo({ styleId, url });
      })
      .catch(() => {
        /* Missing samples leave the frame empty. */
      });
    return () => {
      cancelled = true;
    };
  }, [styleId]);
  return (
    <div className={s.styleSample} aria-label={`Hình mẫu ${name}`}>
      {demo?.styleId === styleId && (
        <iframe
          key={styleId}
          src={demo.url}
          title={`Bản demo ${name}`}
          sandbox="allow-scripts"
          onError={() => setDemo(undefined)}
        />
      )}
    </div>
  );
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
}) {
  const selected = getStyle(value);
  const category = categories.find((p) => p.id === categoryId)!;
  const availableStyles = [...new Set(category.allowedStyles)].map(getStyle);
  return (
    <section className={s.card} id="phong-cach">
      <SectionHeading
        number={2}
        title="Nhóm chủ đề & phong cách đồ họa"
        subtitle="Chọn phong cách để AI tạo hình ảnh và animation cho kịch bản của bạn."
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
              ? category.label
              : `Phong cách cho “${category.label}”`} ({availableStyles.length} lựa chọn)
          </p>
          {!availableStyles.length && (
            <p className={s.scriptStatus}>
              Nhóm chủ đề này chưa có phong cách. Chọn “Tất cả phong cách” để tiếp tục.
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
        <div className={s.stylePreview}>
          {!!availableStyles.length && <StyleSample styleId={value} name={selected.name} />}
        </div>
      </div>
      {!hasScript && <p className={s.scriptStatus}>Hoàn tất tạo kịch bản ở mục 1 để tạo đồ họa.</p>}
      {status && <p className={s.scriptStatus} role={statusError ? "alert" : "status"}>{status}</p>}
      <div className={`${s.sectionFooter} ${s.styleFooter}`}>
        <button
          className={s.primary}
          disabled={!canGenerate || busy || !category.allowedStyles.includes(value)}
          onClick={onGenerate}
        >
          <Sparkles size={17} className={busy ? s.spin : ""} />
          {busy ? "Đang tạo đồ họa…" : "Tạo đồ họa"}
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
