/** The message under an input that the server (or a client-side check) rejected.
 *
 * Renders nothing when there is no error, so a form can place one under every field
 * unconditionally and the layout only grows where something is actually wrong.
 *
 * `role="alert"` so the reason is announced, not just coloured — the red border alone says
 * *which* field, never *why*.
 */
export function FieldError({ message, id }: { message?: string; id?: string }) {
  if (!message) return null;
  return (
    <p id={id} role="alert" className="text-xs text-destructive">
      {message}
    </p>
  );
}
