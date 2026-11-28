import { styles, type StyleId } from "./styleConfig";

export function getStyle(id: StyleId) {
  const configured = styles.find((style) => style.id === id);
  if (configured) return configured;
  const name = id.replaceAll("-", " ");
  return {
    id,
    name: name.charAt(0).toUpperCase() + name.slice(1),
    description: "",
  };
}
