import type { InitContext } from "@vellumai/plugin-api";

import { probeServerReachable } from "../src/client.js";
import { parsePluginConfig } from "../src/config.js";
import { setState } from "../src/state.js";

export default async function init(ctx: InitContext): Promise<void> {
  const config = parsePluginConfig(ctx.config);

  // Config is the only runtime state tools depend on. The probe below is a
  // best-effort boot diagnostic only; its result is never cached.
  setState({ config });

  // Best-effort boot diagnostic; result is never cached. The token from config is
  // sent, so an unauthenticated /health here means the token is wrong. Bound the
  // probe so an unreachable server can never stall boot.
  const probe = await probeServerReachable(config, { signal: AbortSignal.timeout(5000) });

  if (probe.reachable) {
    ctx.logger.info(
      { baseUrl: config.baseUrl, status: probe.status },
      probe.authenticated
        ? "knowledge-rag-proxy: initialized; server reachable and token accepted"
        : "knowledge-rag-proxy: initialized; server reachable but token rejected - fix apiToken in config.json to match KRP_BEARER",
    );
  } else {
    ctx.logger.warn(
      { baseUrl: config.baseUrl, err: probe.error },
      "knowledge-rag-proxy: initialized; server unreachable at baseUrl - tools will report the exact cause per request",
    );
  }
}
