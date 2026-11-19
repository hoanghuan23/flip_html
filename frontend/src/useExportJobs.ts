import { useEffect, useRef, useState } from "react";
import { ApiError, exportVideo, getRenderJob } from "./services";
import { useStudio } from "./store";
import { signature, type ExportConfig, type RenderJob } from "./types";

const finished = (job?: RenderJob) => job?.status === "succeeded" || job?.status === "failed";

export function useExportJobs() {
  const { state, dispatch } = useStudio();
  const current = state.projects.find((p) => p.id === state.activeId)!;
  const stateRef = useRef(state);
  stateRef.current = state;
  const starting = useRef(new Set<string>());
  const [startingIds, setStartingIds] = useState<string[]>([]);
  const [jobs, setJobs] = useState<Record<string, RenderJob>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const pendingKey = JSON.stringify(state.projects
    .filter((p) => p.jobId && !finished(jobs[p.jobId]))
    .map((p) => ({ projectId: p.id, jobId: p.jobId! })));

  useEffect(() => {
    const pending: { projectId: string; jobId: string }[] = JSON.parse(pendingKey);
    if (!pending.length) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      await Promise.all(pending.map(async ({ projectId, jobId }) => {
        try {
          const job = await getRenderJob(jobId);
          if (stopped || stateRef.current.projects.find((p) => p.id === projectId)?.jobId !== jobId) return;
          setJobs((values) => ({ ...values, [jobId]: job }));
          setErrors((values) => ({ ...values, [projectId]: "" }));
        } catch (error) {
          if (stopped || stateRef.current.projects.find((p) => p.id === projectId)?.jobId !== jobId) return;
          if (error instanceof ApiError && error.status === 404) {
            dispatch({ type: "patch", id: projectId, patch: { jobId: undefined } });
            setErrors((values) => ({ ...values, [projectId]: error.message }));
          } else {
            setErrors((values) => ({ ...values, [projectId]: "Tạm mất kết nối. Đang tự kết nối lại để theo dõi xuất video…" }));
          }
        }
      }));
      if (!stopped) timer = setTimeout(() => void poll(), 1500);
    }
    void poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [pendingKey, dispatch]);

  const job = current.jobId ? jobs[current.jobId] : undefined;
  const busy = startingIds.includes(current.id) || (!!current.jobId && !finished(job));

  async function create(config: ExportConfig) {
    const project = current;
    if (busy || starting.current.has(project.id) || !project.snapshot || project.scriptJobId ||
        project.graphicsJobId || project.snapshot.sourceSignature !== signature(project)) return false;
    starting.current.add(project.id);
    setStartingIds((ids) => [...ids, project.id]);
    setErrors((values) => ({ ...values, [project.id]: "" }));
    try {
      const result = await exportVideo(project.snapshot.id, config);
      setJobs((values) => ({ ...values, [result.id]: result }));
      dispatch({ type: "patch", id: project.id, patch: { jobId: result.id, lastExportConfig: config } });
      return true;
    } catch (error) {
      setErrors((values) => ({ ...values, [project.id]: error instanceof Error ? error.message : "Không thể xuất video. Hãy thử lại." }));
      return false;
    } finally {
      starting.current.delete(project.id);
      setStartingIds((ids) => ids.filter((id) => id !== project.id));
    }
  }

  return { job, busy, starting: startingIds.includes(current.id), error: errors[current.id], create };
}
