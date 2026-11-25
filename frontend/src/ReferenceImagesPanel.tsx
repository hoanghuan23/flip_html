import { useEffect, useRef, useState, type DragEvent } from "react";
import { ImagePlus, Plus, X } from "lucide-react";
import { numberReferenceImages, readReferenceImage, type ReferenceImage } from "./referenceImages";
import { uploadImage } from "./services";
import s from "./Studio.module.css";

const imageTabs = [
  { id: "reference", label: "Ảnh tham chiếu" },
  { id: "illustration", label: "Ảnh minh họa" },
] as const;

export default function ReferenceImages({ projectId, images, lastNumber, onChange, notify, disabled }: {
  projectId: string;
  images: ReferenceImage[];
  lastNumber: number;
  onChange: (images: ReferenceImage[], lastNumber: number) => void;
  notify: (text: string, error?: boolean) => void;
  disabled: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const processing = useRef(false);
  const active = useRef(true);
  const [reading, setReading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [tab, setTab] = useState<"reference" | "illustration">("reference");
  const dragDepth = useRef(0);
  const locked = disabled || reading;
  const numberedImages = numberReferenceImages(images);
  const visibleImages = numberedImages.filter((image) => (image.kind ?? "reference") === tab);
  const imageLabel = tab === "reference" ? "tham chiếu" : "minh họa";
  const latestNumber = Math.max(lastNumber, ...numberedImages.map((image) => image.number));
  useEffect(() => {
    active.current = true;
    return () => { active.current = false; };
  }, []);

  async function add(files: File[]) {
    if (disabled || processing.current || !files.length) return;
    processing.current = true;
    setReading(true);
    const added: ReferenceImage[] = [];
    const errors: string[] = [];
    try {
      for (const file of files) {
        try {
          const preview = { ...await readReferenceImage(file), kind: tab,
            number: latestNumber + added.length + 1 };
          const original = await new Promise<string>((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result));
            reader.onerror = () => reject(new Error(`Không thể đọc ${file.name}.`));
            reader.readAsDataURL(file);
          });
          const stored = await uploadImage(projectId, preview, original);
          added.push({ ...preview, serverId: stored.id });
        } catch (error) {
          errors.push(error instanceof Error ? error.message : "Không thể đọc ảnh.");
        }
        if (!active.current) return;
      }
      if (added.length) onChange([
        ...numberedImages,
        ...numberReferenceImages(added),
      ], latestNumber + added.length);
      if (errors.length) notify(errors.join(" "), true);
    } finally {
      processing.current = false;
      if (active.current) setReading(false);
    }
  }
  function drag(event: DragEvent) {
    event.preventDefault();
    if (!locked && event.dataTransfer.types.includes("Files")) {
      event.dataTransfer.dropEffect = "copy";
    }
  }

  return (
    <div className={s.referenceInput}>
      <div
        className={s.imageTabs}
        role="tablist"
        aria-label="Loại ảnh đầu vào"
        onKeyDown={(event) => {
          if (reading || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
          event.preventDefault();
          let next: typeof tab = tab === "reference" ? "illustration" : "reference";
          if (event.key === "Home") next = "reference";
          if (event.key === "End") next = "illustration";
          setTab(next);
          document.getElementById(`image-tab-${next}`)?.focus();
        }}
      >
        {imageTabs.map((item) => (
          <button
            key={item.id}
            id={`image-tab-${item.id}`}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            aria-controls="image-input-panel"
            tabIndex={tab === item.id ? 0 : -1}
            disabled={reading}
            className={tab === item.id ? s.imageTabActive : ""}
            onClick={() => { setTab(item.id); setDragging(false); dragDepth.current = 0; }}
          >
            {item.label}
          </button>
        ))}
      </div>
      <section
        id="image-input-panel"
        role="tabpanel"
        className={`${s.referenceImages} ${dragging && !locked ? s.referenceDragging : ""}`}
        aria-labelledby={`image-tab-${tab}`}
        aria-busy={reading}
        onDragEnter={(event) => {
          drag(event);
          dragDepth.current++;
          if (!locked && event.dataTransfer.types.includes("Files")) setDragging(true);
        }}
        onDragOver={drag}
        onDragLeave={(event) => {
          event.preventDefault();
          if (--dragDepth.current <= 0) { dragDepth.current = 0; setDragging(false); }
        }}
        onDrop={(event) => {
          event.preventDefault();
          dragDepth.current = 0;
          setDragging(false);
          void add(Array.from(event.dataTransfer.files));
        }}
      >
        <div className={s.referenceIntro}>
          <span className={s.referenceIcon}><ImagePlus size={21} strokeWidth={1.7} /></span>
          <div>
            <h3 id="reference-images-title">Thêm ảnh {imageLabel} <span>(tùy chọn)</span></h3>
            <small id="reference-images-help">JPG, PNG, WEBP · tối đa 5 MB/ảnh · có thể kéo thả</small>
          </div>
        </div>
        <div className={s.referenceGallery}>
          {visibleImages.map((image) => (
            <figure key={image.id} className={s.referenceThumbnail}>
              <img src={image.dataUrl} alt={image.name} title={image.name} />
              <button
                type="button"
                disabled={locked}
                aria-label={`Xóa ${image.name}`}
                onClick={() => onChange(numberedImages.filter((item) => item.id !== image.id), latestNumber)}
              ><X size={13} /></button>
              <figcaption>{image.name}</figcaption>
            </figure>
          ))}
          <input
            id="reference-images-input"
            ref={input}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            hidden
            disabled={locked}
            aria-label={`Chọn ảnh ${imageLabel}`}
            aria-describedby="reference-images-help"
            onChange={(event) => {
              const files = Array.from(event.target.files || []);
              event.target.value = "";
              void add(files);
            }}
          />
          <button
            type="button"
            className={s.referenceAdd}
            disabled={locked}
            onClick={() => input.current?.click()}
            aria-describedby="reference-images-help"
          >
            <Plus size={20} strokeWidth={1.5} />
            <span>{reading ? "Đang đọc…" : "Thêm ảnh"}</span>
          </button>
        </div>
        <span className={s.referenceAnnouncement} role="status">
          {reading ? `Đang đọc ảnh ${imageLabel}` : `Đã thêm ${visibleImages.length} ảnh ${imageLabel}`}
        </span>
      </section>
    </div>
  );
}
