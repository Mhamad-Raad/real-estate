import { Outlet } from "react-router-dom";

import { VersionMismatchBanner } from "@/features/system/VersionMismatchBanner";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

// Shell frame: fixed sidebar + header, scrollable content. Direction flips via <html dir>.
export function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <VersionMismatchBanner />
        <main className="flex-1 overflow-y-auto p-4 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
