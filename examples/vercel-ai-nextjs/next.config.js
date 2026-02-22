/** @type {import('next').NextConfig} */
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const localCoreDist = path.join(__dirname, '../../packages/core/dist/index.mjs');
const localVercelDist = path.join(__dirname, '../../packages/integrations/vercel-ai/dist/index.mjs');
const useLocalWorkspaceBuilds = fs.existsSync(localCoreDist) && fs.existsSync(localVercelDist);

const nextConfig = {
  reactStrictMode: true,
  ...(useLocalWorkspaceBuilds ? { outputFileTracingRoot: path.join(__dirname, '../..') } : {}),
  webpack: (config) => {
    config.resolve = config.resolve ?? {};
    config.resolve.alias = config.resolve.alias ?? {};
    if (useLocalWorkspaceBuilds) {
      // In monorepo dev, pin imports to local builds so example bundling
      // does not accidentally resolve older published packages.
      config.resolve.alias['@cascadeflow/core'] = localCoreDist;
      config.resolve.alias['@cascadeflow/vercel-ai'] = localVercelDist;
    }
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
