import { build } from 'esbuild';
import { cpSync, mkdirSync } from 'fs';
import { glob } from 'glob';

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
	external: [
		'n8n-workflow',
		'@langchain/core',
		'@langchain/core/*',
		// Dynamic import in @cascadeflow/core, never used in n8n
		'@cascadeflow/ml',
	],
});

// Copy SVG icons to dist (replaces gulp)
for (const svg of glob.sync('nodes/**/*.svg')) {
	const dest = svg.replace(/^nodes/, 'dist/nodes');
	mkdirSync(dest.replace(/\/[^/]+$/, ''), { recursive: true });
	cpSync(svg, dest);
}

console.log('Build complete — @cascadeflow/core bundled inline');
