import { expect, it } from "vitest";
import { categories, defaultCategoryId, defaultStyleId, isCategoryId, restoreStyle, styleForCategory, styles } from "./styleConfig";
import { getStyle } from "./styleCatalog";
import { newProject, parseDraft } from "./types";

it("loads the character cartoon choice and skill paths from the shared config", () => {
  expect(isCategoryId(defaultCategoryId)).toBe(true);
  expect(isCategoryId("unknown")).toBe(false);
  expect(defaultStyleId).toBe("character-cartoon");
  expect(categories.find((category) => category.id === defaultCategoryId)?.allowedStyles)
    .toContain(defaultStyleId);
  expect(getStyle(defaultStyleId)).toMatchObject({
    name: "Character Cartoon",
    skill_path: "skills/styles/character-cartoon/SKILL.md",
    style_path: "skills/styles/character-cartoon/style.json",
  });
  expect(getStyle(defaultStyleId).description).not.toBe("");
  expect(newProject()).toMatchObject({ categoryId: defaultCategoryId, styleId: defaultStyleId });
  for (const category of categories)
    expect(category.allowedStyles.every((id) => styles.some((style) => style.id === id))).toBe(true);
});

it("restores saved draft styles and labels for unconfigured IDs", () => {
  const ids = ["flat", "flat-with-black", "halftone-line", "future-style"];
  expect(getStyle("flat-with-black").name).toBe("Flat with black");
  expect(getStyle("halftone-line").name).toBe("Halftone line");
  expect(getStyle("future-style").name).toBe("Future style");
  for (const id of ids) {
    expect(restoreStyle(id)).toBe(id);
    expect(parseDraft({ ...newProject(), categoryId: "news_current_affairs", styleId: id }).styleId).toBe(id);
  }
});

it("selects an allowed style when changing to a configured category", () => {
  expect(styleForCategory(defaultCategoryId, "future-style")).toBe(defaultStyleId);
  expect(styleForCategory(defaultCategoryId, "")).toBe(defaultStyleId);
  expect(styleForCategory(defaultCategoryId, defaultStyleId)).toBe(defaultStyleId);
  expect(parseDraft({ ...newProject(), styleId: "future-style" }).styleId).toBe("future-style");
});

it("preserves saved style selections without a category configuration", () => {
  expect(styleForCategory("news_current_affairs", "future-style")).toBe("future-style");
  expect(styleForCategory("news_current_affairs", "unknown")).toBe("unknown");
  expect(styleForCategory("", "")).toBe("");
});
