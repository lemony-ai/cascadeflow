# Deployment Instructions for Lemony Organization Profile

## 1. Deploy Organization README

The organization README needs to be placed in a special repository called `.github` within the `lemony-ai` organization.

### Steps:

1. **Create/Navigate to the `.github` repository**:
   ```bash
   # If the repository doesn't exist, create it at:
   # https://github.com/organizations/lemony-ai/repositories/new
   # Repository name: .github
   # Make it public for the profile to be visible
   ```

2. **Create the profile directory**:
   ```bash
   mkdir -p profile
   ```

3. **Deploy the README**:
   ```bash
   cp /tmp/LEMONY_ORG_README.md profile/README.md
   git add profile/README.md
   git commit -m "docs: add organization profile README"
   git push
   ```

The README will automatically appear on the organization landing page at https://github.com/lemony-ai

---

## 2. Pin Only Cascadeflow Repository

### Via GitHub Web Interface:

1. Go to: https://github.com/lemony-ai
2. Click "Customize your pins" (appears when you hover over the pinned repositories section)
3. **Uncheck all repositories except**:
   - ✅ `cascadeflow` (keep pinned)
4. **Unpin these**:
   - ❌ `.github` (if currently pinned)
   - ❌ `pgloader` (if currently pinned)
   - ❌ Any other repositories

5. Save changes

### Result:
Only `cascadeflow` will be displayed as a pinned repository on the organization landing page.

---

## 3. Optional: Make Repositories Private

If you want to hide `.github` and `pgloader` from the public:

### Make `.github` private:
```bash
gh repo edit lemony-ai/.github --visibility private
```

### Delete or archive `pgloader` fork:
```bash
# Option 1: Delete the fork
gh repo delete lemony-ai/pgloader --yes

# Option 2: Archive it (keeps history but hides from active repos)
gh repo archive lemony-ai/pgloader --yes
```

**Note**: The organization profile README will still work even if the `.github` repository is private.

---

## 4. Verification

After deployment:

1. Visit: https://github.com/lemony-ai
2. Verify:
   - ✅ Organization README is displayed
   - ✅ Only `cascadeflow` is pinned
   - ✅ X profile badge links to @SaschaBuehrle
   - ✅ All badges and links work correctly

---

## Quick Deploy Script

```bash
#!/bin/bash
# Quick deployment script

# 1. Clone or navigate to .github repo
cd /path/to/lemony-ai/.github

# 2. Create profile directory
mkdir -p profile

# 3. Copy README
cp /tmp/LEMONY_ORG_README.md profile/README.md

# 4. Commit and push
git add profile/README.md
git commit -m "docs: add organization profile README

- Professional landing page for lemony-ai organization
- Features Cascadeflow project showcase
- Includes company mission and philosophy
- X profile link for @SaschaBuehrle
"
git push

# 5. Configure pinned repositories (manual step via GitHub UI)
echo "✅ README deployed!"
echo "⚠️  Manual step: Go to https://github.com/lemony-ai and configure pins to show only 'cascadeflow'"
```

---

## Files

- **Organization README**: `/tmp/LEMONY_ORG_README.md`
- **Target location**: `lemony-ai/.github/profile/README.md` (on GitHub)
