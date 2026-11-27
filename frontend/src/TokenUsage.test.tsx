import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { StageUsage, TokenSummary } from "./TokenUsage";
import { newProject, parseDraft, validTokenUsage, type TokenUsage } from "./types";

const usage: TokenUsage = { input_tokens: 120, output_tokens: 30, cached_input_tokens: 80,
  total_tokens: 150, requests: 1, unknown_requests: 0 };

describe("AI usage reporting", () => {
  it("sums three distinct stages without adding cached input again", () => {
    const html = renderToStaticMarkup(<TokenSummary usage={{ script: usage, graphics: usage, animation: usage }} />);
    expect(html).toContain("Tổng 3 giai đoạn");
    expect(html).toContain(">360<");
    expect(html).toContain(">90<");
    expect(html).toContain(">450<");
  });
  it("distinguishes missing usage, measured zero and partial usage", () => {
    expect(renderToStaticMarkup(<StageUsage label="Kịch bản" />)).toContain("Chưa có dữ liệu");
    const partial = renderToStaticMarkup(<TokenSummary usage={{ script: { ...usage, requests: 2, unknown_requests: 1 } }} />);
    expect(partial).toContain("Tổng đã ghi nhận");
    expect(partial).toContain("≥ 120");
    const zero = { ...usage, input_tokens: 0, output_tokens: 0, cached_input_tokens: 0, total_tokens: 0 };
    expect(renderToStaticMarkup(<StageUsage label="Ảnh" usage={{ ...zero, unknown_requests: 1 }} />)).toContain("Chưa có dữ liệu");
    const measuredZero = renderToStaticMarkup(<StageUsage label="Ảnh" usage={{ ...zero, requests: 0 }} />);
    expect(measuredZero).toContain(">0<");
    expect(measuredZero).not.toContain("Chưa có dữ liệu");
  });
  it("persists usage across reloads and drops malformed imported data", () => {
    expect(parseDraft({ ...newProject(), tokenUsage: { script: usage } }).tokenUsage).toEqual({ script: usage });
    expect(parseDraft(newProject()).tokenUsage).toBeUndefined();
    for (const value of [{ script: { ...usage, input_tokens: -1 } },
      { script: { ...usage, total_tokens: 999 } }, { script: { ...usage, unknown_requests: 2 } },
      { unknown: usage }, { script: { ...usage, input_tokens: "120" } }]) {
      expect(validTokenUsage(value)).toBe(false);
      expect(parseDraft({ ...newProject(), tokenUsage: value }).tokenUsage).toBeUndefined();
    }
  });
});
