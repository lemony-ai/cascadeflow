# Publishing n8n v0.5.0 - Migration Guide

## ⚠️ Important Notice

This release changes the version from **5.0.7** back to **0.5.0** to align with the main cascadeflow release versioning.

**Impact:** Users with 5.0.x installed will need to manually reinstall, as npm treats 0.5.0 as a "downgrade" from 5.0.7.

## Pre-Publishing Checklist

- [x] Version updated to `0.5.0` in `package.json`
- [x] Migration notice added to README
- [x] Version history updated
- [x] Deprecation script created (`DEPRECATE_5.0.x.sh`)
- [ ] All tests passing
- [ ] Build successful

## Publishing Steps

### 1. Build the Package

```bash
cd packages/integrations/n8n
pnpm build
```

### 2. Verify Package Contents

```bash
pnpm pack
# This creates a .tgz file - inspect it to ensure it contains the correct files
tar -tzf cascadeflow-n8n-nodes-cascadeflow-0.5.0.tgz | head -20
```

### 3. Publish to npm

```bash
# Make sure you're logged in
npm whoami

# Publish
pnpm publish --access public

# Or with npm directly:
npm publish --access public
```

### 4. Deprecate Old Versions

**After** v0.5.0 is published, run the deprecation script:

```bash
./DEPRECATE_5.0.x.sh
```

Or manually:

```bash
npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.1 "Version numbering error. Please uninstall and install v0.5.0 or later."
npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.2 "Version numbering error. Please uninstall and install v0.5.0 or later."
npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.3 "Version numbering error. Please uninstall and install v0.5.0 or later."
npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.4 "Version numbering error. Please uninstall and install v0.5.0 or later."
npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.5 "Version numbering error. Please uninstall and install v0.5.0 or later."
npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.6 "Version numbering error. Please uninstall and install v0.5.0 or later."
npm deprecate @cascadeflow/n8n-nodes-cascadeflow@5.0.7 "Version numbering error. Please uninstall and install v0.5.0 or later."
```

### 5. Verify on npm

```bash
npm view @cascadeflow/n8n-nodes-cascadeflow versions
npm view @cascadeflow/n8n-nodes-cascadeflow
```

Expected output should show:
- Latest version: `0.5.0`
- Deprecated versions: 5.0.1 through 5.0.7

### 6. Update GitHub Release Notes

When creating the v0.5.0 GitHub release, include this migration notice:

```markdown
## ⚠️ n8n Integration Version Migration

If you're using the n8n integration and have versions 5.0.1-5.0.7 installed:

1. Go to Settings > Community Nodes in n8n
2. Uninstall @cascadeflow/n8n-nodes-cascadeflow
3. Reinstall by searching for @cascadeflow/n8n-nodes-cascadeflow

This manual reinstall is necessary due to npm's version handling.
```

## User Communication

### For Existing 5.0.x Users

Users will see:
1. **Deprecation warning** when viewing 5.0.x versions on npm
2. **Migration notice** at the top of the README on npm and GitHub
3. **Won't auto-upgrade** - they must manually uninstall/reinstall

### What They Need to Do

1. Open n8n
2. Go to **Settings** > **Community Nodes**
3. **Uninstall** `@cascadeflow/n8n-nodes-cascadeflow`
4. **Reinstall** by searching for `@cascadeflow/n8n-nodes-cascadeflow`
5. Verify they're on v0.5.0

## Rollback Plan

If issues are discovered after publishing:

```bash
# Unpublish is only allowed within 72 hours
npm unpublish @cascadeflow/n8n-nodes-cascadeflow@0.5.0

# Then fix and republish as 0.5.1
```

## Future Versioning

Going forward, n8n package versions will align with main cascadeflow releases:
- Main cascadeflow: `0.5.0`, `0.5.1`, `0.6.0`, etc.
- n8n integration: `0.5.0`, `0.5.1`, `0.6.0`, etc.

## Files Changed

- `package.json` - Version changed from 5.0.7 to 0.5.0
- `README.md` - Added migration notice and updated version history
- `DEPRECATE_5.0.x.sh` - Script to deprecate old versions (new file)
- `PUBLISH_0.5.0.md` - This publishing guide (new file)
