/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    // Full ingest can run longer than the default proxy window.
    proxyTimeout: 5 * 60 * 1000
  },
  async rewrites() {
    const backend = process.env.BACKEND_URL || "http://127.0.0.1:8080";
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`
      }
    ];
  }
};

export default nextConfig;
