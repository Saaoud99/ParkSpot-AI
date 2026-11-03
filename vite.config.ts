// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  vite: {
    server: {
      watch: {
        // ENOSPC fix: Vite/chokidar recursively watches the project root.
        // This repo also holds a Python .venv (PyTorch/SAM/EasyOCR = tens of
        // thousands of dirs), local AI model caches and logs — none of which
        // are frontend sources. Watching them exhausts the OS inotify limit
        // (fs.inotify.max_user_watches) and crashes `vite dev` with
        // "System limit for number of file watchers reached".
        // node_modules/.git are re-listed because a user-supplied `ignored`
        // replaces Vite's defaults.
        ignored: [
          "**/node_modules/**",
          "**/.git/**",
          "**/.venv/**",
          "**/.local-ai-cache/**",
          "**/.local-ai-logs/**",
          "**/.idea/**",
          "**/.nitro/**",
          "**/.output/**",
          "**/.tanstack/**",
          "**/dist/**",
        ],
      },
    },
  },
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
});
