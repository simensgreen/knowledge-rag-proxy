import path from "node:path";

import { ApiError, uploadDocument as uploadToServer } from "../src/client.js";
import { openAttachmentBlob, resolveAttachmentPath } from "../src/attachments.js";
import {
  attachmentProcessKey,
  getState,
  isAttachmentProcessed,
  markAttachmentProcessed,
} from "../src/state.js";
import { writeScratchText } from "../src/workspace.js";

interface FileBlockSource {
  type: string;
  media_type: string;
  attachmentId: string;
  filename?: string;
}

interface FileContentBlock {
  type: "file";
  source: FileBlockSource;
  extracted_text?: string;
}

interface TextContentBlock {
  type: "text";
  text: string;
}

type ContentBlock = FileContentBlock | TextContentBlock | { type: string };

interface Message {
  role: string;
  content: ContentBlock[];
}

interface UserPromptSubmitContext {
  conversationId: string;
  latestMessages: Message[];
  logger: {
    info(obj: Record<string, unknown>, msg?: string): void;
    warn(obj: Record<string, unknown>, msg?: string): void;
    error(obj: Record<string, unknown>, msg?: string): void;
    debug(obj: Record<string, unknown>, msg?: string): void;
  };
}

const ATTACHMENT_UPLOAD_TIMEOUT_MS = 20_000;

function isImageMediaType(mediaType: string): boolean {
  return mediaType.toLowerCase().startsWith("image/");
}

function sanitizeScratchFilename(filename: string): string {
  const base = path.basename(filename);
  const withoutExtension = base.replace(/\.[^.]+$/, "") || base;
  const safe = withoutExtension.replace(/[^a-zA-Z0-9._-]+/g, "_").slice(0, 120);
  return safe.length > 0 ? safe : "attachment";
}

async function prepareInjectionExcerpt(
  workspaceDir: string,
  conversationId: string,
  sourceFilename: string,
  content: string,
  maxChars: number,
): Promise<string> {
  if (content.length <= maxChars) {
    return content;
  }

  const scratchRelative = `injected/${conversationId}/${sanitizeScratchFilename(sourceFilename)}.parsed.txt`;
  const workspacePath = await writeScratchText(workspaceDir, scratchRelative, content);
  return `${content.slice(0, maxChars)}\n\n[truncated at ${maxChars} characters; full text at workspace path: ${workspacePath} — use file_read to read it]`;
}

function findLastUserMessage(messages: Message[]): Message | undefined {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message?.role === "user") {
      return message;
    }
  }
  return undefined;
}

function isFileContentBlock(block: ContentBlock): block is FileContentBlock {
  if (block.type !== "file" || !("source" in block)) {
    return false;
  }
  const source = block.source;
  return (
    typeof source === "object" &&
    source !== null &&
    typeof source.media_type === "string" &&
    typeof source.attachmentId === "string"
  );
}

function collectFileBlocks(message: Message): FileContentBlock[] {
  const blocks: FileContentBlock[] = [];
  for (const block of message.content) {
    if (isFileContentBlock(block) && !isImageMediaType(block.source.media_type)) {
      blocks.push(block);
    }
  }
  return blocks;
}

function attachmentFilename(block: FileContentBlock): string {
  if (typeof block.source.filename === "string" && block.source.filename.length > 0) {
    return block.source.filename;
  }
  return `attachment-${block.source.attachmentId}`;
}

// Auto-uploaded chat attachments land in <base>/<conversationId>/ so each
// conversation's files stay grouped and never collide across chats.
function attachmentTargetFiledir(base: string, conversationId: string): string {
  return `${base}/${conversationId}`;
}

async function buildInjectionText(
  workspaceDir: string,
  conversationId: string,
  filename: string,
  content: string,
  maxChars: number,
): Promise<string> {
  const excerpt = await prepareInjectionExcerpt(
    workspaceDir,
    conversationId,
    filename,
    content,
    maxChars,
  );
  return `[knowledge-rag-proxy] Indexed "${filename}" into the knowledge base. Parsed content:\n${excerpt}`;
}

function shouldSkipAsAlreadyIndexed(error: ApiError): boolean {
  return error.statusCode === 400 && error.message.toLowerCase().includes("already exists");
}

function shouldSkipAsUnsupported(error: ApiError): boolean {
  return error.statusCode === 400 && error.message.toLowerCase().includes("unsupported format");
}

async function uploadAttachmentSaveOnly(
  config: NonNullable<ReturnType<typeof getState>["config"]>,
  absolutePath: string,
  filename: string,
  filedir: string,
): Promise<void> {
  const blob = await openAttachmentBlob(absolutePath);
  await uploadToServer(
    config,
    {
      file: blob,
      filename,
      filedir,
      returnDocument: false,
    },
    { signal: AbortSignal.timeout(ATTACHMENT_UPLOAD_TIMEOUT_MS) },
  );
}

