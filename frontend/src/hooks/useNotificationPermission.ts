"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type NotificationPermissionState =
  | "unsupported"
  | "default"
  | "granted"
  | "denied";

function getPermission(): NotificationPermissionState {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return "unsupported";
  }
  return window.Notification.permission;
}

export function useNotificationPermission() {
  const supported = typeof window !== "undefined" && "Notification" in window;
  const [permission, setPermission] = useState<NotificationPermissionState>(getPermission);
  const [isRequesting, setIsRequesting] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    if (!supported) return;

    const sync = () => {
      if (mountedRef.current) setPermission(getPermission());
    };

    // The `permissionchange` event fires on the Notification constructor
    // object. It is not part of the TypeScript DOM lib typing, so access it
    // defensively and fall back to focus re-sync where unsupported.
    const NotificationCtor = window.Notification as typeof window.Notification & {
      addEventListener?: (type: string, listener: () => void) => void;
      removeEventListener?: (type: string, listener: () => void) => void;
    };
    if (typeof NotificationCtor.addEventListener === "function") {
      try {
        NotificationCtor.addEventListener("permissionchange", sync);
        return () =>
          NotificationCtor.removeEventListener?.("permissionchange", sync);
      } catch {
        // fall through to focus sync
      }
    }

    const onFocus = () => sync();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [supported]);

  const requestPermission = useCallback(async (): Promise<NotificationPermissionState> => {
    if (!supported) return "unsupported";
    const current = getPermission();
    if (current !== "default") return current;
    setIsRequesting(true);
    try {
      const result = await window.Notification.requestPermission();
      if (mountedRef.current) setPermission(result);
      return result;
    } catch {
      const after = getPermission();
      if (mountedRef.current) setPermission(after);
      return after;
    } finally {
      if (mountedRef.current) setIsRequesting(false);
    }
  }, [supported]);

  return { supported, permission, isRequesting, requestPermission } as const;
}