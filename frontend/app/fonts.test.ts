import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, it } from "vitest";
import { config } from "../proxy";
import { fontsFromCss } from "../scripts/fetch-fonts.mjs";

const css = readFileSync(join(process.cwd(), "app/fonts.css"), "utf8");

it("serves every Fontshare face from our own origin first, with the CDN as fallback", () => {
  const faces = css.match(/@font-face\s*{[^}]*}/g) ?? [];
  const fonts = fontsFromCss(css);
  expect(faces).toHaveLength(4);
  expect(fonts).toHaveLength(faces.length);
  for (const { file, url } of fonts) {
    expect(file).toMatch(/^[a-z0-9-]+\.woff2$/);
    expect(url).toMatch(/^https:\/\/cdn\.fontshare\.com\/wf\/.+\.woff2$/);
  }
});

it("lets logged-out visitors load /fonts/ (the session proxy skips it)", () => {
  const matcher = new RegExp(`^${config.matcher[0]}$`);
  expect(matcher.test("/fonts/tanker-400.woff2")).toBe(false);
  expect(matcher.test("/dashboard")).toBe(true);
});
