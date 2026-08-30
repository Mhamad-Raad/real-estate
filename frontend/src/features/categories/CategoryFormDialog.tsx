import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/lib/toast";
import { apiErrorMessage } from "@/lib/apiError";
import { labeller } from "@/lib/fieldLabels";
import { useFieldErrors } from "@/hooks/useFieldErrors";
import { FieldError } from "@/components/ui/field-error";

import { useCreateCategoryMutation, useUpdateCategoryMutation } from "./categoriesApi";
import type { Category } from "./types";

// Create/edit a category. `category` present → edit mode (sends the version for the optimistic lock).
export function CategoryFormDialog({
  open,
  category,
  onClose,
}: {
  open: boolean;
  category: Category | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [create, { isLoading: creating }] = useCreateCategoryMutation();
  const [update, { isLoading: updating }] = useUpdateCategoryMutation();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const { errors, setFromError, clear } = useFieldErrors();

  useEffect(() => {
    if (open) {
      setCode(category?.code ?? "");
      setName(category?.name ?? "");
    }
  }, [open, category]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (category) {
        await update({ id: category.id, version: category.version, code, name }).unwrap();
      } else {
        await create({ code, name }).unwrap();
      }
      toast.success(t("common.saved"));
      onClose();
    } catch (err) {
      setFromError(err);
      toast.error(apiErrorMessage(err, t("common.saveError"), labeller(t), t));
    }
  };

  const busy = creating || updating;
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={category ? t("categories.edit") : t("categories.add")}
    >
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="cat-code">{t("categories.code")}</Label>
          <Input
            id="cat-code"
            value={code}
            onChange={(e) => {
              clear("code");
              setCode(e.target.value);
            }}
            required
            autoFocus
            invalid={Boolean(errors.code)}
            aria-describedby={errors.code ? "cat-code-error" : undefined}
          />
          <FieldError id="cat-code-error" message={errors.code} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="cat-name">{t("categories.name")}</Label>
          <Input
            id="cat-name"
            value={name}
            onChange={(e) => {
              clear("name");
              setName(e.target.value);
            }}
            required
            invalid={Boolean(errors.name)}
            aria-describedby={errors.name ? "cat-name-error" : undefined}
          />
          <FieldError id="cat-name-error" message={errors.name} />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" disabled={busy}>
            {busy && <Spinner />}
            {t("common.save")}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
