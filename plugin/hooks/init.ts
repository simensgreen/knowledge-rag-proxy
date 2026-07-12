import type { InitContext } from "@vellumai/plugin-api";

import { checkHealth } from "../src/client.js";
import { parsePluginConfig } from "../src/config.js";
import { setState } from "../src/state.js";

export default async function init(ctx: InitContext): Promise<void> {
  const config = parsePluginConfig(ctx.config);

  let serverHealthy = false;
  try {
    serverHealthy = await checkHealth(config);
  } catch (error) {
    ctx.logger.warn(
      { err: String(error), baseUrl: config.baseUrl },
      "knowledge-rag-proxy: health check failed",
    );
  }

  setState({ config, serverHealthy });

  if (!serverHealthy) {
    ctx.logger.warn(
      { baseUrl: config.baseUrl, credentialRef: config.apiTokenCredentialRef },
      "knowledge-rag-proxy: server unreachable at init; tools will return errors until baseUrl is reachable",
    );
  } else {
    ctx.logger.info(
      { baseUrl: config.baseUrl, credentialRef: config.apiTokenCredentialRef },
      "knowledge-rag-proxy: initialized",
    );
  }
}
