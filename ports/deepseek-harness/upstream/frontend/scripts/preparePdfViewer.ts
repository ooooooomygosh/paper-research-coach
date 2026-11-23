import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { strFromU8, strToU8, unzipSync } from "fflate";

// Mozilla's official generic viewer, legacy build, from the same release as pdfjs-dist.
const VERSION = "6.3.289";
const ARCHIVE = `pdfjs-${VERSION}-legacy-dist.zip`;
const SHA256 = "51683fac4aff7dd31ed91e9ab735a2098a78d50899d1ec529aed6dc8aa19400d";
const RELEASE = `https://github.com/mozilla/pdf.js/releases/download/v${VERSION}/${ARCHIVE}`;

async function verifiedArchive() {
  const override = process.env.PRC_PDFJS_VIEWER_ZIP;
  const path = override || resolve("node_modules/.cache/prc-pdf-viewer", ARCHIVE);
  let bytes: Uint8Array;
  let cache = false;
  try {
    bytes = await readFile(path);
  } catch (error) {
    if (override || (error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    const response = await fetch(RELEASE, { signal: AbortSignal.timeout(60_000) });
    if (!response.ok) throw new Error(`PDF.js viewer download failed (HTTP ${response.status})`);
    bytes = new Uint8Array(await response.arrayBuffer());
    cache = true;
  }
  if (createHash("sha256").update(bytes).digest("hex") !== SHA256) {
    throw new Error(`SHA-256 mismatch for ${ARCHIVE}`);
  }
  if (cache) {
    await mkdir(dirname(path), { recursive: true });
    const temp = path + "." + randomUUID();
    try {
      await writeFile(temp, bytes);
      await rename(temp, path);
    } finally {
      await rm(temp, { force: true });
    }
  }
  return bytes;
}

function replaceRequired(source: string, before: string, after: string) {
  if (!source.includes(before)) throw new Error(`Unable to configure PDF.js viewer: ${before}`);
  return source.replace(before, after);
}

function configureViewer(source: string) {
  for (const [option, from, to] of [
    ["defaultUrl", '"compressed.tracemonkey-pldi-09.pdf"', '""'],
    ["disablePreferences", "false", "true"],
    ["enableScripting", "true", "false"],
    ["enableAltTextModelDownload", "true", "false"],
    ["enableGuessAltText", "true", "false"],
    ["enableNewAltTextWhenAddingImage", "true", "false"],
  ]) {
    source = replaceRequired(source, `["${option}", {\n  value: ${from},`, `["${option}", {\n  value: ${to},`);
  }
  source = replaceRequired(source, 'file = params.get("file") ?? AppOptions.get("defaultUrl");', 'file = AppOptions.get("defaultUrl");');
  return replaceRequired(source, "this._initializeAutoPrint(pdfDocument, openActionPromise);", "/* Print only from the viewer controls. */");
}

export async function preparePdfViewer(destination: string) {
  const files = unzipSync(await verifiedArchive(), {
    filter: ({ name }) => !name.endsWith("/") && !name.endsWith(".map") &&
      !name.endsWith(".pdf") && !name.includes("sandbox") && !name.includes("quickjs"),
  });
  files["web/viewer.mjs"] = strToU8(configureViewer(strFromU8(files["web/viewer.mjs"])));
  files["web/viewer.html"] = strToU8(replaceRequired(
    strFromU8(files["web/viewer.html"]), "connect-src * blob: data:;", "connect-src 'self' blob: data:;",
  ));
  await Promise.all(Object.entries(files).map(async ([name, bytes]) => {
    const path = resolve(destination, name);
    await mkdir(dirname(path), { recursive: true });
    const temp = path + "." + randomUUID();
    try {
      await writeFile(temp, bytes);
      await rename(temp, path);
    } finally {
      await rm(temp, { force: true });
    }
  }));
}
