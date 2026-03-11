import { build } from 'esbuild';
import { cpSync, mkdirSync, rmSync } from 'fs';
import { glob } from 'glob';

// Find all .ts entry points (excluding tests)
const entryPoints = glob.sync('{nodes,credentials}/**/*.ts', {
	ignore: ['**/__tests__/**', '**/*.test.ts', '**/*.spec.ts'],
});

// Ensure stale artifacts (e.g. old compiled tests) are never published.
rmSync('dist', { recursive: true, force: true });

await build({
	entryPoints,
	bundle: true,
	platform: 'node',
	target: 'es2020',
	format: 'cjs',
	outdir: 'dist',
	minify: true,
	// n8n provides these at runtime — keep as external requires
	external: [
		'n8n-workflow',
		'@langchain/core',
		'@langchain/core/*',
	],
});

// Copy SVG icons to dist (replaces gulp)
for (const svg of glob.sync('nodes/**/*.svg')) {
	const dest = svg.replace(/^nodes/, 'dist/nodes');
	mkdirSync(dest.replace(/\/[^/]+$/, ''), { recursive: true });
	cpSync(svg, dest);
}
