/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
    images: {
      domains: ['localhost'],
    },
    env: {
      NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5000/api',
      NEXT_PUBLIC_DEEPSEEK_URL: process.env.NEXT_PUBLIC_DEEPSEEK_URL || 'http://localhost:8000',
      NEXT_PUBLIC_PHI3_URL: process.env.NEXT_PUBLIC_PHI3_URL || 'http://localhost:8001',
    },
    webpack: (config) => {
      // Resolve issues with leaflet on Next.js
      config.resolve.fallback = { fs: false, path: false };
      return config;
    },
  };
  
  module.exports = nextConfig;