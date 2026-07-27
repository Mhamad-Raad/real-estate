import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Dialog, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { apiErrorMessage } from "@/lib/apiError";

import { useUploadTemplateMutation } from "./templatesApi";
import type { TemplateType } from "./types";

const TYPES: TemplateType[] = ["eligibility_single", "process_list"];

// Upload a Word template. The new file becomes the active one for its type, so the office can
// change a letter's wording, signatory or CC list without a developer (§6.6).
export function TemplateUploadDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const [upload, { isLoading }] = useUploadTemplateMutation();
  const [templateType, setTemplateType] = useState<TemplateType>("eligibility_single");
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    if (open) {
      setTemplateType("eligibility_single");
      setName("");
      setFile(null);
    }
  }, [open]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    try {
      await upload({ template_type: templateType, name, file }).unwrap();
      toast.success(t("common.saved"));
      onClose();
    } catch (err) {
      toast.error(apiErrorMessage(err, t("common.saveError")));
    }
  };

  return (
    <Dialog open={open} onClose={onClose} title={t("templates.upload")}>
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="tpl-type">{t("templates.type")}</Label>
          <Select
            id="tpl-type"
            value={templateType}
            onChange={(e) => setTemplateType(e.target.value as TemplateType)}
          >
            {TYPES.map((type) => (
              <option key={type} value={type}>
                {t(`templates.types.${type}`)}
              </option>
            ))}
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="tpl-name">{t("templates.name")}</Label>
          <Input id="tpl-name" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>

        <div className="space-y-2">
          <Label htmlFor="tpl-file">{t("templates.file")}</Label>
          <Input
            id="tpl-file"
            type="file"
            accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            required
          />
          <p className="text-xs text-muted-foreground">{t("templates.fileHint")}</p>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose} disabled={isLoading}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" disabled={isLoading || !file}>
            {isLoading && <Spinner />}
            {t("common.save")}
          </Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
