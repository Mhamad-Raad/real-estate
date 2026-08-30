/**
 * The build identity, baked in at build time by vite.config.ts from the repo-root VERSION file.
 *
 * The format lives here, not in the component, so the stamp and the mismatch banner — which
 * prints this bundle's build and the server's side by side — cannot present the same thing two
 * ways. It is a plain module rather than a component export so a component file never exports a
 * non-component (the Fast Refresh rule It.8 cleared).
 */

/** The one build-string format: `0.9.0 (build 1)`. */
export const formatBuild = (version: string, build: number) => `${version} (build ${build})`;

/** This bundle's own build. The server's comes from `GET /health/`. */
export const buildStamp = formatBuild(__APP_VERSION__, __APP_BUILD__);

/** `0` is the "could not resolve" marker on both sides — never compare against it. */
export const UNKNOWN_BUILD = 0;
