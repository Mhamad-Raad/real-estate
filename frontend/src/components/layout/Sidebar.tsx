import {
  LayoutDashboard,
  Users,
  FolderKanban,
  UserCog,
  FileBarChart,
  ScrollText,
  Settings,
  Tags,
  Landmark,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

import { useAppSelector } from "@/app/hooks";
import { cn } from "@/lib/utils";

interface NavItem {
  to: string;
  labelKey: string;
  icon: LucideIcon;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { to: "/clients", labelKey: "nav.clients", icon: Users },
  { to: "/processes", labelKey: "nav.processes", icon: FolderKanban },
  { to: "/reports", labelKey: "nav.reports", icon: FileBarChart, adminOnly: true },
  { to: "/activities", labelKey: "nav.activities", icon: ScrollText, adminOnly: true },
  { to: "/categories", labelKey: "nav.categories", icon: Tags, adminOnly: true },
  { to: "/users", labelKey: "nav.users", icon: UserCog, adminOnly: true },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
];

export function Sidebar() {
  const { t } = useTranslation();
  const isAdmin = useAppSelector((s) => s.auth.user?.is_admin ?? false);

  return (
    <aside className="hidden w-64 shrink-0 border-e border-sidebar-border bg-sidebar md:flex md:flex-col">
      <div className="flex h-16 items-center gap-2 px-5">
        <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Landmark className="size-5" />
        </span>
        <span className="text-base font-semibold">{t("app.name")}</span>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-2">
        {NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )
            }
          >
            <item.icon className="size-4 shrink-0" />
            <span>{t(item.labelKey)}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
