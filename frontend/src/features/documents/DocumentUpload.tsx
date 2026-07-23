import { Upload } from "lucide-react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { apiErrorMessage } from "@/lib/apiError";

import { useUploadDocumentMutation } from "./documentsApi";

// PDF import button — scan capture is Iteration 6; here it's file import only (§6.1).
export function DocumentUpload({
  process,
  step,
  documentType,
  instituteEntry = null,
  label,
  disabled = false,
}: {
  process: number;
  step: number;
  documentType: string;
  instituteEntry?: number | null;
  label?: string;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  const [upload, { isLoading }] = useUploadDocumentMutation();
  const inputRef = useRef<HTMLInputElement>(null);

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await upload({ process, step_number: step, document_type: documentType, institute_entry: instituteEntry, file }).unwrap();
      toast.success(t("workflow.uploaded"));
    } catch (err) {
      toast.error(apiErrorMessage(err, t("workflow.uploadError")));
    } finally {
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <>
      <input ref={inputRef} type="file" accept="application/pdf" className="hidden" onChange={onFile} />
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled || isLoading}
        onClick={() => inputRef.current?.click()}
      >
        {isLoading ? <Spinner /> : <Upload className="size-4" />}
        {label ?? t("workflow.upload")}
      </Button>
    </>
  );
}
