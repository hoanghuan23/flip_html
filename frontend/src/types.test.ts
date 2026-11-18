import { describe, expect, it } from "vitest";
import { newProject, parseDraft, sceneValid, signature } from "./types";
import { MockVideoService } from "./services";

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
    expect(signature({ ...p, styleId: "dark" })).not.toBe(signature(p));
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