async function uploadAttachmentForInjection(
  config: NonNullable<ReturnType<typeof getState>["config"]>,
  absolutePath: string,
  filename: string,
  filedir: string,
): Promise<string> {
  const blob = await openAttachmentBlob(absolutePath);
  const response = await uploadToServer(
    config,
    {
      file: blob,
      filename,
      filedir,
      returnDocument: true,
    },
    { signal: AbortSignal.timeout(ATTACHMENT_UPLOAD_TIMEOUT_MS) },
  );

  const document = response.document;
  if (document === null || typeof document !== "object") {
    throw new Error("Upload succeeded but returned no document payload");
  }

  const record = document as Record<string, unknown>;
  const content = typeof record.content === "string" ? record.content : "";
  if (content.length === 0) {
    throw new Error("Upload succeeded but parsed document content is empty");
  }

  return content;
}

function scheduleSaveOnlyUpload(
  config: NonNullable<ReturnType<typeof getState>["config"]>,
  absolutePath: string,
  filename: string,
  filedir: string,
  logger: UserPromptSubmitContext["logger"],
): void {
  void (async () => {
    try {
      const blob = await openAttachmentBlob(absolutePath);
      await uploadToServer(config, {
        file: blob,
        filename,
        filedir,
        returnDocument: false,
      });
    } catch (error) {
      logger.warn(
        { err: error instanceof Error ? error.message : String(error), filename },
        "knowledge-rag-proxy: save-only attachment upload failed",
      );
    }
  })();
}

export default async function userPromptSubmit(ctx: UserPromptSubmitContext): Promise<void> {
  try {
    const { config, workspaceDir } = getState();
    if (config === null || workspaceDir === null || !config.autoIndexAttachments) {
      return;
    }

    const userMessage = findLastUserMessage(ctx.latestMessages);
    if (userMessage === undefined) {
      return;
    }

    const fileBlocks = collectFileBlocks(userMessage);
    if (fileBlocks.length === 0) {
      return;
    }

    for (const block of fileBlocks) {
      const attachmentId = block.source.attachmentId;
      if (isAttachmentProcessed(ctx.conversationId, attachmentId)) {
        continue;
      }

      const filename = attachmentFilename(block);
      const targetFiledir = attachmentTargetFiledir(config.attachmentFiledir, ctx.conversationId);
      let absolutePath: string;
      try {
        absolutePath = await resolveAttachmentPath(workspaceDir, ctx.conversationId, filename);
      } catch (error) {
        ctx.logger.warn(
          {
            conversationId: ctx.conversationId,
            attachmentId,
            filename,
            err: error instanceof Error ? error.message : String(error),
          },
          "knowledge-rag-proxy: attachment path resolution failed",
        );
        continue;
      }

      try {
        if (config.injectAttachmentDocument) {
          const parsedContent = await uploadAttachmentForInjection(
            config,
            absolutePath,
            filename,
            targetFiledir,
          );
          let injectionText: string;
          try {
            injectionText = await buildInjectionText(
              workspaceDir,
              ctx.conversationId,
              filename,
              parsedContent,
              config.attachmentMaxInjectChars,
            );
          } catch (writeError) {
            ctx.logger.warn(
              {
                conversationId: ctx.conversationId,
                filename,
                err: writeError instanceof Error ? writeError.message : String(writeError),
              },
              "knowledge-rag-proxy: failed to write full parsed text to workspace; injecting truncated excerpt only",
            );
            const truncated = `${parsedContent.slice(0, config.attachmentMaxInjectChars)}\n\n[truncated at ${config.attachmentMaxInjectChars} characters]`;
            injectionText = `[knowledge-rag-proxy] Indexed "${filename}" into the knowledge base. Parsed content:\n${truncated}`;
          }
          userMessage.content.push({
            type: "text",
            text: injectionText,
          });
        } else {
          await uploadAttachmentSaveOnly(
            config,
            absolutePath,
            filename,
            targetFiledir,
          );
        }
        markAttachmentProcessed(ctx.conversationId, attachmentId);
      } catch (error) {
        if (error instanceof ApiError && (shouldSkipAsAlreadyIndexed(error) || shouldSkipAsUnsupported(error))) {
          markAttachmentProcessed(ctx.conversationId, attachmentId);
          continue;
        }

        ctx.logger.warn(
          {
            conversationId: ctx.conversationId,
            attachmentId,
            filename,
            processKey: attachmentProcessKey(ctx.conversationId, attachmentId),
            err: error instanceof Error ? error.message : String(error),
          },
          "knowledge-rag-proxy: attachment parse-upload failed; scheduling save-only upload",
        );
        scheduleSaveOnlyUpload(config, absolutePath, filename, targetFiledir, ctx.logger);
        markAttachmentProcessed(ctx.conversationId, attachmentId);
      }
    }
  } catch (error) {
    ctx.logger.error(
      { err: error instanceof Error ? error.message : String(error) },
      "knowledge-rag-proxy: user-prompt-submit hook failed",
    );
  }
}
