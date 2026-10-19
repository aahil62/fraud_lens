import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Self-contained server for the single-container image (scripts/serve.py).
  output: "standalone",
  experimental: {
    optimizePackageImports: ["@phosphor-icons/react"],
  },
  // In the container the browser only reaches this server; it proxies the
  // API, which stays bound to 127.0.0.1. Local dev keeps calling :8001 directly.
  async rewrites() {
    return [{ source: "/backend/:path*", destination: "http://127.0.0.1:8001/:path*" }];
  },
};

export default nextConfig;
