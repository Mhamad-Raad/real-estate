import { useTranslation } from "react-i18next";

import { useAppSelector } from "@/app/hooks";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function DashboardPage() {
  const { t } = useTranslation();
  const user = useAppSelector((s) => s.auth.user);
  const name =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.username || "";

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          {t("dashboard.welcome", { name })}
        </h1>
        <p className="text-muted-foreground">{t("dashboard.subtitle")}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {["clients", "processes", "reports"].map((key) => (
          <Card key={key}>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {t(`nav.${key}`)}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Skeleton className="h-8 w-16" />
              <span className="text-xs text-muted-foreground">{t("dashboard.comingSoon")}</span>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
