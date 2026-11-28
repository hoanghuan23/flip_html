export type StyleId = string;
export type CategoryId = string;

export const categories: { id: CategoryId; label: string; allowedStyles: StyleId[] }[] = [];
export const defaultCategoryId = "";
export const defaultStyleId = "";

export function isCategoryId(_value: unknown): _value is CategoryId {
  return false;
}

// Retain saved selections as metadata so existing previews can still be exported.
function savedId(value: unknown): string | undefined {
  return typeof value === "string" && /^[a-zA-Z0-9_-]*$/.test(value) ? value : undefined;
}
export const restoreCategory = savedId;
export const restoreStyle = savedId;

export function styleForCategory(_categoryId: CategoryId, styleId: StyleId): StyleId {
  return styleId;
}
