import type { NextConfig } from "next";

const apiProxyDestination =
  process.env.NEXT_PUBLIC_API_PROXY_DESTINATION || "http://localhost:8000";

const nextConfig: NextConfig = {
  trailingSlash: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*/",
        destination: `${apiProxyDestination}/api/:path*/`,
      },
      {
        source: "/api/:path*",
        destination: `${apiProxyDestination}/api/:path*/`,
      },
    ];
  },
};

export default nextConfig;
