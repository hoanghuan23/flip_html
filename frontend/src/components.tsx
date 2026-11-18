import { useEffect, useRef, type ReactNode, type CSSProperties } from "react";
import { X, Check, Sparkles } from "lucide-react";
import { styles, type StyleId } from "./types";
import s from "./Studio.module.css";

export function SectionHeading({
  number,
  title,
  subtitle,
  action,
}: {
  number: number;
  title: string;
  subtitle: string;
  action?: ReactNode;
}) {
  return (
    <div className={s.sectionHeading}>
      <div className={s.headingLeft}>
        <span className={s.stepNumber}>
          {number.toString().padStart(2, "0")}
        </span>
        <div>
          <h2>{title}</h2>
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
  const style = styles.find((p) => p.id === styleId)!;
  return (
    <div
      className={`${s.art} ${large ? s.artLarge : ""} ${s[styleId]}`}
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
export function StylePicker({
  value,
  onChange,
  onGenerate,
  busy,
  canGenerate,
}: {
  value: StyleId;
  onChange: (id: StyleId) => void;
  onGenerate: () => void;
  busy: boolean;
  canGenerate: boolean;
}) {
  const selected = styles.find((p) => p.id === value)!;
  return (
    <section className={s.card} id="phong-cach">
      <SectionHeading
        number={2}
        title="Chọn một chất riêng"
        subtitle="Một ý tưởng, nhiều cách kể. Bạn thích phong cách nào?"
      />
      <div className={s.styleLayout}>
        <div className={s.styleGrid}>
          {styles.map((style) => (
            <button
              key={style.id}
              className={`${s.styleCard} ${style.id === value ? s.selected : ""}`}
              aria-pressed={style.id === value}
              onClick={() => onChange(style.id)}
            >
              <Art styleId={style.id} />
              <span>
                {style.name}
                {style.id === value && <Check size={16} />}
              </span>
            </button>
          ))}
        </div>
        <div className={s.stylePreview}>
          <div className={s.previewLabel}>
            <span>HÌNH MẪU · {selected.name.toLocaleUpperCase("vi")}</span>
            <span className={s.selectedBadge}>
              <Check size={12} /> Đã chọn
            </span>
          </div>
          <Art styleId={value} large />
          <p>{selected.description}</p>
        </div>
      </div>
      <div className={s.sectionFooter}>
        <span className={s.muted}>
          Bạn có thể đổi phong cách trước khi tạo animation.
        </span>
        <button
          className={s.primary}
          disabled={!canGenerate || busy}
          onClick={onGenerate}
        >
          <Sparkles size={17} className={busy ? s.spin : ""} />
          {busy ? "Đang chuẩn bị kịch bản…" : "AI tạo kịch bản"}
          <span aria-hidden="true">↗</span>
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
