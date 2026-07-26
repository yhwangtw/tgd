import type { Plugin } from "@opencode-ai/plugin"

/**
 * SessionStart — records that tGD's globally installed skills and commands
 * are available. Routing comes from discovered skills, any project-local
 * instructions, and explicit commands; the logging API does not inject model
 * context.
 */
export const SessionStart: Plugin = async ({ client }) => {
  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        try {
          await client.app.log({
            body: {
              service: "tgd-hooks",
              level: "info",
              message: "tGD skills and /tgd-* commands are available for this session.",
            },
          })
        } catch {
          // Logging is advisory; never block session creation.
        }
      }
    },
  }
}
