import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { LoginPage } from "@/features/auth/LoginPage";
import { ProtectedRoute } from "@/features/auth/ProtectedRoute";
import { DashboardPage } from "@/pages/DashboardPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="clients" element={<PlaceholderPage titleKey="nav.clients" />} />
          <Route path="processes" element={<PlaceholderPage titleKey="nav.processes" />} />
          <Route path="reports" element={<PlaceholderPage titleKey="nav.reports" />} />
          <Route path="activities" element={<PlaceholderPage titleKey="nav.activities" />} />
          <Route path="users" element={<PlaceholderPage titleKey="nav.users" />} />
          <Route path="settings" element={<PlaceholderPage titleKey="nav.settings" />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
