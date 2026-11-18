import { describe, expect, it } from "vitest";
import { newProject, parseDraft, sceneValid, signature } from "./types";
import { MockVideoService } from "./services";
import { categories, styleForCategory } from "./styleConfig";

describe("draft and snapshot contracts", () => {
  it("accepts only a versioned project shape with valid scenes", () => {
    const p = newProject();
    expect(parseDraft(p).title).toBe(p.title);
    expect(() =>
      parseDraft({ ...p, scenes: [{ id: "x", name: "Cảnh", duration: 0 }] }),
    ).toThrow();
    expect(() => parseDraft({ ...p, styleId: "unknown" })).toThrow();
  });
  it("invalidates preview on renderable edits, preserving chat-only changes", () => {
    const p = newProject();
    expect(
      signature({ ...p, messages: [{ id: "x", role: "user", text: "Chào" }] }),
    ).toBe(signature(p));
    expect(signature({ ...p, styleId: "outlined-cartoon" })).not.toBe(
      signature(p),
    );
    expect(signature({ ...p, categoryId: "science" })).not.toBe(signature(p));
    expect(signature({ ...p, title: "Mới" })).not.toBe(signature(p));
    expect(
      sceneValid({
        id: "x",
        name: "Cảnh",
        narration: "",
        description: "",
        duration: NaN,
      }),
    ).toBe(false);
  });
  it("restores editable data without trusting URLs from an imported file", () => {
    const p = newProject();
    const imported = parseDraft({
      ...p,
      snapshot: { id: "bad", url: "https://invalid" },
      jobId: "bad",
    });
    expect(imported.snapshot).toBeUndefined();
    expect(imported.jobId).toBeUndefined();
  });
});
describe("category style configuration", () => {
  it("keeps a permitted style and resets an incompatible selection", () => {
    expect(categories.find((c) => c.id === "science")?.label).toBe("Khoa học");
    expect(styleForCategory("science", "outlined-cartoon")).toBe(
      "flat",
    );
    expect(styleForCategory("technology", "outlined-cartoon")).toBe(
      "isometric-mono",
    );
    expect(styleForCategory("science", "flat")).toBe("flat");
    expect(styleForCategory("technology", "flat")).toBe("isometric-mono");
    const p = newProject();
    expect(
      parseDraft({
        ...p,
        categoryId: "technology",
        styleId: "outlined-cartoon",
      }).styleId,
    ).toBe("isometric-mono");
    expect(
      parseDraft({ ...p, categoryId: "all_styles", styleId: "one-line" }).styleId,
    ).toBe("one-line");
    expect(() => parseDraft({ ...p, categoryId: "unknown" })).toThrow();
  });
  it("preserves scenes in older drafts with legacy visual presets", () => {
    const p = newProject();
    const scene = {
      id: "kept",
      name: "Cảnh cũ",
      narration: "Nội dung cũ",
      description: "",
      duration: 3,
    };
    const imported = parseDraft({
      ...p,
      categoryId: undefined,
      styleId: "cartoon",
      scenes: [scene],
    });
    expect(imported.styleId).toBe(styleForCategory(p.categoryId, "outlined-cartoon"));
    expect(imported.scenes).toEqual([scene]);
    expect(parseDraft({ ...p, styleId: "flat" }).styleId).toBe("flat");
  });
});
describe("AI demonstration boundary", () => {
  it("loads example scenes and revises only the requested scene", async () => {
    const service = new MockVideoService();
    const scenes = await service.generateScript("Bài viết");
    const result = await service.reviseScript(scenes[0], "Rút ngắn cảnh");
    expect(result.scene!.id).toBe(scenes[0].id);
    expect(result.scene!.duration).toBeLessThan(scenes[0].duration);
    expect(scenes[0].duration).toBe(6);
    expect(
      (await service.reviseScript(scenes[0], "Yêu cầu không hỗ trợ")).scene,
    ).toBeUndefined();
  });
});
