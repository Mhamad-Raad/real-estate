import { ArrowLeft } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DateField } from "@/components/ui/date-field";
import { FieldError } from "@/components/ui/field-error";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { FormSection } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";
import { useDuplicateGate } from "@/features/clients/useDuplicateGate";
import { useFieldErrors } from "@/hooks/useFieldErrors";
import { apiErrorMessage } from "@/lib/apiError";
import { labeller } from "@/lib/fieldLabels";
import { filterPid } from "@/lib/pid";
import { toast } from "@/lib/toast";

import { useFastEntryProcessMutation } from "./processesApi";

// TIFF is accepted by the API but no browser renders it inline, so it gets the named fallback.
const canPreview = (file: File) =>
  file.type === "application/pdf" || (file.type.startsWith("image/") && file.type !== "image/tiff");

// One picked file, sizes from a few hundred KB to ~80 MB — two units cover the real range.
const formatSize = (bytes: number) =>
  bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;

const EMPTY = {
  full_name: "",
  pid: "",
  mother_full_name: "",
  date_of_birth: "",
  category: "",
  land_id: "",
};

/**
 * The backlog door (UC-114) — **temporary by design; delete this screen when the backlog is in.**
 *
 * The office has thousands of finished allocations that exist only on paper, and no intention of
 * re-keying five steps of each. So this asks for the part that has to be **findable** — the
 * beneficiary, their national ID, the land number, the category — and takes **one PDF**: the case
 * file, which is the same document step 5 compiles for a case worked here.
 *
 * Everything else is left empty on purpose, and the case is badged as fast entry so its empty
 * steps read as history rather than as work nobody finished.
 *
 * The duplicate rules are **not** relaxed here (the office's call): a national ID already on file
 * is refused exactly as it is on the intake form.
 */
