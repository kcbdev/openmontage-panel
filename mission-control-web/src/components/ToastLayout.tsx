"use client";

import { createPortal } from "react-dom";
import { CheckCircle, XCircle, Loader2, X } from "lucide-react";
import { ToastProvider, useToast } from "@/lib/toast";

function ToastRenderer() {
  const { toasts, removeToast } = useToast();
  if (toasts.length === 0) return null;

  return createPortal(
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-center gap-2 px-3 py-2.5 rounded-lg shadow-lg text-sm text-white ${
            t.type === "success"
              ? "bg-green-600"
              : t.type === "error"
                ? "bg-red-600"
                : "bg-blue-600"
          }`}
        >
          {t.type === "success" ? (
            <CheckCircle className="w-4 h-4 shrink-0" />
          ) : t.type === "error" ? (
            <XCircle className="w-4 h-4 shrink-0" />
          ) : (
            <Loader2 className="w-4 h-4 shrink-0 animate-spin" />
          )}
          <span className="flex-1">{t.message}</span>
          <button onClick={() => removeToast(t.id)} className="shrink-0 hover:opacity-80">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
    </div>,
    document.body,
  );
}

export default function ToastLayout({ children }: { children: React.ReactNode }) {
  return (
    <ToastProvider>
      {children}
      <ToastRenderer />
    </ToastProvider>
  );
}
