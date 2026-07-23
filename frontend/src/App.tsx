import { Navigate, Route, Routes } from "react-router-dom";

import { Toaster } from "@/components/ui/toaster";
import { AppLayout } from "@/components/layout/AppLayout";
import { AdminRoute } from "@/features/auth/AdminRoute";
import { LoginPage } from "@/features/auth/LoginPage";
import { ProtectedRoute } from "@/features/auth/ProtectedRoute";
import { CategoriesPage } from "@/features/categories/CategoriesPage";
import { ClientsPage } from "@/features/clients/ClientsPage";
import { ProcessesPage } from "@/features/processes/ProcessesPage";
import { ProcessDetailPage } from "@/features/processes/detail/ProcessDetailPage";
import { UsersPage } from "@/features/users/UsersPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";

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
            <Route path="processes/:id" element={<ProcessDetailPage />} />
            <Route path="reports" element={<PlaceholderPage titleKey="nav.reports" />} />
            <Route path="activities" element={<PlaceholderPage titleKey="nav.activities" />} />
            {/* Admin-only management screens (server enforces RBAC too). */}
            <Route element={<AdminRoute />}>
              <Route path="categories" element={<CategoriesPage />} />
              <Route path="users" element={<UsersPage />} />
            </Route>
            <Route path="settings" element={<PlaceholderPage titleKey="nav.settings" />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </>
  );
}
