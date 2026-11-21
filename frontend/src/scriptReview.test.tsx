import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import ScenePanel from "./ScenePanel";
import { newProject, parseDraft, safeSourceUrl, sceneValid, type Scene, type ScriptReview } from "./types";

const scene: Scene = {
  id: "1", name: "Mưa đá", narration: "", description: "Mưa đá rơi từ mây.", duration: 7.25,
  voiceover: "Nước đóng băng trong mây.", duration_status: "estimated",
  annotations: [{ text: "Nước đóng băng", target: "CLOUD", action_index: 0, cue: "đóng băng" }],
};
const review: ScriptReview = {
  input_type: "topic", warnings: ["Cần xem lại số liệu."],
  research: { status: "sources_reported", sources: [
    { title: "Nguồn tham khảo", url: "https://example.org/hail", claims: ["Nước đóng băng."] },
  ] },
};

describe("script review persistence and rendering", () => {
  it("round trips new metadata and still reads old drafts", () => {
    const project = { ...newProject(), scenes: [scene], scriptReview: review };
    const restored = parseDraft(JSON.parse(JSON.stringify(project)));
    expect(restored.scriptReview).toEqual(review);
    expect(restored.scenes).toEqual([scene]);
    expect(parseDraft(newProject()).scriptReview).toBeUndefined();
    const second = parseDraft({ ...newProject(), scenes: [] });
    expect(second.scenes).toEqual([]);
    expect(parseDraft(project).scriptReview).toEqual(review);
  });
  it("shows annotations, warnings, estimated duration and unverified source attribution", () => {
    const html = renderToStaticMarkup(<ScenePanel project={{ ...newProject(), scenes: [scene], scriptReview: review }}
      selectedId="1" onSelect={() => {}} />);
    for (const text of ["Chú giải trên màn hình", "Nước đóng băng", "Cần xem lại số liệu",
      "chưa được hệ thống xác minh độc lập", "ƯỚC TÍNH", 'rel="noopener noreferrer"']) {
      expect(html).toContain(text);
    }
    expect(html).not.toContain("CLOUD");
  });
  it("renders unverified drafts and escapes AI text", () => {
    const html = renderToStaticMarkup(<ScenePanel project={{ ...newProject(), scenes: [{ ...scene,
      annotations: [{ text: "<script>alert(1)</script>", target: "CLOUD" }] }],
      scriptReview: { research: { status: "unverified", sources: [] }, warnings: ["<img onerror=alert(1)>"] } }}
      selectedId="1" onSelect={() => {}} />);
    expect(html).toContain("chưa được kiểm chứng bằng nguồn web");
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img onerror");
  });
  it("rejects malformed metadata and executable source links from imports", () => {
    for (const url of ["javascript:alert(1)", "data:text/html,test", "https://user:password@example.org", "not-a-url"]) {
      expect(safeSourceUrl(url)).toBe(false);
      const bad = { ...review, research: { ...review.research!, sources: [{ ...review.research!.sources[0], url }] } };
      expect(() => parseDraft({ ...newProject(), scenes: [scene], scriptReview: bad })).toThrow();
      const html = renderToStaticMarkup(<ScenePanel project={{ ...newProject(), scenes: [scene], scriptReview: bad }}
        selectedId="1" onSelect={() => {}} />);
      expect(html).not.toContain('<a href=');
    }
    expect(() => parseDraft({ ...newProject(), scriptReview: { warnings: "bad" } })).toThrow();
    expect(() => parseDraft({ ...newProject(), scriptReview: { research: { status: "verified", sources: [] } } })).toThrow();
  });
  it("checks annotation cues, types and duration status without changing old scenes", () => {
    expect(sceneValid(scene)).toBe(true);
    expect(sceneValid({ ...scene, annotations: [{ text: "A", target: "CLOUD", cue: "không có" }] })).toBe(false);
    expect(sceneValid({ ...scene, annotations: [{ text: "A", target: "CLOUD", action_index: -1 }] })).toBe(false);
    expect(sceneValid({ ...scene, annotations: [] })).toBe(true);
  });
});
