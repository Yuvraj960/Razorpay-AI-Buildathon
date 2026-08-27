/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // API proxying happens in app/api/[...path]/route.ts (runtime BACKEND_URL),
  // NOT via rewrites here: standalone builds freeze next.config at build time.
};

export default nextConfig;
