"use client";

import { useState } from "react";
import { Download, MonitorSmartphone, Info, CheckCircle2 } from "lucide-react";
import { ShellDialog } from "@/components/shell/ShellDialog";
import { Button } from "@/components/ui/button";
import type { BeforeInstallPromptEvent } from "@/hooks/useInstallPrompt";

interface InstallAppModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  deferredPrompt: BeforeInstallPromptEvent | null;
  isStandalone: boolean;
}

export function InstallAppModal({
  open,
  onOpenChange,
  deferredPrompt,
  isStandalone,
}: InstallAppModalProps) {
  const [installOutcome, setInstallOutcome] = useState<"idle" | "accepted" | "dismissed">("idle");
  const [installing, setInstalling] = useState(false);

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setInstallOutcome("idle");
      setInstalling(false);
    }
    onOpenChange(next);
  };

  const handleInstall = async () => {
    if (!deferredPrompt || installing) return;
    setInstalling(true);
    try {
      await deferredPrompt.prompt();
      const choice = await deferredPrompt.userChoice;
      setInstallOutcome(choice.outcome);
    } catch {
      setInstallOutcome("dismissed");
    } finally {
      setInstalling(false);
    }
  };

  return (
    <ShellDialog
      open={open}
      onOpenChange={handleOpenChange}
      title="Install App"
      description="Install AttendanceDash Pro on this device"
    >
      {isStandalone ? (
        <div className="flex flex-col items-center gap-3 py-4 text-center">
          <CheckCircle2 className="size-10 text-success" aria-hidden="true" />
          <p className="text-sm font-medium text-foreground">
            You are using the installed app
          </p>
          <p className="text-sm text-muted-foreground">
            AttendanceDash Pro is running in standalone mode from your device.
          </p>
        </div>
      ) : deferredPrompt ? (
        <div className="flex flex-col gap-3 py-2">
          {installOutcome === "accepted" ? (
            <div className="flex flex-col items-center gap-3 py-4 text-center">
              <CheckCircle2 className="size-10 text-success" aria-hidden="true" />
              <p className="text-sm font-medium text-foreground">Installed</p>
              <p className="text-sm text-muted-foreground">
                You can now launch AttendanceDash Pro from your home screen.
              </p>
            </div>
          ) : (
            <>
              <div className="flex gap-2.5 rounded-lg border border-border bg-background p-3">
                <MonitorSmartphone className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <p className="text-xs leading-relaxed text-muted-foreground">
                  Your browser offers to install this app. The app will launch
                  in its own window, with an offline shell, once installed.
                </p>
              </div>
              <Button onClick={handleInstall} disabled={installing}>
                <Download className="size-4" aria-hidden="true" />
                Install AttendanceDash Pro
              </Button>
              {installOutcome === "dismissed" && (
                <p className="text-xs text-muted-foreground">
                  You dismissed the install prompt. You can try again later.
                </p>
              )}
            </>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-3 py-2">
          <div className="flex gap-2.5 rounded-lg border border-border bg-background p-3">
            <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <div className="text-xs leading-relaxed text-muted-foreground">
              <p>
                This app is not installable yet. Installation requires PWA
                infrastructure — a web app manifest and a registered service
                worker — which are not configured in this build.
              </p>
              <p className="mt-1.5">
                Once PWA support lands, the browser will offer an install
                prompt here and the app will launch with its own window and
                offline shell. Tracked in task.md.
              </p>
            </div>
          </div>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Got it
          </Button>
        </div>
      )}
    </ShellDialog>
  );
}