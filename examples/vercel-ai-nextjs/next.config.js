/** @type {import('next').NextConfig} */
import { fileURLToPath } from 'url';
import path from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const nextConfig = {
  reactStrictMode: true,
  // Silence the multi-lockfile warning for this monorepo example and ensure
  // Next.js traces files correctly from the workspace root.
  outputFileTracingRoot: path.join(__dirname, '../..'),
};

export default nextConfig;
