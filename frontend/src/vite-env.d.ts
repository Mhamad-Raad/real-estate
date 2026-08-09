/// <reference types="vite/client" />

// Baked in at build time by vite.config.ts from the repo-root VERSION file. Declared here so
// both `tsc -b` and vitest see them — `define` substitutes the literals, it does not type them.
declare const __APP_VERSION__: string;
declare const __APP_BUILD__: number;
