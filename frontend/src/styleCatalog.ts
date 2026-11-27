import type { StyleId } from "./styleConfig";

export function getStyle(id: StyleId) {
  const name = id.replaceAll("-", " ");
  return {
    id,
    name: name.charAt(0).toUpperCase() + name.slice(1),
    description: "",
  };
}
