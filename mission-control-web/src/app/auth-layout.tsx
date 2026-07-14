"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { AuthProvider, useAuth } from "@/lib/auth-context";

function Header() {
  const { user, loading, logout } = useAuth();

  return (
    <header className="border-b bg-white">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link href="/projects" className="font-semibold text-lg">
          Mission Control
        </Link>
        <nav className="flex items-center gap-3">
          {loading ? null : user ? (
            <>
              <Link href="/settings" className="text-sm text-gray-500 hover:text-gray-700">
                Settings
              </Link>
              <Link href="/projects/new" className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700">
                + New Launch
              </Link>
              <span className="text-xs text-gray-400 ml-2">{user.email}</span>
              <button onClick={logout} className="text-xs text-gray-400 hover:text-gray-600 ml-1">
                logout
              </button>
            </>
          ) : (
            <Link href="/login" className="text-sm text-blue-600 hover:underline">
              Sign in
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <Header />
      <main className="max-w-6xl mx-auto px-6 py-6">{children}</main>
    </AuthProvider>
  );
}
