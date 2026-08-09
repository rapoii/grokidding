import type { NextConfig } from "next";

const API_URL = process.env.API_URL || "http://localhost:8090";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_URL}/api/:path*`,
      },
      {
        source: "/ws",
        destination: `${API_URL}/ws`,
      },
    ];
  },
};

export default nextConfig;
