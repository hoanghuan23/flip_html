import { expect, it } from "vitest";
import { categories, restoreStyle, styleForCategory } from "./styleConfig";
import { getStyle } from "./styleCatalog";
import { newProject, parseDraft } from "./types";

it("has no configured choices and restores saved draft styles", () => {
  const ids = ["flat", "flat-with-black", "halftone-line", "future-style"];
  expect(categories).toEqual([]);
  expect(getStyle("flat-with-black").name).toBe("Flat with black");
  expect(getStyle("halftone-line").name).toBe("Halftone line");
  expect(getStyle("future-style").name).toBe("Future style");
  for (const id of ids) {
    expect(restoreStyle(id)).toBe(id);
    expect(parseDraft({ ...newProject(), categoryId: "news_current_affairs", styleId: id }).styleId).toBe(id);
  }
});

it("preserves saved style selections without a category configuration", () => {
  expect(styleForCategory("news_current_affairs", "future-style")).toBe("future-style");
  expect(styleForCategory("news_current_affairs", "unknown")).toBe("unknown");
  expect(styleForCategory("", "")).toBe("");
});
