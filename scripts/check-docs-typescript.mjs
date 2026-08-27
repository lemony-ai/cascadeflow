import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(scriptDirectory, '..');
const docsRoot = path.join(repositoryRoot, 'docs-site');
const requireFromCore = createRequire(
  path.join(repositoryRoot, 'packages', 'core', 'package.json'),
);
const ts = requireFromCore('typescript');

function listMdxFiles(directory) {
  const files = [];

  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...listMdxFiles(target));
    } else if (entry.isFile() && entry.name.endsWith('.mdx')) {
      files.push(target);
    }
  }

  return files;
}

function lineNumberAt(source, offset) {
  return source.slice(0, offset).split(/\r?\n/).length;
}

const fencePattern = /```(typescript|tsx)(?: [^\n]*)?\r?\n([\s\S]*?)```/g;
const failures = [];
let checkedBlocks = 0;

for (const file of listMdxFiles(docsRoot)) {
  const source = fs.readFileSync(file, 'utf8');
  let match;

  while ((match = fencePattern.exec(source)) !== null) {
    checkedBlocks += 1;
    const language = match[1];
    const code = match[2];
    const blockStartLine = lineNumberAt(source, match.index) + 1;
    const output = ts.transpileModule(code, {
      compilerOptions: {
        jsx: ts.JsxEmit.ReactJSX,
        module: ts.ModuleKind.ESNext,
        target: ts.ScriptTarget.ES2020,
      },
      fileName: `${file}.${language === 'tsx' ? 'tsx' : 'ts'}`,
      reportDiagnostics: true,
    });

    for (const diagnostic of output.diagnostics ?? []) {
      if (diagnostic.category !== ts.DiagnosticCategory.Error) {
        continue;
      }

      let diagnosticLine = blockStartLine;
      if (diagnostic.file && diagnostic.start !== undefined) {
        const position = diagnostic.file.getLineAndCharacterOfPosition(diagnostic.start);
        diagnosticLine += position.line;
      }

      const relativeFile = path.relative(repositoryRoot, file);
      const message = ts.flattenDiagnosticMessageText(diagnostic.messageText, ' ');
      failures.push(`${relativeFile}:${diagnosticLine}: ${message}`);
    }
  }
}

if (failures.length > 0) {
  console.error(failures.join('\n'));
  process.exitCode = 1;
} else {
  console.log(`Checked ${checkedBlocks} TypeScript and TSX documentation blocks.`);
}
