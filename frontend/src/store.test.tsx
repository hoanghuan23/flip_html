import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { StudioProvider, useStudio } from "./store";
import { newProject } from "./types";

afterEach(() => vi.unstubAllGlobals());

function RestoredAudio() {
  const { state } = useStudio();
  return <span>{state.projects[0].snapshot?.phases[0].audio?.url}</span>;
}

describe("saved narration", () => {
  it.each(["wav", "mp3"])("restores %s audio using the local preview URL", (extension) => {
    const snapshotId = "a".repeat(32);
    const filename = `${"b".repeat(64)}.${extension}`;
    const project = {
      ...newProject(),
      snapshot: {
        id: snapshotId,
        phases: [{
          id: "1", duration: 2, url: "https://old.example/phase_1.html",
          audio: { url: `https://old.example/assets/audio/${filename}`, duration: 2 },
        }],
      },
    };
    vi.stubGlobal("localStorage", {
      getItem: () => JSON.stringify({ version: 1, projects: [project], activeId: project.id }),
    });
    const html = renderToStaticMarkup(<StudioProvider><RestoredAudio /></StudioProvider>);
    expect(html).toContain(`/api/previews/${snapshotId}/assets/audio/${filename}`);
    expect(html).not.toContain("old.example");
  });
});
