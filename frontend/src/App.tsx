import { Navigate, Route, Routes } from "react-router-dom";

import { Toaster } from "@/components/ui/toaster";
import { AppLayout } from "@/components/layout/AppLayout";
import { ActivitiesPage } from "@/features/activities/ActivitiesPage";
import { AdminRoute } from "@/features/auth/AdminRoute";
import { LoginPage } from "@/features/auth/LoginPage";
import { ProtectedRoute } from "@/features/auth/ProtectedRoute";
import { CategoriesPage } from "@/features/categories/CategoriesPage";
import { TemplatesPage } from "@/features/templates/TemplatesPage";
import { ClientsPage } from "@/features/clients/ClientsPage";
import { ProcessCreatePage } from "@/features/processes/ProcessCreatePage";
import { ProcessesPage } from "@/features/processes/ProcessesPage";
import { ReportsPage } from "@/features/reports/ReportsPage";
import { ProcessDetailPage } from "@/features/processes/detail/ProcessDetailPage";
import { UsersPage } from "@/features/users/UsersPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { NotFoundPage } from "@/pages/NotFoundPage";

export default function App() {
  return (
    <>
      <Toaster />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="clients" element={<ClientsPage />} />
            <Route path="processes" element={<ProcessesPage />} />
            {/* Before `:id`, or "new" would be parsed as a process id. */}
            <Route path="processes/new" element={<ProcessCreatePage />} />
            <Route path="processes/:id" element={<ProcessDetailPage />} />
            {/* Admin-only management screens (server enforces RBAC too). */}
            <Route element={<AdminRoute />}>
              <Route path="reports" element={<ReportsPage />} />
              <Route path="activities" element={<ActivitiesPage />} />
              <Route path="categories" element={<CategoriesPage />} />
              <Route path="templates" element={<TemplatesPage />} />
              <Route path="users" element={<UsersPage />} />
            </Route>
            <Route path="settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </>
  );
}
