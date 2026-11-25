import { useLayoutEffect, useRef, useState } from "react";
import { numberReferenceImages, type ReferenceImage } from "./referenceImages";
import s from "./Studio.module.css";

function mentionAt(value: string, start: number, end: number) {
  if (start !== end) return null;
  const match = /(?:^|[\s([{])@([a-zA-Z0-9_]*)$/.exec(value.slice(0, start));
  if (!match) return null;
  const from = start - match[1].length - 1;
  const suffix = /^[a-zA-Z0-9_]*/.exec(value.slice(start))![0];
  return { from, to: start + suffix.length, query: match[1].toLowerCase() };
}

export default function SourceTextInput({ value, images, disabled, onChange }: {
  value: string;
  images: ReferenceImage[];
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  const input = useRef<HTMLTextAreaElement>(null);
  const option = useRef<HTMLButtonElement>(null);
  const pendingCaret = useRef<number | null>(null);
  const [selection, setSelection] = useState({ start: 0, end: 0 });
  const [focused, setFocused] = useState(false);
  const [dismissed, setDismissed] = useState<string | null>(null);
  const [active, setActive] = useState(0);
  const mention = mentionAt(value, selection.start, selection.end);
  const context = `${selection.start}:${selection.end}:${value}`;
  const open = focused && !disabled && !!mention && dismissed !== context && images.length > 0;
  const matches = mention ? numberReferenceImages(images).filter((image) => image.name.startsWith(mention.query)) : [];
  const selected = Math.min(active, Math.max(0, matches.length - 1));

  useLayoutEffect(() => {
    if (pendingCaret.current === null || !input.current) return;
    const caret = pendingCaret.current;
    pendingCaret.current = null;
    input.current.focus();
    input.current.setSelectionRange(caret, caret);
    setSelection({ start: caret, end: caret });
  });

  useLayoutEffect(() => {
    if (open) option.current?.scrollIntoView({ block: "nearest" });
  }, [open, selected]);

  function select(image: ReferenceImage) {
    if (!mention) return;
    const after = value.slice(mention.to);
    const text = `@${image.name}${!after ? " " : ""}`;
    pendingCaret.current = mention.from + text.length;
    setDismissed(context);
    onChange(value.slice(0, mention.from) + text + after);
  }

  return <div className={s.sourceEditor}>
    <textarea
      ref={input}
      id="source-text"
      disabled={disabled}
      value={value}
      aria-describedby={images.length ? "source-image-help" : undefined}
      aria-autocomplete="list"
      aria-controls={open ? "source-image-options" : undefined}
      aria-activedescendant={open && matches.length ? `source-image-option-${matches[selected].id}` : undefined}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      onSelect={(event) => {
        const { selectionStart: start, selectionEnd: end } = event.currentTarget;
        setSelection({ start, end });
      }}
      onChange={(event) => {
        const { value: next, selectionStart: start, selectionEnd: end } = event.currentTarget;
        setSelection({ start, end });
        setActive(0);
        setDismissed(null);
        onChange(next);
      }}
      onKeyDown={(event) => {
        if (!open || event.nativeEvent.isComposing) return;
        if (event.key === "Escape") {
          event.preventDefault();
          setDismissed(context);
        } else if (matches.length && ["ArrowDown", "ArrowUp"].includes(event.key)) {
          event.preventDefault();
          setActive((selected + (event.key === "ArrowDown" ? 1 : -1) + matches.length) % matches.length);
        } else if (matches.length && ["Enter", "Tab"].includes(event.key)) {
          event.preventDefault();
          select(matches[selected]);
        }
      }}
      placeholder={'Mưa đá hình thành như thế nào?\n\nHoặc nhập kịch bản chi tiết:\nPhase 1: Giới thiệu\nHoạt ảnh: Bối cảnh, đối tượng và chuyển động…\nAudio: Lời đọc nguyên văn cho phase này.'}
    />
    {images.length > 0 && <small id="source-image-help" className={s.imageMentionHelp}>Gõ @ để chọn ảnh tham khảo.</small>}
    {open && <div className={s.imageMentionPopover}>
      <div className={s.imageMentionHeading}>Chọn ảnh tham khảo</div>
      <div id="source-image-options" role="listbox" aria-label="Ảnh tham khảo" className={s.imageMentionOptions}>
        {matches.map((image, index) => <button
          ref={index === selected ? option : undefined}
          key={image.id}
          id={`source-image-option-${image.id}`}
          type="button"
          role="option"
          aria-selected={index === selected}
          tabIndex={-1}
          className={s.imageMentionOption}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => select(image)}
        >
          <img src={image.dataUrl} alt="" />
          <span>{image.name}</span>
        </button>)}
        {!matches.length && <p className={s.imageMentionEmpty} role="status">Không tìm thấy ảnh phù hợp.</p>}
      </div>
      <small className={s.imageMentionHelp}>↑ ↓ để chọn · Enter để chèn · Esc để đóng</small>
    </div>}
  </div>;
}
