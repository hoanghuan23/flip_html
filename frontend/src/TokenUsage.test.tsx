import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { PhaseUsage, StageUsage, TokenSummary } from "./TokenUsage";
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
  it("shows only the selected phase and keeps shared assets out of its total", () => {
    const breakdown = {
      ...usage, input_tokens: 480, output_tokens: 90, cached_input_tokens: 240, total_tokens: 570, requests: 3,
      phases: { "1": usage, "2": { ...usage, input_tokens: 240, total_tokens: 270 } }, shared: usage,
    };
    const html = renderToStaticMarkup(<PhaseUsage phaseId="1" label="Phase 1" usage={{ graphics: breakdown, animation: breakdown }} />);
    expect(html).toContain("Token · Phase 1");
    expect(html).toContain("Tổng phase <b>300</b>");
    expect(html).toContain("Thư viện/tác vụ dùng chung cho các phase: 300 token");
    const second = renderToStaticMarkup(<PhaseUsage phaseId="2" label="Phase 2" usage={{ graphics: breakdown, animation: breakdown }} />);
    expect(second).toContain("Tổng phase <b>540</b>");
    expect(second).not.toContain("Tổng phase <b>300</b>");
    expect(parseDraft({ ...newProject(), tokenUsage: { animation: breakdown } }).tokenUsage).toEqual({ animation: breakdown });
  });
  it("distinguishes legacy totals, cache hits and incomplete attribution", () => {
    expect(renderToStaticMarkup(<PhaseUsage phaseId="1" label="Phase 1" usage={{ animation: usage }} />))
      .toContain("Lượt tạo này chưa lưu token theo phase");
    const zero = { input_tokens: 0, output_tokens: 0, cached_input_tokens: 0, total_tokens: 0, requests: 0, unknown_requests: 0 };
    expect(renderToStaticMarkup(<PhaseUsage phaseId="1" label="Phase 1" usage={{ animation: { ...zero, phases: { "1": zero }, shared: zero } }} />))
      .toContain("Tổng phase <b>0</b>");
    const partial = renderToStaticMarkup(<PhaseUsage phaseId="1" label="Phase 1" usage={{ animation: { ...usage, requests: 2, phases: { "1": usage } } }} />);
    expect(partial).toContain("Tổng phase <b>≥ 150</b>");
    expect(partial).toContain("dữ liệu cũ chưa tách đủ theo phase");
    expect(validTokenUsage({ animation: { ...usage, phases: { "1": { ...usage, total_tokens: -1 } } } })).toBe(false);
    expect(validTokenUsage({ animation: { ...usage, shared: { ...usage, requests: "1" } } })).toBe(false);
  });
});
