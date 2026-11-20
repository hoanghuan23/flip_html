import { useEffect, useRef, useState, type DragEvent } from "react";
import { ImagePlus, Plus, X } from "lucide-react";
import { numberReferenceImages, readReferenceImage, type ReferenceImage } from "./referenceImages";
import s from "./Studio.module.css";

export default function ReferenceImages({ images, lastNumber, onChange, notify, disabled }: {
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
  const dragDepth = useRef(0);
  const locked = disabled || reading;
  const numberedImages = numberReferenceImages(images);
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
          added.push(await readReferenceImage(file));
        } catch (error) {
          errors.push(error instanceof Error ? error.message : "Không thể đọc ảnh.");
        }
        if (!active.current) return;
      }
      if (added.length) onChange([
        ...numberedImages,
        ...added.map((image, index) => ({ ...image, number: latestNumber + index + 1 })),
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
    <section
      className={`${s.referenceImages} ${dragging && !locked ? s.referenceDragging : ""}`}
      aria-labelledby="reference-images-title"
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
          <h3 id="reference-images-title">Thêm hình ảnh tham khảo <span>(tùy chọn)</span></h3>
          <p>Tải lên hình ảnh, sơ đồ, ảnh thực tế… để lưu cùng nội dung và phong cách bạn muốn.</p>
          <p>Bạn có thể ghi trong nội dung: “Sử dụng Hình 1 cho cảnh mở đầu”.</p>
          <small id="reference-images-help">JPG, PNG, WEBP · tối đa 5 MB/ảnh · có thể kéo thả</small>
        </div>
      </div>
      <div className={s.referenceGallery}>
        {numberedImages.map((image) => (
          <figure key={image.id} className={s.referenceThumbnail}>
            <img src={image.dataUrl} alt={`Hình ${image.number}: ${image.name}`} title={image.name} />
            <button
              type="button"
              disabled={locked}
              aria-label={`Xóa Hình ${image.number}: ${image.name}`}
              onClick={() => onChange(numberedImages.filter((item) => item.id !== image.id), latestNumber)}
            ><X size={13} /></button>
            <figcaption>Hình {image.number}</figcaption>
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
          aria-label="Chọn hình ảnh tham khảo"
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
        {reading ? "Đang đọc ảnh tham khảo" : `Đã thêm ${images.length} ảnh tham khảo`}
      </span>
    </section>
  );
}
