// A card side, held as a File so the camera and the file picker produce the same thing and the
// upload code never has to know which one it came from.
export type CardSide = { file: File; url: string };

/** Swap a side for another, revoking the old preview URL so previews cannot leak. */
export function replaceSide(current: CardSide | null, file: File | null): CardSide | null {
  if (current) URL.revokeObjectURL(current.url);
  return file ? { file, url: URL.createObjectURL(file) } : null;
}
