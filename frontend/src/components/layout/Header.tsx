import { LogOut, User as UserIcon } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "@/components/ui/toaster";
import { useLogoutMutation } from "@/features/auth/authApi";
import { logOut } from "@/features/auth/authSlice";

import { LanguageSwitcher } from "./LanguageSwitcher";
import { ThemeToggle } from "./ThemeToggle";

export function Header() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const user = useAppSelector((s) => s.auth.user);
  const refresh = useAppSelector((s) => s.auth.refresh);
  const [logout] = useLogoutMutation();

  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.username || "";

  const onLogout = async () => {
    if (refresh) {
      // Best-effort server-side blacklist; local sign-out proceeds regardless.
      await logout({ refresh })
        .unwrap()
        .catch(() => toast.warning(t("header.logoutServerWarning")));
    }
    dispatch(logOut());
    navigate("/login", { replace: true });
  };

  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-background px-4 md:px-6">
      <div className="text-sm text-muted-foreground">
        {user && t(`role.${user.role}`)}
      </div>
      <div className="flex items-center gap-1">
        <LanguageSwitcher />
        <ThemeToggle />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" aria-label={t("header.account")}>
              <UserIcon />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel className="truncate">{displayName}</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={onLogout} className="text-destructive">
              <LogOut className="size-4" />
              <span>{t("header.logout")}</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
