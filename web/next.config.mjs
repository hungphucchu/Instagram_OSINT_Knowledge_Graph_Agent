/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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
