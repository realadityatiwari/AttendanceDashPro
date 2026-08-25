import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /*
   * Phase 21D.2 — Vercel/Next.js 16.3 deployment compatibility fix.
   *
   * `output: "standalone"` is required for the self-hosted Docker path
   * (Phase 18A) but is incompatible with Vercel's adapter during Vercel
   * builds (ENOENT: .next/next-server.js.nft.json).
   *
   * Vercel sets `VERCEL=1` at build time, so:
   *   - Vercel builds use the default (normal) Next.js output.
   *   - Non-Vercel builds (Docker / local) retain "standalone".
   *
   * SSR and the Phase 13 PWA are preserved in both modes; this is NOT a
   * static export.
   */
  output: process.env.VERCEL ? undefined : "standalone",
};

export default nextConfig;
