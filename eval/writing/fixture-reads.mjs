// Keep the model's only tool inside the installed variant, including symlinks.
import { realpathSync } from "node:fs";
import { resolve, sep } from "node:path";

export default function fixtureReads(pi) {
  pi.on("tool_call", (event, ctx) => {
    if (event.toolName === "read") {
      try {
        const root = resolve(ctx.cwd, "skills") + sep;
        const file = realpathSync(resolve(ctx.cwd, event.input.path));
        if (file.startsWith(root)) {
          event.input.path = file;
          return undefined;
        }
      } catch {
        // A missing file is also outside the readable fixture inventory.
      }
    }
    return { block: true, reason: "Only installed fixture files may be read." };
  });
}
