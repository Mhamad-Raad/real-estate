import type { DocumentMeta } from "./types";

/**
 * The documents a generated-output panel owns, newest first.
 *
 * Superseding leaves exactly one live file, but the API payload has no guaranteed order, so the
 * "newest" shown inline must be chosen explicitly rather than taken from position 0.
 */
export function newestFirst(documents: DocumentMeta[], keep: (doc: DocumentMeta) => boolean) {
  return documents
    .filter(keep)
    .slice()
    .sort((a, b) => b.id - a.id);
}
