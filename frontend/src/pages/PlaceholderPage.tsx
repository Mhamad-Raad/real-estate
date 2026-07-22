import { useTranslation } from "react-i18next";

import { Card, CardContent } from "@/components/ui/card";

// Stand-in for routes whose features land in later iterations (keeps nav honest + localized).
export function PlaceholderPage({ titleKey }: { titleKey: string }) {
  const { t } = useTranslation();
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">{t(titleKey)}</h1>
      <Card>
        <CardContent className="flex h-40 items-center justify-center text-muted-foreground">
          {t("dashboard.comingSoon")}
        </CardContent>
      </Card>
    </div>
  );
}
