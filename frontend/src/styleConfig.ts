import config from "../../config/style_config.json";

export type StyleId = string;
export type CategoryId = string;

export const styles = config.styles;
export const categories: { id: CategoryId; label: string; allowedStyles: StyleId[] }[] =
  config.categories.map(({ id, label, allowed_styles }) => ({
    id,
    label,
    allowedStyles: allowed_styles,
  }));
export const defaultCategoryId = config.default_category;
export const defaultStyleId = config.default_style;

export function isCategoryId(value: unknown): value is CategoryId {
  return categories.some((category) => category.id === value);
}

// Retain saved selections as metadata so existing previews can still be exported.
function savedId(value: unknown): string | undefined {
  return typeof value === "string" && /^[a-zA-Z0-9_-]*$/.test(value) ? value : undefined;
}
export const restoreCategory = savedId;
export const restoreStyle = savedId;

export function styleForCategory(categoryId: CategoryId, styleId: StyleId): StyleId {
  const category = categories.find((item) => item.id === categoryId);
  if (!category || category.allowedStyles.includes(styleId)) return styleId;
  return category.allowedStyles[0] ?? "";
}
