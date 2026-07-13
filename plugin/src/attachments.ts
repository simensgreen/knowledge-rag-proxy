/** Resolve chat attachment paths under the Vellum workspace. */

import { access, readdir } from "node:fs/promises";
import path from "node:path";

import { openPathAsBlob } from "./stream.js";

export class AttachmentPathError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AttachmentPathError";
  }
}

export async function resolveAttachmentPath(
  workspaceDir: string,
  conversationId: string,
  filename: string,
): Promise<string> {
  const conversationsDir = path.join(workspaceDir, "conversations");
  const entries = await readdir(conversationsDir, { withFileTypes: true });
  const suffix = `_${conversationId}`;

  for (const entry of entries) {
    if (!entry.isDirectory() || !entry.name.endsWith(suffix)) {
      continue;
    }

    const candidate = path.join(conversationsDir, entry.name, "attachments", filename);
    try {
      await access(candidate);
      return candidate;
    } catch {
      continue;
    }
  }

  throw new AttachmentPathError(
    `Attachment not found for conversation ${conversationId}: ${filename}`,
  );
}

export async function openAttachmentBlob(absolutePath: string): Promise<Blob> {
  return openPathAsBlob(absolutePath);
}
