#!/usr/bin/env node

import fs from 'fs';
import path from 'path';
import { spawnSync } from 'child_process';

const repoRoot = process.cwd();

const packages = [
  {
    name: '@cascadeflow/ml',
    dir: 'packages/ml',
    requiredFiles: ['dist/index.js', 'dist/index.mjs', 'dist/index.d.ts'],
  },
  {
    name: '@cascadeflow/core',
    dir: 'packages/core',
    requiredFiles: ['dist/index.js', 'dist/index.mjs', 'dist/index.d.ts'],
  },
  {
    name: '@cascadeflow/langchain',
    dir: 'packages/langchain-cascadeflow',
    requiredFiles: ['dist/index.js', 'dist/index.mjs', 'dist/index.d.ts'],
  },
  {
    name: '@cascadeflow/vercel-ai',
    dir: 'packages/integrations/vercel-ai',
    requiredFiles: ['dist/index.js', 'dist/index.mjs', 'dist/index.d.ts'],
  },
  {
    name: '@cascadeflow/paygentic',
    dir: 'packages/integrations/paygentic',
    requiredFiles: ['dist/index.js', 'dist/index.mjs', 'dist/index.d.ts'],
  },
  {
    name: '@cascadeflow/n8n-nodes-cascadeflow',
    dir: 'packages/integrations/n8n',
    requiredFiles: [
      'dist/credentials/CascadeFlowApi.credentials.js',
      'dist/nodes/LmChatCascadeFlow/LmChatCascadeFlow.node.js',
      'dist/nodes/CascadeFlowAgent/CascadeFlowAgent.node.js',
    ],
  },
];

function run(command, args, cwd) {
  const result = spawnSync(command, args, {
    cwd,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  if (result.status !== 0) {
    const detail = (result.stderr || result.stdout || '').trim();
    throw new Error(`Command failed: ${command} ${args.join(' ')}\n${detail}`);
  }

  return result.stdout.trim();
}

function assertNoWorkspaceProtocols(pkgJson, packageName) {
  const fields = ['dependencies', 'optionalDependencies', 'peerDependencies'];
  for (const field of fields) {
    const entries = Object.entries(pkgJson[field] || {});
    for (const [depName, version] of entries) {
      if (typeof version === 'string' && version.startsWith('workspace:')) {
        throw new Error(
          `${packageName}: packed package.json still contains workspace protocol in ${field} -> ${depName}: ${version}`,
        );
      }
    }
  }
}

function verifyPackage(pkg) {
  const pkgPath = path.join(repoRoot, pkg.dir);
  console.log(`\nPacking ${pkg.name} (${pkg.dir})...`);

  const packOutput = run('pnpm', ['pack', '--pack-destination', '.'], pkgPath);
  const tarball = packOutput.split(/\r?\n/).filter(Boolean).pop();
  if (!tarball || !tarball.endsWith('.tgz')) {
    throw new Error(`${pkg.name}: could not determine tarball from pnpm pack output: ${packOutput}`);
  }

  const tarballPath = path.join(pkgPath, tarball);

  try {
    const tarList = run('tar', ['-tf', tarballPath], repoRoot).split(/\r?\n/);
    for (const requiredFile of pkg.requiredFiles) {
      const packedPath = `package/${requiredFile}`;
      if (!tarList.includes(packedPath)) {
        throw new Error(`${pkg.name}: missing ${requiredFile} in ${tarball}`);
      }
    }

    const packedPackageJsonRaw = run('tar', ['-xOf', tarballPath, 'package/package.json'], repoRoot);
    const packedPackageJson = JSON.parse(packedPackageJsonRaw);
    assertNoWorkspaceProtocols(packedPackageJson, pkg.name);

    console.log(`${pkg.name}: OK (${tarball})`);
  } finally {
    fs.rmSync(tarballPath, { force: true });
  }
}

for (const pkg of packages) {
  verifyPackage(pkg);
}

console.log('\nAll npm package tarballs include required build artifacts and publish-safe dependency specs.');
