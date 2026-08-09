import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";

import { UNKNOWN_BUILD, buildStamp, formatBuild } from "@/lib/build";
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
  if (!data || data.build === UNKNOWN_BUILD || __APP_BUILD__ === UNKNOWN_BUILD) return null;
  if (data.build === __APP_BUILD__) return null;

  return (
    <div
      role="alert"
      className="flex items-start gap-3 border-b border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive md:px-8"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <div className="space-y-1">
        <p>{t("app.versionMismatch")}</p>
        {/* Both sides go through the same formatter — this is the one screen where they are read
            side by side, so presenting them differently would be its own confusion. */}
        <p dir="ltr" className="font-mono text-xs opacity-80">
          {`app ${buildStamp} · server ${formatBuild(data.app_version, data.build)}`}
        </p>
      </div>
    </div>
  );
}
