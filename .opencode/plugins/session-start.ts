import type { Plugin } from "@opencode-ai/plugin"
import { readFileSync, existsSync } from "fs"
import { join, dirname } from "path"

/**
 * SessionStart — injects the tgd-router meta-skill into every session.
 * OpenCode equivalent of Claude Code's SessionStart hook.
 */
export const SessionStart: Plugin = async ({ directory, client }) => {
  // Find skills directory relative to the project
  const skillsDir = join(directory, "skills")
  const metaSkillPath = join(skillsDir, "tgd-router", "SKILL.md")

  return {
    event: async ({ event }) => {
      if (event.type === "session.created") {
        if (existsSync(metaSkillPath)) {
          try {
            const content = readFileSync(metaSkillPath, "utf-8")
            await client.app.log({
              body: {
                service: "tgd-hooks",
                level: "info",
                message: `tGD loaded. Use the skill discovery flowchart to find the right skill for your task.\n\n${content}`,
              },
            })
          } catch {
            // Graceful degradation
          }
        }
      }
    },
  }
}
