"use client";

import {
  CircleUserRound,
  Palette,
  Download,
  MessageSquareText,
  Settings,
  LogOut,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useProfile } from "@/hooks/useApi";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

export type ShellModalId =
  | "profile"
  | "appearance"
  | "settings"
  | "feedback"
  | "install";

interface UserMenuProps {
  onOpenModal: (modal: ShellModalId) => void;
}

/**
 * Authenticated user menu. Opens the global shell modals and signs out
 * through the existing auth mechanism. Focus management, Escape and
 * outside-click closing are handled by the Base UI Menu primitive; items
 * close the menu after selection.
 */
export function UserMenu({ onOpenModal }: UserMenuProps) {
  const { user, logout } = useAuth();
  const { profile, isLoading } = useProfile();

  const displayName = profile?.display_name || user?.display_name || "Student";
  const initials = displayName.trim().charAt(0).toUpperCase() || "?";
  const rollNumber = profile?.roll_number || user?.roll_number || null;

  const handleSignOut = () => {
    logout();
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        aria-label="Open user menu"
        className="-m-1.5 flex items-center gap-3 rounded-md p-1.5 transition-colors outline-none hover:bg-accent focus-visible:bg-accent data-popup-open:bg-accent"
      >
        <Avatar className="h-8 w-8 border border-border bg-surface2">
          <AvatarFallback className="text-xs font-semibold">{initials}</AvatarFallback>
        </Avatar>
        <span className="hidden text-sm font-semibold text-foreground lg:block">
          {isLoading ? "…" : displayName}
        </span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel>
          <div className="flex flex-col gap-0.5 py-1">
            <p className="text-sm font-medium text-foreground">{displayName}</p>
            <p className="font-mono text-xs text-muted-foreground">
              {rollNumber || "No roll number"}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => onOpenModal("profile")}>
          <CircleUserRound className="mr-2 size-4" aria-hidden="true" />
          Profile
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onOpenModal("appearance")}>
          <Palette className="mr-2 size-4" aria-hidden="true" />
          Appearance
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onOpenModal("install")}>
          <Download className="mr-2 size-4" aria-hidden="true" />
          Install App
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onOpenModal("feedback")}>
          <MessageSquareText className="mr-2 size-4" aria-hidden="true" />
          Send Feedback
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onOpenModal("settings")}>
          <Settings className="mr-2 size-4" aria-hidden="true" />
          Settings
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          variant="destructive"
          onClick={handleSignOut}
        >
          <LogOut className="mr-2 size-4" aria-hidden="true" />
          Sign Out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}