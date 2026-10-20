import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { expect, it } from "vitest";

const ROOT = process.cwd();
const SCANNED = ["app", "components", "lib"];
const SOURCE = /\.(css|tsx?|jsx?)$/;
// A raw colour: #rgb, #rrggbb or #rrggbbaa (but not an id like "#golden-hour"),
// a 0xRRGGBB number (Three.js), or an rgb()/hsl() literal.
const RAW_COLOUR = /#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})(?![0-9a-z-])|0x[0-9a-f]{6}\b|\b(?:rgba?|hsla?)\(/i;

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path);
    return SOURCE.test(name) ? [path] : [];
  });
}

it("keeps every raw colour value in app/tokens.css", () => {
  const offenders = SCANNED.flatMap((dir) => files(join(ROOT, dir)))
    // scrollcraft.js is the vendored scroll engine: its only colour code interpolates
    // values it is given, so it holds no palette of its own.
    .filter((path) => !path.endsWith("tokens.css") && !path.endsWith("scrollcraft.js") && !/\.test\.tsx?$/.test(path))
    .flatMap((path) => readFileSync(path, "utf8").split("\n")
      .map((line, index) => ({ line, at: `${relative(ROOT, path)}:${index + 1}` }))
      .filter(({ line }) => RAW_COLOUR.test(line))
      .map(({ at, line }) => `${at}  ${line.trim().slice(0, 80)}`));
  expect(offenders).toEqual([]);
});
