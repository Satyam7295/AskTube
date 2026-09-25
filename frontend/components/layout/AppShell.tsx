"use client";

import { useState } from "react";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

type AppShellProps = { children: React.ReactNode; activeView: string; onNavigate: (view: string) => void };

export function AppShell({ children, activeView, onNavigate }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  return (
    <div className="min-h-screen bg-[#f9fafb] text-[#16181d]">
      <Header onMenu={() => setSidebarOpen(true)} />
      <div className="flex">
        <Sidebar activeView={activeView} onNavigate={onNavigate} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}