import { useTranslation } from "react-i18next";
import { Navigate, Outlet } from "react-router-dom";

import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { Spinner } from "@/components/ui/spinner";
import { useMeQuery } from "./authApi";
import { logOut, setUser } from "./authSlice";
import { useEffect } from "react";

// Gate for authenticated routes: requires a token, then hydrates the user profile.
export function ProtectedRoute() {
  const { t } = useTranslation();
  const dispatch = useAppDispatch();
  const hasToken = useAppSelector((s) => Boolean(s.auth.access));

  const { data, isError, isLoading } = useMeQuery(undefined, { skip: !hasToken });

  useEffect(() => {
    if (data) dispatch(setUser(data));
  }, [data, dispatch]);

  if (!hasToken) return <Navigate to="/login" replace />;

  if (isError) {
    dispatch(logOut());
    return <Navigate to="/login" replace />;
  }

  if (isLoading || !data) {
    return (
      <div className="flex h-screen items-center justify-center gap-2 text-muted-foreground">
        <Spinner />
        <span>{t("common.loading")}</span>
      </div>
    );
  }

  return <Outlet />;
}
