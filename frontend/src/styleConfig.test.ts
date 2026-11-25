import { expect, it, vi } from "vitest";
import { categories, restoreStyle, styleForCategory } from "./styleConfig";
import { getStyle } from "./styleCatalog";
import { newProject, parseDraft } from "./types";

vi.mock("../../config/style_config.json", () => ({
  default: {
    categories: {
      news_current_affairs: {
        label: "Thời sự - tin tức",
        templates: {
          id_1: { allowed_styles: ["flat", "flat-with-black"] },
          id_2: { allowed_styles: ["flat", "halftone-line", "future-style"] },
        },
      },
      economy_finance: { label: "Kinh doanh", templates: { id_3: { allowed_styles: [] } } },
      health: { label: "Sức khỏe", templates: {} },
    },
    default_style: "flat",
  },
}));

it("keeps configured styles in order and restores their draft selections", () => {
  const ids = ["flat", "flat-with-black", "halftone-line", "future-style"];
  const category = categories[0];
  expect(category.allowedStyles.map(getStyle).map((style) => style.id)).toEqual(ids);
  expect(getStyle("flat-with-black").name).toBe("Flat with black");
  expect(getStyle("halftone-line").name).toBe("Halftone line");
  expect(getStyle("future-style").name).toBe("Future style");
  for (const id of ids) {
    expect(restoreStyle(id)).toBe(id);
    expect(parseDraft({ ...newProject(), categoryId: category.id, styleId: id }).styleId).toBe(id);
  }
});

it("selects allowed styles across templates and preserves selections for empty categories", () => {
  expect(styleForCategory("news_current_affairs", "future-style")).toBe("future-style");
  expect(styleForCategory("news_current_affairs", "unknown")).toBe("flat");
  for (const category of categories.slice(1)) {
    expect(category.allowedStyles).toEqual([]);
    expect(styleForCategory(category.id, "future-style")).toBe("future-style");
  }
});
