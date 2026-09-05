import Link from "next/link";
import Image from "next/image";
import { Compass } from "lucide-react";

/**
 * Route-level 404 (UI-007). Branded, token-based, mobile-safe; offers the
 * primary recovery destination (dashboard) without exposing internal details.
 */
export default function NotFound() {
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-8 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-muted">
          <Compass className="size-6 text-muted-foreground" aria-hidden="true" />
        </div>
        <div className="mt-4 flex items-center justify-center gap-2">
          <Image
            src="/brand/logo-mark.png"
            alt=""
            width={20}
            height={20}
            className="size-5"
          />
          <span className="text-sm font-semibold text-foreground">
            AttendanceDash Pro
          </span>
        </div>
        <h1 className="mt-3 text-xl font-bold tracking-tight text-foreground">
          Page not found
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          The page you&apos;re looking for doesn&apos;t exist or may have
          moved.
        </p>
        <Link
          href="/dashboard"
          className="mt-6 inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors outline-none hover:bg-primary/80 focus-visible:ring-2 focus-visible:ring-ring/60"
        >
          Go to Dashboard
        </Link>
      </div>
    </div>
  );
}
