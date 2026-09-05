"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastVariant = "success" | "error" | "warning" | "info";

interface ToastOptions {
  title: string;
  description?: string;
  variant?: ToastVariant;
  /** Auto-dismiss delay in ms. Defaults: 5000 for success/info, 8000 for error/warning. */
  duration?: number;
  /** Optional inline action (e.g. "Undo"); clicking it runs the handler and
   * closes the toast. Phase 8: supports notification dismiss-undo. */
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface ToastItem {
  id: number;
  title: string;
  description?: string;
  variant: ToastVariant;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface ToastContextValue {
  toast: (options: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const VARIANT_META: Record<
  ToastVariant,
  { icon: typeof CheckCircle2; iconClass: string; assertive: boolean }
> = {
  success: { icon: CheckCircle2, iconClass: "text-success", assertive: false },
  error: { icon: XCircle, iconClass: "text-destructive", assertive: true },
  warning: { icon: AlertTriangle, iconClass: "text-warning", assertive: true },
  info: { icon: Info, iconClass: "text-primary", assertive: false },
};

const DEFAULT_DURATION: Record<ToastVariant, number> = {
  success: 5000,
  info: 5000,
  error: 8000,
  warning: 8000,
};

/** Maximum toasts kept on screen; older ones are dropped. */
const MAX_VISIBLE = 3;

/**
 * Lightweight application toast layer (UI-025 feedback foundation).
 *
 * No external dependency: a context provider plus a fixed viewport rendered
 * by the provider. Toasts are non-blocking, auto-dismiss, always manually
 * dismissible, use the canonical semantic tokens (success/error/warning/
 * primary) with an icon so state is never conveyed by color alone, and are
 * announced politely (success/info) or assertively (error/warning). Sits
 * above the mobile bottom navigation and never steals focus.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const toast = useCallback(
    (options: ToastOptions) => {
      const id = Date.now() + Math.random();
      const variant = options.variant ?? "info";
      setToasts((prev) => [
        ...prev.slice(-(MAX_VISIBLE - 1)),
        { ...options, variant, id },
      ]);
      const duration = options.duration ?? DEFAULT_DURATION[variant];
      timers.current.set(
        id,
        setTimeout(() => dismiss(id), duration)
      );
    },
    [dismiss]
  );

  useEffect(() => {
    const pending = timers.current;
    return () => {
      pending.forEach((timer) => clearTimeout(timer));
      pending.clear();
    };
  }, []);

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-label="Notifications"
        className="pointer-events-none fixed inset-x-4 bottom-24 z-50 flex flex-col items-center gap-2 sm:inset-x-auto sm:bottom-6 sm:right-6 sm:items-end"
      >
        {toasts.map((item) => {
          const meta = VARIANT_META[item.variant];
          const Icon = meta.icon;
          return (
            <div
              key={item.id}
              role={meta.assertive ? "alert" : "status"}
              aria-live={meta.assertive ? "assertive" : "polite"}
              className={cn(
                "pointer-events-auto flex w-full max-w-sm items-start gap-2.5 rounded-lg border border-border bg-popover p-3 shadow-lg animate-in fade-in slide-in-from-bottom-2 duration-200 motion-reduce:animate-none",
                item.variant === "error" && "border-destructive/40",
                item.variant === "warning" && "border-warning/40",
                item.variant === "success" && "border-success/40"
              )}
            >
              <Icon
                className={cn("mt-0.5 size-4 shrink-0", meta.iconClass)}
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">
                  {item.title}
                </p>
                {item.description && (
                  <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                    {item.description}
                  </p>
                )}
              </div>
              {item.action && (
                <button
                  type="button"
                  onClick={() => {
                    item.action?.onClick();
                    dismiss(item.id);
                  }}
                  className="shrink-0 rounded-md px-2 py-1 text-xs font-semibold text-primary outline-none transition-colors hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring/60"
                >
                  {item.action.label}
                </button>
              )}
              <button
                type="button"
                aria-label="Dismiss notification"
                onClick={() => dismiss(item.id)}
                className="shrink-0 rounded-md p-1 text-muted-foreground outline-none transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/60"
              >
                <X className="size-3.5" aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
