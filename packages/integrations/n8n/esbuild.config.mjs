import { build } from 'esbuild';
import { cpSync, mkdirSync, rmSync } from 'fs';
import { glob } from 'glob';

// Ensure stale artifacts (including old test outputs) never leak into published tarballs.
rmSync('dist', { recursive: true, force: true });

// Find all .ts entry points (excluding tests)
const entryPoints = glob.sync('{nodes,credentials}/**/*.ts', {
	ignore: ['**/__tests__/**', '**/*.test.ts', '**/*.spec.ts'],
});

await build({
	entryPoints,
	bundle: true,
	platform: 'node',
	target: 'es2020',
	format: 'cjs',
	outdir: 'dist',
	minify: true,
	// n8n provides these at runtime — keep as external requires
	external: ['n8n-workflow', '@n8n/ai-node-sdk', '@n8n/ai-node-sdk/*'],
});

// Copy SVG icons to dist (replaces gulp)
for (const svg of glob.sync('nodes/**/*.svg')) {
	const dest = svg.replace(/^nodes/, 'dist/nodes');
	mkdirSync(dest.replace(/\/[^/]+$/, ''), { recursive: true });
	cpSync(svg, dest);
}

console.log('Build complete — n8n package built');
