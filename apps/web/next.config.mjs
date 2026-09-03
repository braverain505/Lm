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
  // API proxy is now handled by /api/proxy/[...path]/route.ts
  // which forwards requests server-side using process.env.API_URL
};

export default nextConfig;