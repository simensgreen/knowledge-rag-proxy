/** Vellum workspace path resolution and scratch file writes. */

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { openPathAsBlob } from "./stream.js";

export class WorkspacePathError extends Error {
  readonly hint: string;

  constructor(message: string, hint: string) {
    super(message);
    this.name = "WorkspacePathError";
    this.hint = hint;
  }
}

export function resolveWorkspacePath(workingDir: string, relativePath: string): string {
  const trimmed = relativePath.trim();
  if (trimmed.length === 0) {
    throw new WorkspacePathError(
      "workspace_path is empty",
      "Provide a non-empty path relative to the Vellum workspace.",
    );
  }

  if (path.isAbsolute(trimmed)) {
    throw new WorkspacePathError(
      "workspace_path must be relative",
      "Use a path relative to the Vellum workspace root, not an absolute filesystem path.",
    );
  }

  if (trimmed.split(path.sep).includes("..")) {
    throw new WorkspacePathError(
      "workspace_path must not contain '..'",
      "Use a path inside the Vellum workspace; parent-directory segments are blocked.",
    );
  }

  const workspaceRoot = path.resolve(workingDir);
  const resolved = path.resolve(workspaceRoot, trimmed);
  if (!resolved.startsWith(workspaceRoot + path.sep) && resolved !== workspaceRoot) {
    throw new WorkspacePathError(
      "workspace_path escapes the workspace sandbox",
      "Use a path inside the Vellum workspace; no .. segments or paths outside the workspace root.",
    );
  }

  return resolved;
}

export async function openWorkspaceFileBlob(workingDir: string, workspacePath: string): Promise<Blob> {
  const absolutePath = resolveWorkspacePath(workingDir, workspacePath);
  try {
    return await openPathAsBlob(absolutePath);
  } catch {
    throw new WorkspacePathError(
      `File not found in workspace: ${workspacePath}`,
      "Check the path with file_read, or use the conversation attachment basename if the user uploaded a file.",
    );
  }
}

export async function readWorkspaceFile(workingDir: string, workspacePath: string): Promise<Uint8Array> {
  const absolutePath = resolveWorkspacePath(workingDir, workspacePath);
  try {
    return await readFile(absolutePath);
  } catch {
    throw new WorkspacePathError(
      `File not found in workspace: ${workspacePath}`,
      "Check the path with file_read, or use the conversation attachment basename if the user uploaded a file.",
    );
  }
}

const SCRATCH_PREFIX = "scratch/grimoire";

export async function writeScratchFile(
  workingDir: string,
  relativePath: string,
  bytes: Uint8Array,
): Promise<string> {
  const trimmed = relativePath.replace(/^\/+/, "");
  const workspaceRelative = `${SCRATCH_PREFIX}/${trimmed}`;
  const absolutePath = resolveWorkspacePath(workingDir, workspaceRelative);
  await mkdir(path.dirname(absolutePath), { recursive: true });
  await writeFile(absolutePath, bytes);
  return workspaceRelative;
}
