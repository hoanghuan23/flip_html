import styleConfig from "../../skills/style_config.json";

export type StyleId = string;
export type CategoryId = string;
interface StyleConfig {
  categories: Record<CategoryId, { label: string; allowed_styles: StyleId[] }>;
  default_style: StyleId;
}

const config: StyleConfig = styleConfig;
export const categories = Object.entries(config.categories).map(
  ([id, value]) => ({
    id: id as CategoryId,
    label: value.label,
    allowedStyles: value.allowed_styles as StyleId[],
  }),
);
export const defaultCategoryId = categories[0].id;
export const defaultStyleId = config.default_style;

export function isCategoryId(value: unknown): value is CategoryId {
  return typeof value === "string" && Object.hasOwn(config.categories, value);
}

export function styleForCategory(
  categoryId: CategoryId,
  styleId: StyleId,
): StyleId {
  const allowed = config.categories[categoryId].allowed_styles as StyleId[];
  if (allowed.includes(styleId)) return styleId;
  return allowed.includes(defaultStyleId) ? defaultStyleId : allowed[0];
}

// Version 1 drafts originally offered six visual presets. Keep their content
// when opening them with the category-based configuration.
const legacyStyles: Record<string, StyleId> = {
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
