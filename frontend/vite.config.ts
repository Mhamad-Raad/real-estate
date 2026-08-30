import fs from "node:fs";
import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The build identity is baked into the bundle here because the app is served offline as static
// files behind Nginx — there is no runtime it could ask. Same repo-root VERSION file the backend
// reads, so the two halves cannot claim different builds. Environment wins over the file: a
// production image is built without the repo around it.
function readVersionFile(): Record<string, string> {
  try {
    const text = fs.readFileSync(path.resolve(__dirname, "../VERSION"), "utf8");
    return Object.fromEntries(
      text
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line && !line.startsWith("#") && line.includes("="))
        .map((line) => {
          const at = line.indexOf("=");
          return [line.slice(0, at).trim(), line.slice(at + 1).trim()];
        }),
    );
  } catch {
    return {};
  }
}

const versionFile = readVersionFile();
const appVersion = process.env.APP_VERSION || versionFile.APP_VERSION || "0.0.0";
const parsedBuild = Number.parseInt(process.env.APP_BUILD ?? versionFile.APP_BUILD ?? "", 10);
// An unreadable build degrades to 0 rather than breaking the build — the same contract as the
// backend's version.py, so "0.0.0 (build 0)" means the same thing on both sides.
const appBuild = Number.isFinite(parsedBuild) ? parsedBuild : 0;

// Dev server proxies /api to Django so the browser talks to one origin (no CORS in dev).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
    __APP_BUILD__: JSON.stringify(appBuild),
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test/setup.ts"],
  },
});
