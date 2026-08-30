import { useTranslation } from "react-i18next";

import { Dialog } from "@/components/ui/dialog";
import { formatDate } from "@/lib/format";

import type { Activity } from "./types";

/** Union of the keys on both sides, so a field that only appears in one still shows. */
function changedKeys(activity: Activity): string[] {
  return [...new Set([...Object.keys(activity.before ?? {}), ...Object.keys(activity.after ?? {})])];
}

function render(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

export function ActivityDetailDialog({
  activity,
  onClose,
}: {
  activity: Activity | null;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  if (!activity) return null;

  const keys = changedKeys(activity);

  return (
    <Dialog
      open
      onClose={onClose}
      title={`${t(`activities.action.${activity.action}`)} · ${activity.entity_type}`}
    >
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <dt className="text-muted-foreground">{t("activities.actor")}</dt>
        <dd>{activity.actor_username || t("activities.systemActor")}</dd>
        <dt className="text-muted-foreground">{t("activities.when")}</dt>
        <dd>
          {formatDate(activity.created_at, i18n.language, {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </dd>
        <dt className="text-muted-foreground">{t("activities.entity")}</dt>
        <dd>
          {activity.entity_type}
          {activity.entity_id && ` #${activity.entity_id}`}
        </dd>
        {activity.ip_address && (
          <>
            <dt className="text-muted-foreground">{t("activities.ip")}</dt>
            {/* dir=ltr: an IPv4 address scrambles if the surrounding page is RTL. */}
            <dd dir="ltr" className="text-start">
              {activity.ip_address}
            </dd>
          </>
        )}
      </dl>

      <div className="mt-4 space-y-2">
        <h3 className="text-sm font-medium">{t("activities.changes")}</h3>
        {!keys.length ? (
          <p className="text-sm text-muted-foreground">{t("activities.noFieldData")}</p>
        ) : (
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-3 py-2 text-start font-medium">{t("activities.field")}</th>
                  <th className="px-3 py-2 text-start font-medium">{t("activities.before")}</th>
                  <th className="px-3 py-2 text-start font-medium">{t("activities.after")}</th>
                </tr>
              </thead>
              <tbody>
                {keys.map((key) => (
                  <tr key={key} className="border-t border-border">
                    <td className="px-3 py-2 font-medium">{key}</td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {render(activity.before?.[key])}
                    </td>
                    <td className="px-3 py-2">{render(activity.after?.[key])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Dialog>
  );
}
