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
  webpack: (config) => {
    config.resolve = config.resolve ?? {};
    config.resolve.alias = config.resolve.alias ?? {};
    // Pin monorepo imports to local builds so example bundling does not
    // accidentally resolve an older published package from the pnpm store.
    config.resolve.alias['@cascadeflow/core'] = path.join(__dirname, '../../packages/core/dist/index.mjs');
    config.resolve.alias['@cascadeflow/vercel-ai'] = path.join(__dirname, '../../packages/integrations/vercel-ai/dist/index.mjs');

    // cascadeflow uses dynamic optional imports for integrations/providers.
    // Next's webpack build warns about "dependency is an expression"; it's safe.
    config.ignoreWarnings = config.ignoreWarnings ?? [];
    config.ignoreWarnings.push({
      message: /Critical dependency: the request of a dependency is an expression/,
    });
    return config;
  },
};

export default nextConfig;
