import { expect, it, vi } from "vitest";
import { categories, restoreStyle } from "./styleConfig";
import { getStyle } from "./styleCatalog";
import { newProject, parseDraft } from "./types";

vi.mock("../../skills/style_config.json", () => ({
  default: {
    categories: {
      news_current_affairs: {
        label: "Thời sự - tin tức",
        allowed_styles: ["flat", "flat-with-black", "halftone-line", "future-style"],
      },
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
