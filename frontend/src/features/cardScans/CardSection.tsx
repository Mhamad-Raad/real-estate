/** One person's card: its scan beside the fields read from it, in a box of its own (UC-128). */
export function CardSection({
  title,
  aside,
  children,
}: {
  title: string;
  /** Beside the title — the spouse's reading spinner. */
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-4 rounded-md border border-border p-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-medium">{title}</h3>
        {aside}
      </div>
      <div className="grid gap-6 lg:grid-cols-2">{children}</div>
    </section>
  );
}
