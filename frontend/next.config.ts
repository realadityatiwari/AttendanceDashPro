import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* Phase 18A: standalone output — minimal self-contained production server
   * (smaller Docker image). SSR and the Phase 13 PWA are preserved; this is
   * NOT a static export. */
  output: "standalone",
};

export default nextConfig;
