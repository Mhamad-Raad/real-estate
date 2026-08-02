import {
  FileType,
  LayoutDashboard,
  Users,
  FolderKanban,
  UserCog,
  FileBarChart,
  ScrollText,
  Settings,
  Tags,
  Landmark,
  PanelLeftClose,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { toggleSidebar } from "@/features/ui/uiSlice";
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
  // No standalone scan entry: a card is scanned inside the Step-1 intake form, so exactly one
  // path opens a case (§5, UC-024).
  { to: "/processes", labelKey: "nav.processes", icon: FolderKanban },
  { to: "/reports", labelKey: "nav.reports", icon: FileBarChart, adminOnly: true },
  { to: "/activities", labelKey: "nav.activities", icon: ScrollText, adminOnly: true },
  { to: "/categories", labelKey: "nav.categories", icon: Tags, adminOnly: true },
  { to: "/templates", labelKey: "nav.templates", icon: FileType, adminOnly: true },
  { to: "/users", labelKey: "nav.users", icon: UserCog, adminOnly: true },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
];

export function Sidebar() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const isAdmin = useAppSelector((s) => s.auth.user?.is_admin ?? false);
  const collapsed = useAppSelector((s) => s.ui.sidebarCollapsed);

  return (
    <aside
      className={cn(
        "hidden shrink-0 border-e border-sidebar-border bg-sidebar transition-[width] md:flex md:flex-col",
        collapsed ? "w-16" : "w-64",
      )}
    >
      <div className={cn("flex h-16 items-center gap-2", collapsed ? "justify-center px-2" : "px-5")}>
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Landmark className="size-5" />
        </span>
        {!collapsed && <span className="truncate text-base font-semibold">{t("app.name")}</span>}
      </div>
      <nav className="flex-1 space-y-1 px-3 py-2">
        {NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            // Collapsed, the label leaves the screen but must stay for a screen reader — and as a
            // native tooltip for anyone who does not recognise the icon.
            title={collapsed ? t(item.labelKey) : undefined}
            aria-label={collapsed ? t(item.labelKey) : undefined}
            className={({ isActive }) =>
              cn(
                "flex items-center rounded-md py-2 text-sm font-medium transition-colors",
                collapsed ? "justify-center px-2" : "gap-3 px-3",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )
            }
          >
            <item.icon className="size-4 shrink-0" />
            {!collapsed && <span className="truncate">{t(item.labelKey)}</span>}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-sidebar-border p-2">
        <button
          type="button"
          onClick={() => dispatch(toggleSidebar())}
          title={t(collapsed ? "nav.expand" : "nav.collapse")}
          aria-label={t(collapsed ? "nav.expand" : "nav.collapse")}
          className={cn(
            "flex w-full items-center rounded-md py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
            collapsed ? "justify-center px-2" : "gap-3 px-3",
          )}
        >
          {/* Points at the edge it collapses toward; `rtl:rotate-180` flips that with the layout. */}
          <PanelLeftClose
            className={cn("size-4 shrink-0 rtl:rotate-180", collapsed && "rotate-180 rtl:rotate-0")}
          />
          {!collapsed && <span>{t("nav.collapse")}</span>}
        </button>
      </div>
    </aside>
  );
}
