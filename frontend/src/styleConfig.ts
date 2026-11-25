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
function categoryStyles(category: StyleConfig["categories"][string]): StyleId[] {
  return [...new Set(Object.values(category.templates).flatMap((template) => template.allowed_styles))];
}

export const categories = Object.entries(config.categories).map(
  ([id, value]) => ({
    id: id as CategoryId,
    label: value.label,
    allowedStyles: categoryStyles(value),
  }),
);
export const defaultCategoryId = categories[0].id;
export const defaultStyleId = config.default_style;

export function isCategoryId(value: unknown): value is CategoryId {
  return typeof value === "string" && Object.hasOwn(config.categories, value);
}

const legacyCategories: Record<string, CategoryId> = {
  technology: "science",
  politics_society: "news_current_affairs",
  lifestyle: "news_current_affairs",
  environment: "all_styles",
  disasters_accidents: "all_styles",
  law_security: "all_styles",
  culture_entertainment: "all_styles",
  sports: "all_styles",
  travel: "all_styles",
  "3D": "all_styles",
};

export function restoreCategory(value: unknown): CategoryId | undefined {
  if (isCategoryId(value)) return value;
  return typeof value === "string" && Object.hasOwn(legacyCategories, value)
    ? legacyCategories[value] : undefined;
}

export function styleForCategory(
  categoryId: CategoryId,
  styleId: StyleId,
): StyleId {
  const allowed = categoryStyles(config.categories[categoryId]);
  if (!allowed.length) return styleId;
  if (allowed.includes(styleId)) return styleId;
  return allowed.includes(defaultStyleId) ? defaultStyleId : allowed[0];
}

// Version 1 drafts originally offered six visual presets. Keep their content
// when opening them with the category-based configuration.
const legacyStyles: Record<string, StyleId> = {
  "3D-Motion-InFographic": "3d-motion-infographic",
  "3D-Motion-Infographic": "3d-motion-infographic",
  "3D-Motion_Infographic": "3d-motion-infographic",
  cartoon: "outlined-cartoon",
  dark: "detailed-vector",
  watercolor: "detailed-vector",
  pixel: "detailed-vector",
  sketch: "detailed-vector",
};

export function restoreStyle(value: unknown): StyleId | undefined {
  if (
    value === "detailed-vector" ||
    value === "outlined-cartoon" ||
    value === "flat" ||
    (typeof value === "string" && categories.some((category) => category.allowedStyles.includes(value)))
  )
    return value;
  return typeof value === "string" && Object.hasOwn(legacyStyles, value)
    ? legacyStyles[value]
    : undefined;
}
