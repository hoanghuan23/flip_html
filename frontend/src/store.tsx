import {
  createContext,
  useContext,
  useEffect,
  useReducer,
  useState,
  type ReactNode,
} from "react";
import { newProject, parseDraft, type ProjectDraft } from "./types";

const KEY = "ai-video-studio:v1";
interface State {
  projects: ProjectDraft[];
  activeId: string;
}
type Action =
  | { type: "patch"; id: string; patch: Partial<ProjectDraft> }
  | { type: "add"; project: ProjectDraft }
  | { type: "open" | "delete"; id: string };
function initial(): State {
  try {
    const stored = JSON.parse(localStorage.getItem(KEY) || "null");
    if (
      stored?.version === 1 &&
      Array.isArray(stored.projects) &&
      stored.projects.length
    ) {
      const projects = stored.projects.map((p: ProjectDraft) => {
        const validated = parseDraft(p);
        const snapshot =
          p.snapshot && /^[a-f0-9]{32}$/.test(p.snapshot.id)
            ? {
                ...p.snapshot,
                phases: p.snapshot.phases.map((phase, i) => ({
                  ...phase,
                  url: `/api/previews/${p.snapshot!.id}/phase_${i + 1}.html`,
                })),
              }
            : undefined;
        return {
          ...validated,
          updatedAt: p.updatedAt,
          scriptJobId:
            typeof p.scriptJobId === "string" && /^[a-f0-9]{32}$/.test(p.scriptJobId)
              ? p.scriptJobId : undefined,
          graphicsJobId:
            typeof p.graphicsJobId === "string" && /^[a-f0-9]{32}$/.test(p.graphicsJobId)
              ? p.graphicsJobId : undefined,
          snapshot,
          jobId:
            p.jobId && /^[a-f0-9]{32}$/.test(p.jobId) ? p.jobId : undefined,
        };
      });
      return {
        projects,
        activeId: projects.some((p: ProjectDraft) => p.id === stored.activeId)
          ? stored.activeId
          : projects[0].id,
      };
    }
  } catch {
    /* Invalid or inaccessible browser storage starts a new project. */
  }
  const project = newProject();
  return { projects: [project], activeId: project.id };
}
function reducer(state: State, action: Action): State {
  if (action.type === "patch")
    return {
      ...state,
      projects: state.projects.map((p) =>
        p.id === action.id
          ? { ...p, ...action.patch, updatedAt: new Date().toISOString() }
          : p,
      ),
    };
  if (action.type === "add")
    return {
      projects: [action.project, ...state.projects],
      activeId: action.project.id,
    };
  if (action.type === "open") return { ...state, activeId: action.id };
  const projects = state.projects.filter((p) => p.id !== action.id);
  if (!projects.length) {
    const p = newProject();
    return { projects: [p], activeId: p.id };
  }
  return {
    projects,
    activeId: state.activeId === action.id ? projects[0].id : state.activeId,
  };
}
const Context = createContext<null | {
  state: State;
  dispatch: React.Dispatch<Action>;
  saveStatus: string;
}>(null);
export function StudioProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, initial);
  const [saveStatus, setSaveStatus] = useState("Đang mở bản nháp");
  useEffect(() => {
    setSaveStatus("Đang lưu…");
    const timer = setTimeout(() => {
      try {
        localStorage.setItem(KEY, JSON.stringify({ version: 1, ...state }));
        setSaveStatus("Đã lưu trên trình duyệt");
      } catch {
        setSaveStatus("Không thể tự lưu bản nháp trên trình duyệt");
      }
    }, state.projects.some((p) => p.scriptJobId || p.graphicsJobId || p.jobId) ? 0 : 500);
    return () => clearTimeout(timer);
  }, [state]);
  return (
    <Context.Provider value={{ state, dispatch, saveStatus }}>
      {children}
    </Context.Provider>
  );
}
export function useStudio() {
  const value = useContext(Context);
  if (!value) throw new Error("Missing StudioProvider");
  return value;
}
