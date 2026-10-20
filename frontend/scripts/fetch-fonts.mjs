// Downloads the Fontshare faces declared in app/fonts.css into public/fonts/ so the
// console serves them from its own origin. The ITF Free Font License allows that but
// forbids redistributing the files from this repository, so public/fonts/ is
// gitignored and filled at build time (npm's predev/prebuild hooks). A failed fetch
// never fails the build: fonts.css lists the CDN copy after the local one.
import { mkdir, readFile, rename, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(ROOT, "public/fonts");
// src: url("/fonts/<file>") format("woff2"), url("<CDN url>") format("woff2")
const FACE =
  /url\("\/fonts\/([^"]+)"\)\s*format\("woff2"\),\s*url\("(https:\/\/cdn\.fontshare\.com\/[^"]+)"\)/g;

/** @param {string} css @returns {{ file: string, url: string }[]} */
export function fontsFromCss(css) {
  return [...css.matchAll(FACE)].map(([, file, url]) => ({ file, url }));
}

async function fetchFont({ file, url }) {
  const target = join(OUT, file);
  if (
    await stat(target).then(
      () => true,
      () => false,
    )
  )
    return "present";
  const response = await fetch(url, { signal: AbortSignal.timeout(15_000) });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const body = Buffer.from(await response.arrayBuffer());
  if (body.subarray(0, 4).toString("latin1") !== "wOF2") throw new Error("not a woff2 file");
  await writeFile(`${target}.part`, body);
  await rename(`${target}.part`, target);
  return "fetched";
}

async function main() {
  const fonts = fontsFromCss(await readFile(join(ROOT, "app/fonts.css"), "utf8"));
  await mkdir(OUT, { recursive: true });
  for (const font of fonts) {
    try {
      console.log(`fonts: ${font.file} ${await fetchFont(font)}`);
    } catch (error) {
      console.warn(`fonts: ${font.file} not fetched (${error.message}); the CDN copy will be used`);
    }
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) await main();
