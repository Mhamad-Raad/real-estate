import { useTranslation } from "react-i18next";

import { FieldError } from "@/components/ui/field-error";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useListCategoriesQuery } from "@/features/categories/categoriesApi";

import type { ClientInput, MaritalStatus } from "./types";

const MARITAL: MaritalStatus[] = ["single", "married", "divorced", "widowed"];

// The beneficiary's fields, in one place. Used by the Clients dialog and by the Step-1 intake form
// (§5, UC-024) — two screens that must ask for exactly the same things or the DB check constraint
// on a married client will reject one of them.
export function ClientFields({
  value: form,
  onChange,
  idPrefix = "c",
  showCategory = true,
  errors = {},
  onFieldEdit,
}: {
  value: ClientInput;
  onChange: (next: ClientInput) => void;
  idPrefix?: string;
  showCategory?: boolean;
  /** Per-field messages from the server, keyed by API field name (see `useFieldErrors`). */
  errors?: Record<string, string>;
  /** Called as a field is edited, so its error clears instead of staying red until the next save. */
  onFieldEdit?: (field: string) => void;
}) {
  const { t } = useTranslation();
  const { data: categories } = useListCategoriesQuery(undefined, { skip: !showCategory });

  const set = (key: keyof ClientInput) => (e: { target: { value: string } }) => {
    onFieldEdit?.(key);
    onChange({ ...form, [key]: e.target.value });
  };
  const id = (suffix: string) => `${idPrefix}-${suffix}`;
  // Everything a field needs to show itself as rejected: red border, the reason, and the link
  // between them for a screen reader.
  const bad = (key: keyof ClientInput) => ({
    invalid: Boolean(errors[key]),
    "aria-describedby": errors[key] ? id(`${key}-error`) : undefined,
  });
  const err = (key: keyof ClientInput) => (
    <FieldError id={id(`${key}-error`)} message={errors[key]} />
  );

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="space-y-2">
        <Label htmlFor={id("name")}>{t("clients.fullName")}</Label>
        <Input id={id("name")} value={form.full_name} onChange={set("full_name")} required {...bad("full_name")} />
        {err("full_name")}
      </div>
      <div className="space-y-2">
        <Label htmlFor={id("pid")}>{t("clients.pid")}</Label>
        <Input id={id("pid")} dir="ltr" className="text-start" value={form.pid} onChange={set("pid")} required {...bad("pid")} />
        {err("pid")}
      </div>
      <div className="space-y-2">
        <Label htmlFor={id("mother")}>{t("clients.motherName")}</Label>
        <Input id={id("mother")} value={form.mother_full_name} onChange={set("mother_full_name")} required {...bad("mother_full_name")} />
        {err("mother_full_name")}
      </div>
      <div className="space-y-2">
        <Label htmlFor={id("marital")}>{t("clients.maritalStatus")}</Label>
        <Select
          id={id("marital")}
          value={form.marital_status}
          onChange={set("marital_status")}
          invalid={Boolean(errors.marital_status)}
        >
          {MARITAL.map((m) => (
            <option key={m} value={m}>
              {t(`clients.marital.${m}`)}
            </option>
          ))}
        </Select>
        {err("marital_status")}
      </div>
      {/* The generated letter prints a spouse row of name / birth date / mother's name,
          so a married client needs all three (§6.6). */}
      {form.marital_status === "married" && (
        <>
          <div className="space-y-2">
            <Label htmlFor={id("spouse")}>{t("clients.spouseName")}</Label>
            <Input id={id("spouse")} value={form.spouse_name} onChange={set("spouse_name")} required {...bad("spouse_name")} />
            {err("spouse_name")}
          </div>
          <div className="space-y-2">
            <Label htmlFor={id("spouse-dob")}>{t("clients.spouseDateOfBirth")}</Label>
            <Input
              id={id("spouse-dob")}
              type="date"
              value={form.spouse_date_of_birth ?? ""}
              onChange={set("spouse_date_of_birth")}
              required
              {...bad("spouse_date_of_birth")}
            />
            {err("spouse_date_of_birth")}
          </div>
          <div className="space-y-2">
            <Label htmlFor={id("spouse-mother")}>{t("clients.spouseMotherName")}</Label>
            <Input
              id={id("spouse-mother")}
              value={form.spouse_mother_full_name}
              onChange={set("spouse_mother_full_name")}
              required
              {...bad("spouse_mother_full_name")}
            />
            {err("spouse_mother_full_name")}
          </div>
          {/* Not printed on any letter — this is the household dedup key (§5.7), so a
              couple entered by hand is covered by the same rule as a scanned one. */}
          <div className="space-y-2">
            <Label htmlFor={id("spouse-pid")}>{t("clients.spousePid")}</Label>
            <Input
              id={id("spouse-pid")}
              dir="ltr"
              className="text-start"
              value={form.spouse_pid}
              onChange={set("spouse_pid")}
              {...bad("spouse_pid")}
            />
            {err("spouse_pid")}
            <p className="text-xs text-muted-foreground">{t("clients.spousePidHint")}</p>
          </div>
        </>
      )}
      <div className="space-y-2">
        <Label htmlFor={id("dob")}>{t("clients.dateOfBirth")}</Label>
        <Input
          id={id("dob")}
          type="date"
          value={form.date_of_birth ?? ""}
          onChange={set("date_of_birth")}
          required
          {...bad("date_of_birth")}
        />
        {err("date_of_birth")}
      </div>
      <div className="space-y-2">
        <Label htmlFor={id("pob")}>{t("clients.placeOfBirth")}</Label>
        <Input id={id("pob")} value={form.place_of_birth} onChange={set("place_of_birth")} {...bad("place_of_birth")} />
        {err("place_of_birth")}
      </div>
      <div className="space-y-2">
        <Label htmlFor={id("phone")}>{t("clients.phone")}</Label>
        {/* `tel` + LTR: a phone is dialled left-to-right whatever the page direction, and the
            input mode brings up a numeric keypad rather than a full keyboard. */}
        <Input
          id={id("phone")}
          type="tel"
          inputMode="tel"
          dir="ltr"
          className="text-start"
          value={form.phone}
          onChange={set("phone")}
          {...bad("phone")}
        />
        {err("phone")}
      </div>
      <div className="space-y-2 sm:col-span-2">
        <Label htmlFor={id("address")}>{t("clients.address")}</Label>
        <Input id={id("address")} value={form.address} onChange={set("address")} {...bad("address")} />
        {err("address")}
      </div>
      {/* Hidden on the intake form, where the case's own category is asked once and copied here. */}
      {showCategory && (
        <div className="space-y-2">
          <Label htmlFor={id("category")}>{t("clients.category")}</Label>
          <Select
            id={id("category")}
            value={form.category ?? ""}
            onChange={(e) => {
              onFieldEdit?.("category");
              onChange({ ...form, category: e.target.value ? Number(e.target.value) : null });
            }}
            invalid={Boolean(errors.category)}
          >
            <option value="">{t("common.none")}</option>
            {(categories ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} — {c.name}
              </option>
            ))}
          </Select>
          {err("category")}
        </div>
      )}
    </div>
  );
}
