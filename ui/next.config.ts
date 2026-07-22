import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

const BACKEND_BASE_URL = "http://127.0.0.1:18080";

export default function nextConfig(phase: string): NextConfig {
  if (phase === PHASE_DEVELOPMENT_SERVER) {
    return {
      allowedDevOrigins: ["127.0.0.1"],
      async rewrites() {
        return [
          {
            source: "/api/:path*",
            destination: `${BACKEND_BASE_URL}/api/:path*`,
          },
          {
            source: "/v1/:path*",
            destination: `${BACKEND_BASE_URL}/v1/:path*`,
          },
          {
            source: "/v1beta/:path*",
            destination: `${BACKEND_BASE_URL}/v1beta/:path*`,
          },
        ];
      },
    };
  }

  return {
    output: "export",
    trailingSlash: true,
    images: {
      unoptimized: true,
    },
  };
}
