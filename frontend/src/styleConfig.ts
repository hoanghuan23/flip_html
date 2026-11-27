import styleConfig from "../../config/style_config.json";

export type StyleId = string;
export type CategoryId = string;
interface StyleConfig {
  categories: Record<CategoryId, {
    label: string;
    templates: Record<string, { allowed_styles: StyleId[] }>;
  }>;
  default_style: StyleId;
}

const config: StyleConfig = styleConfig;
function categoryStyles(category?: StyleConfig["categories"][string]): StyleId[] {
  return category ? [...new Set(Object.values(category.templates).flatMap((template) => template.allowed_styles))] : [];
}

export const categories = Object.entries(config.categories).map(([id, value]) => ({
  id, label: value.label, allowedStyles: categoryStyles(value),
}));
export const defaultCategoryId = categories[0]?.id ?? "";
export const defaultStyleId = config.default_style;

export function isCategoryId(value: unknown): value is CategoryId {
  return typeof value === "string" && Object.hasOwn(config.categories, value);
}

// Retain saved selections as metadata so existing previews can still be exported.
// Only config.categories supplies choices to the UI.
function savedId(value: unknown): string | undefined {
  return typeof value === "string" && /^[a-zA-Z0-9_-]*$/.test(value) ? value : undefined;
}
export const restoreCategory = savedId;
export const restoreStyle = savedId;

export function styleForCategory(categoryId: CategoryId, styleId: StyleId): StyleId {
  const allowed = categoryStyles(Object.hasOwn(config.categories, categoryId) ? config.categories[categoryId] : undefined);
  if (!allowed.length || allowed.includes(styleId)) return styleId;
  return allowed.includes(defaultStyleId) ? defaultStyleId : allowed[0];
}
