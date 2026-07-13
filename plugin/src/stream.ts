/** Stream a file from disk into a Blob without loading it entirely into RAM when supported. */

import { readFile } from "node:fs/promises";

type OpenAsBlobFn = (path: string) => Promise<Blob>;

async function tryOpenAsBlob(absolutePath: string): Promise<Blob | null> {
  const fsPromises = await import("node:fs/promises");
  const openAsBlob = (fsPromises as { openAsBlob?: OpenAsBlobFn }).openAsBlob;
  if (typeof openAsBlob !== "function") {
    return null;
  }
  return openAsBlob(absolutePath);
}

export async function openPathAsBlob(absolutePath: string): Promise<Blob> {
  const lazyBlob = await tryOpenAsBlob(absolutePath);
  if (lazyBlob !== null) {
    return lazyBlob;
  }
  const bytes = await readFile(absolutePath);
  return new Blob([bytes]);
}
