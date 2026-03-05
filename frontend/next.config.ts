import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Local dev: proxy /api/* to the local backend
  async rewrites() {
    return process.env.NEXT_PUBLIC_API_URL
      ? []
      : [
          {
            source: "/api/:path*",
            destination: "http://localhost:8000/api/:path*",
          },
        ];
  },
};

export default nextConfig;
