import type { NextConfig } from 'next'

const backendBaseUrl = process.env.LENS_UI_BACKEND_BASE_URL || 'http://127.0.0.1:18080'

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendBaseUrl}/api/:path*`
      },
      {
        source: '/v1/chat/completions',
        destination: `${backendBaseUrl}/v1/chat/completions`
      },
      {
        source: '/v1/responses',
        destination: `${backendBaseUrl}/v1/responses`
      },
      {
        source: '/v1/messages',
        destination: `${backendBaseUrl}/v1/messages`
      },
      {
        source: '/v1/models',
        destination: `${backendBaseUrl}/v1/models`
      },
      {
        source: '/v1beta/:path*',
        destination: `${backendBaseUrl}/v1beta/:path*`
      }
    ]
  }
}

export default nextConfig
