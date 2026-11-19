import { useEffect, useRef, useState } from "react";
import { ApiError, createGraphicsJob, getGraphicsJob } from "./services";
import { useStudio } from "./store";
import type { GraphicsJob } from "./types";

const stages: Record<string, string> = {
  queued: "Đang chờ tạo đồ họa…",
  preparing: "Đang chuẩn bị kịch bản và phong cách…",
  images: "AI đang sinh hình ảnh",
  phases: "AI đang dựng animation",
  checking: "Đang kiểm tra toàn bộ phase…",
};

export function useGraphicsJobs(notify: (message: string, error?: boolean) => void) {
  const { state, dispatch } = useStudio();
  const current = state.projects.find((p) => p.id === state.activeId)!;
  const stateRef = useRef(state);
  stateRef.current = state;
  const starting = useRef(new Set<string>());
  const [startingIds, setStartingIds] = useState<string[]>([]);
  const [jobs, setJobs] = useState<Record<string, GraphicsJob>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const scrollProject = useRef<string | undefined>(undefined);
  const pendingKey = JSON.stringify(state.projects.filter((p) => p.graphicsJobId)
    .map((p) => ({ projectId: p.id, jobId: p.graphicsJobId! })));

  useEffect(() => {
    if (scrollProject.current === current.id && current.snapshot) {
      scrollProject.current = undefined;
      document.getElementById("xem-truoc")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [current.id, current.snapshot?.id]);

  useEffect(() => {
    const pending: { projectId: string; jobId: string }[] = JSON.parse(pendingKey);
    if (!pending.length) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      await Promise.all(pending.map(async ({ projectId, jobId }) => {
        try {
          const job = await getGraphicsJob(jobId);
          if (stopped) return;
          const project = stateRef.current.projects.find((p) => p.id === projectId);
          if (!project || project.graphicsJobId !== jobId) return;
          setJobs((values) => ({ ...values, [jobId]: job }));
          setErrors((values) => ({ ...values, [projectId]: "" }));
          if (job.status === "succeeded" && job.result) {
            scrollProject.current = projectId;
            dispatch({ type: "patch", id: projectId, patch: {
              snapshot: job.result, graphicsJobId: undefined,
            } });
            if (stateRef.current.activeId === projectId) notify("Đã tạo xong toàn bộ animation. Bạn có thể xem ở mục 3.");
          } else if (job.status === "failed") {
            const message = job.error || "Không thể tạo đồ họa. Hãy thử lại ở mục 2.";
            dispatch({ type: "patch", id: projectId, patch: { graphicsJobId: undefined } });
            setErrors((values) => ({ ...values, [projectId]: message }));
            if (stateRef.current.activeId === projectId) notify(message, true);
          }
        } catch (error) {
          if (stopped) return;
          const missing = error instanceof ApiError && error.status === 404;
          if (missing) dispatch({ type: "patch", id: projectId, patch: { graphicsJobId: undefined } });
          setErrors((values) => ({ ...values, [projectId]: missing
            ? error.message
            : "Tạm mất kết nối. Đang tự kết nối lại để theo dõi đồ họa…" }));
        }
      }));
      if (!stopped) timer = setTimeout(() => void poll(), 1500);
    }
    void poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [pendingKey, dispatch, notify]);

  async function create() {
    const project = current;
    if (!project.scriptId || project.scriptJobId || project.graphicsJobId || starting.current.has(project.id)) return;
    starting.current.add(project.id);
    setStartingIds((ids) => [...ids, project.id]);
    setErrors((values) => ({ ...values, [project.id]: "" }));
    try {
      const job = await createGraphicsJob(project);
      setJobs((values) => ({ ...values, [job.id]: job }));
      dispatch({ type: "patch", id: project.id, patch: { graphicsJobId: job.id } });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không thể tạo đồ họa.";
      setErrors((values) => ({ ...values, [project.id]: message }));
      if (stateRef.current.activeId === project.id) notify(message, true);
    } finally {
      starting.current.delete(project.id);
      setStartingIds((ids) => ids.filter((id) => id !== project.id));
    }
  }

  const busy = !!current.graphicsJobId || startingIds.includes(current.id);
  const job = current.graphicsJobId ? jobs[current.graphicsJobId] : undefined;
  const progress = job && job.total > 0 ? ` · ${job.completed}/${job.total}` : "";
  const error = errors[current.id];
  const status = error || (busy ? `${stages[job?.stage || "queued"] || "Đang xử lý…"}${progress}` : "");
  return { busy, status, error: !!error, create };
}
