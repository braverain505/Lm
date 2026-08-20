/** @type {import('next').NextConfig} */
const nextConfig = {
  // ESLint is not configured in this repo yet; Next would otherwise block
  // production builds on an interactive config prompt.
  eslint: { ignoreDuringBuilds: true },
  // The @schoolos/shared package ships raw TypeScript from its src/ (see
  // apps/web/tsconfig.json paths + packages/shared/package.json exports).
  // Transpile + cache it as a first-class dependency so dev/build don't
  // re-transform it per page and slow every route down.
  transpilePackages: ["@schoolos/shared"],
  // Proxy /api → the FastAPI service so the browser rides a single origin and
  // httpOnly cookies flow without CORS. The API backend publishes under /api.
  async rewrites() {
    const apiUrl = process.env.API_URL ?? "https://schoolos-api-5066.onrender.com";
    return [
      { source: "/api/:path*", destination: `${apiUrl}/api/:path*` },
    ];
  },
};

export default nextConfig;