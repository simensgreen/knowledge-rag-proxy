/**
 * Minimal stubs for local typecheck when @vellumai/plugin-api is not installed.
 * At runtime Vellum provides the real package.
 */
declare module "@vellumai/plugin-api" {
  export interface InitContext {
    config: unknown;
    logger: {
      info: (obj: object, msg?: string) => void;
      warn: (obj: object, msg?: string) => void;
      error: (obj: object, msg?: string) => void;
    };
    pluginStorageDir: string;
    assistantVersion: string;
  }

  export interface ToolContext {
    conversationId: string;
    workingDir: string;
    requestId?: string;
    signal?: AbortSignal;
    onOutput?: (chunk: string) => void;
    assistantId?: string;
    isInteractive?: boolean;
  }

  export interface ToolExecutionResult {
    content: string;
    isError: boolean;
    status?: string;
    yieldToUser?: boolean;
  }
}
