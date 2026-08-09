import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useGetHealthQuery } from "./systemApi";

/**
 * Warns when this bundle and the server were built from different versions.
 *
 * The office updates by copying images onto one computer at a time, so half an update — a new
 * frontend against an old backend — is a real outcome, and every symptom of it looks like an
 * app bug instead of an install problem.
 */
export function VersionMismatchBanner() {
  const { t } = useTranslation();
  const { data } = useGetHealthQuery();

  // Build 0 is the "unknown" marker on both sides (no VERSION file, or a folder-copy build).
  // Comparing against it would fire on every developer machine, so only real builds are judged.
  if (!data || data.build === 0 || __APP_BUILD__ === 0) return null;
  if (data.build === __APP_BUILD__) return null;

  return (
    <div
      role="alert"
      className="flex items-start gap-3 border-b border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive md:px-8"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <div className="space-y-1">
        <p>{t("app.versionMismatch")}</p>
        {/* Latin and LTR: these are the two numbers the office reads back during a support call. */}
        <p dir="ltr" className="font-mono text-xs opacity-80">
          {`app ${__APP_VERSION__} (build ${__APP_BUILD__}) · server ${data.app_version} (build ${data.build})`}
        </p>
      </div>
    </div>
  );
}
