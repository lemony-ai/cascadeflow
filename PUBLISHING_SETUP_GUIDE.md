# Package Publishing Setup Guide

Complete step-by-step guide for setting up PyPI and npm publishing for Cascadeflow.

---

## Overview

You need to set up accounts and tokens for:
1. **PyPI** - for `cascadeflow` Python package
2. **npm** - for `@cascadeflow/core` TypeScript package
3. **npm** - for `n8n-nodes-cascadeflow` n8n node package

---

## Part 1: PyPI Setup (Python Package)

### Step 1: Create PyPI Account

1. Go to https://pypi.org/account/register/
2. Fill in:
   - Username: `lemony-ai` or your preferred username
   - Email: `hello@lemony.ai` (or your email)
   - Password: Use a strong password (save in password manager)
3. Verify email address
4. **Enable 2FA** (recommended for security):
   - Go to https://pypi.org/manage/account/
   - Click "Add 2FA with authentication application"
   - Use your authenticator app to scan QR code

### Step 2: Create API Token for GitHub Actions

1. Go to https://pypi.org/manage/account/token/
2. Click "Add API token"
3. Fill in:
   - Token name: `GitHub Actions - Cascadeflow`
   - Scope: **"Entire account"** (for now - we'll scope it after first publish)
4. Click "Add token"
5. **COPY THE TOKEN IMMEDIATELY** - it won't be shown again
   - Format: `pypi-AgEIcH...` (starts with `pypi-`)
   - Save it securely in your password manager

### Step 3: Add Token to GitHub Secrets

```bash
# Navigate to repository settings
gh secret set PYPI_API_TOKEN --body "pypi-AgEIcH..."
```

Or manually:
1. Go to https://github.com/lemony-ai/cascadeflow/settings/secrets/actions
2. Click "New repository secret"
3. Name: `PYPI_API_TOKEN`
4. Value: Paste the token (starts with `pypi-`)
5. Click "Add secret"

### Step 4: Scope Token to Specific Package (After First Publish)

After your first successful publish:

1. Go to https://pypi.org/manage/project/cascadeflow/settings/
2. Click "Manage publishing"
3. Create new scoped token:
   - Token name: `GitHub Actions - Cascadeflow (scoped)`
   - Scope: **"Project: cascadeflow"**
4. Update GitHub secret with new scoped token

### Step 5: Test PyPI Setup (Optional)

Create a TestPyPI account for testing:

1. Go to https://test.pypi.org/account/register/
2. Create account (can use same email)
3. Create API token: https://test.pypi.org/manage/account/token/
4. Add to GitHub secrets as `TEST_PYPI_API_TOKEN`

Test publish command:
```bash
python -m build
twine upload --repository testpypi dist/*
```

---

## Part 2: npm Setup (TypeScript & n8n Packages)

### Step 1: Create npm Account

1. Go to https://www.npmjs.com/signup
2. Fill in:
   - Username: `lemony-ai` or your preferred username
   - Email: `hello@lemony.ai`
   - Password: Use a strong password
3. Verify email address
4. **Enable 2FA** (REQUIRED by npm for publishing):
   - Go to https://www.npmjs.com/settings/~/profile
   - Click "Two-Factor Authentication"
   - Choose: **"Authorization and Publishing"** (not just "Authorization")
   - Scan QR code with authenticator app

### Step 2: Create npm Organization (Optional but Recommended)

For `@cascadeflow/core` scoped package:

1. Go to https://www.npmjs.com/org/create
2. Organization name: `cascadeflow`
3. Choose plan: **Free** (unlimited public packages)
4. Invite team members if needed

### Step 3: Create npm Access Token

1. Go to https://www.npmjs.com/settings/~/tokens
2. Click "Generate New Token"
3. Choose: **"Automation"** (for CI/CD)
   - This bypasses 2FA for automated publishing
4. Token name: `GitHub Actions - Cascadeflow`
5. Copy the token immediately
   - Format: `npm_...` (starts with `npm_`)
   - Save it securely

### Step 4: Add Token to GitHub Secrets

```bash
# Add npm token to GitHub secrets
gh secret set NPM_TOKEN --body "npm_..."
```

Or manually:
1. Go to https://github.com/lemony-ai/cascadeflow/settings/secrets/actions
2. Click "New repository secret"
3. Name: `NPM_TOKEN`
4. Value: Paste the token (starts with `npm_`)
5. Click "Add secret"

### Step 5: Configure Package Access

#### For @cascadeflow/core:

1. After first publish, go to: https://www.npmjs.com/package/@cascadeflow/core
2. Click "Settings" → "Collaborators"
3. Add team members if needed
4. Ensure package is set to **"Public"**

#### For n8n-nodes-cascadeflow:

1. After first publish, go to: https://www.npmjs.com/package/n8n-nodes-cascadeflow
2. Same steps as above
3. **Important**: Add keyword `n8n-community-node-package` in package.json
4. This makes it discoverable in n8n community nodes

---

## Part 3: Verify Package Configurations

### Python Package (cascadeflow)

Check `setup.py` or `pyproject.toml`:

```bash
cat setup.py | grep -A 10 "name="
# Should show: name="cascadeflow"
```

Verify build:
```bash
python -m build
ls dist/
# Should see: cascadeflow-0.1.0.tar.gz, cascadeflow-0.1.0-py3-none-any.whl
```

### TypeScript Core Package (@cascadeflow/core)

Check `packages/core/package.json`:

```bash
cat packages/core/package.json | grep -E "(name|version)"
# Should show: "name": "@cascadeflow/core", "version": "0.1.0"
```

Verify build:
```bash
cd packages/core
pnpm build
ls dist/
# Should see compiled .js, .d.ts files
```

### n8n Node Package (n8n-nodes-cascadeflow)

Check `packages/integrations/n8n/package.json`:

```bash
cat packages/integrations/n8n/package.json | grep -E "(name|version|keywords)"
# Should show:
# "name": "n8n-nodes-cascadeflow"
# "version": "0.1.0"
# "keywords": [..., "n8n-community-node-package"]
```

Verify build:
```bash
cd packages/integrations/n8n
pnpm build
ls dist/
# Should see compiled nodes
```

---

## Part 4: Test Publishing Locally

### Test PyPI Publish (Dry Run)

```bash
# Build package
python -m build

# Check package contents
twine check dist/*

# Test upload to TestPyPI
twine upload --repository testpypi dist/* --verbose
```

### Test npm Publish (Dry Run)

```bash
# For @cascadeflow/core
cd packages/core
npm publish --dry-run
# Shows what would be published

# For n8n-nodes-cascadeflow
cd packages/integrations/n8n
npm publish --dry-run
```

---

## Part 5: GitHub Actions Workflow Verification

### Check Workflow Files

1. **Python Publishing**: `.github/workflows/publish-python.yml`
   - Uses `PYPI_API_TOKEN` secret
   - Triggers on git tag push (e.g., `v0.1.0`)

2. **TypeScript Publishing**: `.github/workflows/publish-npm.yml`
   - Uses `NPM_TOKEN` secret
   - Publishes both `@cascadeflow/core` and `n8n-nodes-cascadeflow`
   - Triggers on git tag push

### Test Workflow Locally (Optional)

Install `act` to test GitHub Actions locally:

```bash
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash  # Linux

# Test publish workflow
act -s PYPI_API_TOKEN="your-token" -j publish-python
```

---

## Part 6: First Publish Checklist

### Pre-Publish Verification

- [ ] All tests passing
- [ ] Version numbers updated in:
  - [ ] `setup.py` or `pyproject.toml` (Python)
  - [ ] `packages/core/package.json` (TypeScript)
  - [ ] `packages/integrations/n8n/package.json` (n8n)
- [ ] CHANGELOG.md updated
- [ ] README.md badges pointing to correct packages
- [ ] GitHub secrets configured:
  - [ ] `PYPI_API_TOKEN`
  - [ ] `NPM_TOKEN`

### Publishing Steps

1. **Create and push git tag**:
   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0"
   git push origin v0.1.0
   ```

2. **Monitor GitHub Actions**:
   - Go to: https://github.com/lemony-ai/cascadeflow/actions
   - Watch workflows complete
   - Check for any errors

3. **Verify packages published**:
   ```bash
   # Check PyPI
   curl https://pypi.org/pypi/cascadeflow/json | jq '.info.version'

   # Check npm
   npm view @cascadeflow/core version
   npm view n8n-nodes-cascadeflow version
   ```

4. **Test installation**:
   ```bash
   # Python
   pip install cascadeflow==0.1.0

   # TypeScript
   npm install @cascadeflow/core@0.1.0

   # n8n (in n8n project)
   npm install n8n-nodes-cascadeflow@0.1.0
   ```

---

## Part 7: Post-Publishing Setup

### PyPI Project Page

1. Go to: https://pypi.org/project/cascadeflow/
2. Add project description (from README.md)
3. Add project links:
   - Homepage: https://github.com/lemony-ai/cascadeflow
   - Documentation: https://github.com/lemony-ai/cascadeflow#readme
   - Issues: https://github.com/lemony-ai/cascadeflow/issues
4. Add classifiers in `setup.py`:
   ```python
   classifiers=[
       "Development Status :: 4 - Beta",
       "Intended Audience :: Developers",
       "Topic :: Software Development :: Libraries :: Python Modules",
       "License :: OSI Approved :: MIT License",
       "Programming Language :: Python :: 3.9",
       "Programming Language :: Python :: 3.10",
       "Programming Language :: Python :: 3.11",
       "Programming Language :: Python :: 3.12",
   ]
   ```

### npm Package Pages

#### @cascadeflow/core

1. Go to: https://www.npmjs.com/package/@cascadeflow/core
2. Verify README displays correctly
3. Add keywords in `package.json`:
   ```json
   "keywords": [
     "ai", "llm", "openai", "anthropic", "claude",
     "gpt", "cost-optimization", "model-cascading",
     "typescript", "sdk"
   ]
   ```

#### n8n-nodes-cascadeflow

1. Go to: https://www.npmjs.com/package/n8n-nodes-cascadeflow
2. Verify it appears in n8n community nodes: https://www.npmjs.com/search?q=keywords:n8n-community-node-package
3. Ensure `package.json` has:
   ```json
   "keywords": [
     "n8n-community-node-package",
     "n8n",
     "ai",
     "cascadeflow"
   ],
   "n8n": {
     "nodes": [
       "dist/nodes/CascadeFlow/CascadeFlow.node.js"
     ]
   }
   ```

---

## Part 8: Troubleshooting

### PyPI Issues

**Error: "The user isn't allowed to upload to project 'cascadeflow'"**
- Solution: Package name already taken. Choose different name or reclaim if you own it.

**Error: "Invalid or non-existent authentication information"**
- Solution: Regenerate API token and update GitHub secret

**Error: "File already exists"**
- Solution: Increment version number, you can't re-upload same version

### npm Issues

**Error: "You must sign in to publish packages"**
- Solution: Check `NPM_TOKEN` is correctly set in GitHub secrets

**Error: "You do not have permission to publish"**
- Solution: Ensure you're a member of the `@cascadeflow` organization (for scoped packages)

**Error: "Package name too similar to existing package"**
- Solution: npm may block similar names. Choose more distinctive name.

### GitHub Actions Issues

**Workflow not triggering**
- Solution: Ensure workflows are enabled in repository settings
- Check branch protection rules aren't blocking automation

**Secrets not accessible**
- Solution: Secrets are only available to workflows in private repos by default
- For public repos, ensure secrets are added at repository level (not environment)

---

## Part 9: Security Best Practices

### Token Security

1. **Never commit tokens to git**
   - Add `.env` to `.gitignore`
   - Use GitHub secrets for CI/CD

2. **Rotate tokens regularly**
   - Set reminder to rotate every 90 days
   - Immediately rotate if compromised

3. **Use scoped tokens**
   - PyPI: Scope to specific package after first publish
   - npm: Use Automation tokens (bypass 2FA for CI/CD only)

4. **Monitor usage**
   - Check PyPI downloads: https://pypistats.org/packages/cascadeflow
   - Check npm downloads: https://www.npmjs.com/package/@cascadeflow/core

### Package Security

1. **Enable 2FA** on both PyPI and npm accounts
2. **Use package signing** (optional but recommended)
3. **Monitor security advisories**
   - GitHub Dependabot alerts
   - npm audit
   - Snyk or similar security scanning

---

## Part 10: Quick Reference Commands

### PyPI Commands

```bash
# Build package
python -m build

# Check package
twine check dist/*

# Upload to PyPI
twine upload dist/*

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Check package info
pip show cascadeflow
```

### npm Commands

```bash
# Login (one-time)
npm login

# Check logged in user
npm whoami

# Publish @cascadeflow/core
cd packages/core
npm publish --access public

# Publish n8n-nodes-cascadeflow
cd packages/integrations/n8n
npm publish --access public

# Check package info
npm view @cascadeflow/core
npm view n8n-nodes-cascadeflow

# Unpublish (within 72 hours only)
npm unpublish @cascadeflow/core@0.1.0 --force
```

### GitHub Secrets Commands

```bash
# List secrets
gh secret list

# Set secret
gh secret set SECRET_NAME --body "value"

# Delete secret
gh secret delete SECRET_NAME
```

---

## Ready to Publish!

Once you've completed all steps:

1. ✅ PyPI account created with 2FA enabled
2. ✅ npm account created with 2FA enabled
3. ✅ Tokens generated and added to GitHub secrets
4. ✅ Package configurations verified
5. ✅ Dry-run tests successful

You're ready to tag and publish your first release! 🚀

**Next Step**: Tag your release and let GitHub Actions handle the publishing:

```bash
git tag -a v0.1.0 -m "Release v0.1.0 - Initial public release"
git push origin v0.1.0
```

Then monitor: https://github.com/lemony-ai/cascadeflow/actions
