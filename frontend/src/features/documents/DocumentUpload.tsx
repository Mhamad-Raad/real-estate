import { Upload } from "lucide-react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/lib/toast";
import { apiErrorMessage } from "@/lib/apiError";

import { useUploadDocumentMutation } from "./documentsApi";
import { ScanDocumentDialog } from "./ScanDocumentDialog";

/** The two ways paper reaches a document slot (§6.1): import a ready-made PDF, or scan it.
 *
 * Both end at the same `POST /documents/` upload and produce the same kind of row — scanning
 * differs only in that the browser builds the PDF first, and the row records `scanned`. An
 * office that already has a PDF never has to go near the camera. */
export function DocumentUpload({
  process,
  step,
  documentType,
  instituteEntry = null,
  label,
  disabled = false,
  disabledReason,
}: {
  process: number;
  step: number;
  documentType: string;
  instituteEntry?: number | null;
  label?: string;
  disabled?: boolean;
  /** Why both controls are greyed out — a full slot looks like a fault without it. */
  disabledReason?: string;
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
      // `t` last: the server answers a refused upload with an i18n key, not an English sentence.
      toast.error(apiErrorMessage(err, t("workflow.uploadError"), undefined, t));
    } finally {
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div
      className="flex flex-wrap items-center gap-2"
      title={disabled ? disabledReason : undefined}
    >
      {/* The formats the server actually takes: a PDF as-is, or a scanner/camera image it converts
          on arrival (`documents.filestore.IMAGE_MAGIC`). It offered PDF alone, so the office could
          not pick the JPEG or TIFF their scanner produces even though the API accepts it (UC-087).
          Kept in step with that list — a format offered here and refused there is a dead end. */}
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,image/jpeg,image/png,image/tiff"
        className="hidden"
        onChange={onFile}
      />
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
      <ScanDocumentDialog
        process={process}
        step={step}
        documentType={documentType}
        instituteEntry={instituteEntry}
        disabled={disabled || isLoading}
      />
    </div>
  );
}
