import { build } from "esbuild";
import { cp, mkdir, rm } from "node:fs/promises";

await rm("dist", { recursive: true, force: true });
await mkdir("dist", { recursive: true });
await build({
  entryPoints: {
    "page-hook": "src/page-hook.ts",
    content: "src/content.ts",
    background: "src/background.ts",
    options: "src/options.ts",
  },
  outdir: "dist",
  bundle: true,
  format: "iife",
  target: "chrome120",
  logLevel: "info",
});
await cp("static/manifest.json", "dist/manifest.json");
await cp("static/options.html", "dist/options.html");
