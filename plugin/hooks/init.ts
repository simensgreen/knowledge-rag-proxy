import type { InitContext } from "@vellumai/plugin-api";

import { probeServerReachable } from "../src/client.js";
import { parsePluginConfig } from "../src/config.js";
import { setState } from "../src/state.js";

export default async function init(ctx: InitContext): Promise<void> {
  const config = parsePluginConfig(ctx.config);
  setState({ config });

  const probe = await probeServerReachable(config, { signal: AbortSignal.timeout(5000) });

  if (probe.reachable) {
    ctx.logger.info(
      { baseUrl: config.baseUrl, status: probe.status },
      probe.authenticated
        ? "grimoire: initialized; server reachable and token accepted"
        : "grimoire: initialized; server reachable but token rejected - fix apiToken in config.json to match GRIM_BEARER",
    );
  } else {
    ctx.logger.warn(
      { baseUrl: config.baseUrl, err: probe.error },
      "grimoire: initialized; server unreachable at baseUrl - tools will report the exact cause per request",
    );
  }
}
