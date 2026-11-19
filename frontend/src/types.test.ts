import { describe, expect, it } from "vitest";
import { newProject, parseDraft, sceneValid, signature } from "./types";
import { api, createGraphicsJob, getGraphicsJob, createScriptJob, getScriptJob } from "./services";
import { afterEach, vi } from "vitest";
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
    expect(signature({ ...p, title: "Mới" })).toBe(signature(p));
    expect(signature({ ...p, scriptId: "a".repeat(32) })).not.toBe(signature(p));
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
describe("AI script API boundary", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("posts user content to the Python backend and polls its job", async () => {
    const job = { id: "a".repeat(32), projectId: "p", status: "queued", stage: "queued", result: null, error: null };
    const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify(job)));
    vi.stubGlobal("fetch", fetchMock);
    expect(await createScriptJob("p", "Ý tưởng của tôi")).toEqual(job);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ projectId: "p", content: "Ý tưởng của tôi" });
    expect(await getScriptJob(job.id)).toEqual(job);
    expect(fetchMock.mock.calls[1][0]).toBe(`/api/scripts/${job.id}`);
  });
  it("reports a missing job and a network failure without demo fallback", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Không tìm thấy tác vụ" }), { status: 404 })));
    await expect(getScriptJob("a".repeat(32))).rejects.toThrow("Không tìm thấy tác vụ");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(api("/api/scripts")).rejects.toThrow("Không kết nối được máy chủ");
  });
  it("keeps safe canonical references but never resumes imported pending jobs", () => {
    const p = newProject();
    const id = "b".repeat(32);
    expect(parseDraft({ ...p, scriptId: id, scriptJobId: id }).scriptId).toBe(id);
    expect(parseDraft({ ...p, scriptJobId: id }).scriptJobId).toBeUndefined();
    expect(parseDraft({ ...p, scriptId: "https://untrusted" }).scriptId).toBeUndefined();
  });
});

describe("graphics generation contract", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("submits only canonical script and selected style references", async () => {
    const project = { ...newProject(), scriptId: "c".repeat(32) };
    const job = { id: "d".repeat(32), projectId: project.id, status: "queued", stage: "queued", completed: 0, total: 0, error: null, result: null };
    const fetchMock = vi.fn().mockImplementation(async () => new Response(JSON.stringify(job)));
    vi.stubGlobal("fetch", fetchMock);
    expect(await createGraphicsJob(project)).toEqual(job);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      projectId: project.id, scriptId: project.scriptId, categoryId: project.categoryId, styleId: project.styleId,
    });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/graphics");
    expect(await getGraphicsJob(job.id)).toEqual(job);
    expect(fetchMock.mock.calls[1][0]).toBe(`/api/graphics/${job.id}`);
  });
  it("does not resume graphics tasks supplied by imported draft JSON", () => {
    const project = { ...newProject(), graphicsJobId: "a".repeat(32) };
    expect(parseDraft(project).graphicsJobId).toBeUndefined();
  });
});