export function FastEntryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [form, setForm] = useState(EMPTY);
  const [markComplete, setMarkComplete] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  // The picked file shown back before saving — on a desk of look-alike paper files, filing a
  // backlog case under the wrong PDF is exactly the mistake this screen invites.
  const [preview, setPreview] = useState<string | null>(null);
  const { errors, setFromError, clear, clearAll } = useFieldErrors();

  const pickFile = (chosen: File | null) => {
    clear("file");
    // Revoked outside the state updater — React may run an updater twice, so it must stay pure.
    if (preview) URL.revokeObjectURL(preview);
    setFile(chosen);
    setPreview(chosen && canPreview(chosen) ? URL.createObjectURL(chosen) : null);
  };

  // Navigating away also ends the form; the ref lets the cleanup see the URL that exists then.
  const livePreview = useRef<string | null>(null);
  livePreview.current = preview;
  useEffect(() => () => {
    if (livePreview.current) URL.revokeObjectURL(livePreview.current);
  }, []);

  const { data: categories } = useListCategoriesQuery();
  const [fastEntry, { isLoading }] = useFastEntryProcessMutation();
  // The **same** gate the intake form uses (§5.7). The server refuses a hard duplicate at this
  // door either way, but a similar mother's name is advisory and never reaches an error — and on
  // a backlog case it would otherwise surface only inside Step 1, which nobody will ever open.
  const { guard, dialog: duplicateDialog } = useDuplicateGate();

  const set = (key: keyof typeof form) => (value: string) => {
    clear(key);
    setForm((current) => ({ ...current, [key]: value }));
  };
  const bad = (key: keyof typeof form) => ({
    invalid: Boolean(errors[key]),
    "aria-describedby": errors[key] ? `fe-${key}-error` : undefined,
  });
  const err = (key: string) => <FieldError id={`fe-${key}-error`} message={errors[key]} />;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file) return toast.error(t("fastEntry.fileRequired"));
    if (!(await guard({ pid: form.pid, mother_full_name: form.mother_full_name }))) return;
    try {
      const created = await fastEntry({
        ...form,
        mark_complete: markComplete,
        file,
      }).unwrap();
      clearAll();
      toast.success(t("fastEntry.created", { code: created.unique_code }));
      // Back to the list (the office's call, 2026-08-30). It costs a click per case against
      // staying on an emptied form, and buys the thing the office wanted instead: the case they
      // just typed, visible in the list with its code, before they start the next one.
      navigate("/processes");
    } catch (error) {
      setFromError(error);
      toast.error(apiErrorMessage(error, t("common.saveError"), labeller(t), t));
    }
  };

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-6 p-4">
      <div className="space-y-2">
        <Button type="button" variant="outline" size="sm" onClick={() => navigate("/processes")}>
          <ArrowLeft className="size-4 rtl:rotate-180" />
          {t("workflow.backToList")}
        </Button>
        <h1 className="text-2xl font-semibold">{t("fastEntry.heading")}</h1>
        <p className="text-sm text-muted-foreground">{t("fastEntry.subtitle")}</p>
      </div>

      <FormSection title={t("fastEntry.beneficiary")}>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="fe-name">{t("clients.fullName")}</Label>
            <Input
              id="fe-name"
              value={form.full_name}
              onChange={(e) => set("full_name")(e.target.value)}
              required
              {...bad("full_name")}
            />
            {err("full_name")}
          </div>
          <div className="space-y-2">
            <Label htmlFor="fe-pid">{t("clients.pid")}</Label>
            {/* Filtered as it is typed, like every other ID box: digits only, Arabic-Indic
                folded. `validate_pid` on the server is still the boundary (§4.1). */}
            <Input
              id="fe-pid"
              dir="ltr"
              inputMode="numeric"
              className="text-start"
              value={form.pid}
              onChange={(e) => set("pid")(filterPid(e.target.value))}
              required
              {...bad("pid")}
            />
            {err("pid")}
          </div>
          <div className="space-y-2">
            <Label htmlFor="fe-mother">{t("clients.motherName")}</Label>
            <Input
              id="fe-mother"
              value={form.mother_full_name}
              onChange={(e) => set("mother_full_name")(e.target.value)}
              required
              {...bad("mother_full_name")}
            />
            {err("mother_full_name")}
          </div>
          <div className="space-y-2">
            <Label htmlFor="fe-dob">{t("clients.dateOfBirth")}</Label>
            <DateField
              id="fe-dob"
              value={form.date_of_birth}
              onChange={set("date_of_birth")}
              required
              {...bad("date_of_birth")}
            />
            {err("date_of_birth")}
          </div>
        </div>
      </FormSection>

      <FormSection title={t("fastEntry.theCase")}>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="fe-category">{t("processes.category")}</Label>
            {/* Required here, unlike an ordinary case: the code takes its letter from the
                category and can never be issued afterwards (UC-056, UC-059). */}
            <Select
              id="fe-category"
              value={form.category}
              onChange={(e) => set("category")(e.target.value)}
              required
              {...bad("category")}
            >
              <option value="">{t("processes.chooseCategory")}</option>
              {(categories ?? []).map((category) => (
                <option key={category.id} value={category.id}>
                  {category.code} — {category.name}
                </option>
              ))}
            </Select>
            {err("category")}
          </div>
          <div className="space-y-2">
            <Label htmlFor="fe-land">{t("workflow.landId")}</Label>
            <Input
              id="fe-land"
              value={form.land_id}
              onChange={(e) => set("land_id")(e.target.value)}
              {...bad("land_id")}
            />
            {err("land_id")}
          </div>
        </div>
        {/* A row of its own rather than a stray line: it is a decision about the case, and it sits
            with the rest of the case. `items-center` keeps the box on the text's centre line in
            all three languages, where the label is one line in each. */}
        <label className="flex cursor-pointer items-center gap-2.5 rounded-md border border-border bg-muted/40 px-3 py-2.5 text-sm">
          <Checkbox checked={markComplete} onChange={(e) => setMarkComplete(e.target.checked)} />
          <span>{t("fastEntry.markComplete")}</span>
        </label>
      </FormSection>

      <FormSection title={t("fastEntry.theFile")}>
        <div className="space-y-2">
          <Label htmlFor="fe-file">{t("fastEntry.caseFile")}</Label>
          <Input
            id="fe-file"
            type="file"
            accept="application/pdf,image/*"
            onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
            // Guarded in `submit` instead of with `required`: a native validation bubble is
            // rendered by the browser in the **browser's** language, which is the same reason
            // dates stopped being native inputs (UC-108). The office reads Sorani.
            invalid={Boolean(errors.file)}
          />
          <p className="text-xs text-muted-foreground">{t("fastEntry.caseFileHint")}</p>
          {err("file")}
          {file && (
            <div className="space-y-2 pt-1">
              {/* <bdi> keeps the Latin filename and size from scrambling the RTL line around them. */}
              <p className="text-xs text-muted-foreground">
                {t("workflow.preview")} — <bdi>{file.name}</bdi> (<bdi>{formatSize(file.size)}</bdi>)
              </p>
              {preview ? (
                file.type === "application/pdf" ? (
                  <iframe
                    src={preview}
                    title={file.name}
                    className="h-[28rem] w-full rounded-md border border-border bg-white"
                  />
                ) : (
                  <img
                    src={preview}
                    alt={file.name}
                    className="max-h-[28rem] rounded-md border border-border"
                  />
                )
              ) : (
                <p className="rounded-md border border-border bg-muted/40 px-3 py-2.5 text-sm text-muted-foreground">
                  {t("fastEntry.noPreview")}
                </p>
              )}
            </div>
          )}
        </div>
      </FormSection>

      <Button type="submit" disabled={isLoading} className="w-full sm:w-auto">
        {isLoading && <Spinner className="size-4" />}
        {t("common.save")}
      </Button>
      {duplicateDialog}
    </form>
  );
}
