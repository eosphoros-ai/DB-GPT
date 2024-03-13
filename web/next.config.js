/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  experimental: {
    esmExternals: 'loose',
  },
  typescript: {
    ignoreBuildErrors: true,
  },
  env: {
    API_BASE_URL: process.env.API_BASE_URL,
  },
  trailingSlash: true,
  images: { unoptimized: true },
};

module.exports = nextConfig;
