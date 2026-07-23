import { Navigate, Outlet } from "react-router-dom";

import { useMeQuery } from "./authApi";

// Client-side gate for admin-only screens (the server still enforces RBAC — this is UX only).
// Reads the shared `me` cache rather than the auth slice: the slice is hydrated by ProtectedRoute
// in an effect, so on a full page load it lags one render — long enough to wrongly redirect.
export function AdminRoute() {
  const { data, isLoading } = useMeQuery();
  if (isLoading || !data) return null; // parent ProtectedRoute already shows the loading state
  return data.is_admin ? <Outlet /> : <Navigate to="/" replace />;
}
