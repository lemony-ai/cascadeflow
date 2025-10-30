# CascadeFlow Launch Checklist

## Pre-Launch Tasks

### 1. Repository Configuration
- [ ] Make repository PUBLIC
- [ ] Add repository topics for discoverability
- [ ] Set homepage URL to documentation site
- [ ] Enable GitHub Discussions for community Q&A
- [ ] Disable Wiki (use /docs folder instead)
- [ ] Create public Projects board for roadmap transparency
- [ ] **Deploy organization profile README**:
  - [ ] Copy `LEMONY_ORG_README.md` to `lemony-ai/.github/profile/README.md`
  - [ ] Configure pinned repositories (only Cascadeflow)
  - [ ] Verify organization landing page displays correctly

### 2. GitHub Secrets (CI/CD)
- [ ] Add `PYPI_API_TOKEN` for Python package publishing
- [ ] Add `NPM_TOKEN` for npm package publishing (n8n + @cascadeflow/core)
- [ ] Add `CODECOV_TOKEN` for code coverage (optional)
- [ ] Add `TEST_PYPI_API_TOKEN` for testing (optional)

### 3. Branch Protection
- [x] Require PR before merging
- [x] Require 1 approval
- [x] Require conversation resolution
- [ ] Add required status checks after first workflow run:
  - [ ] `test-python` (Python 3.9-3.12 on ubuntu-latest)
  - [ ] `test-typescript-core` (TypeScript core tests)
  - [ ] `test-n8n` (n8n node tests)
  - [ ] `lint-python` (Black, Ruff, mypy)
  - [ ] `lint-typescript` (ESLint, TypeScript)

### 4. Package Publishing
- [ ] Publish `cascadeflow` to PyPI (v0.1.0)
- [ ] Publish `@cascadeflow/core` to npm (v0.1.0)
- [ ] Publish `n8n-nodes-cascadeflow` to npm (v1.0.0)
- [ ] Verify all badges show correct status

### 5. GitHub Release
- [ ] Create v0.1.0 release from tag
- [ ] Write release notes highlighting key features
- [ ] Attach build artifacts (wheels, tarballs)
- [ ] Mark as "Latest Release"

### 6. Community Setup
- [ ] Create initial Discussions categories:
  - [ ] 📣 Announcements
  - [ ] 💡 Ideas & Feature Requests
  - [ ] 🙏 Q&A (mark as default for questions)
  - [ ] 🏆 Show and Tell (community projects)
  - [ ] 📚 Guides & Tutorials
- [ ] Pin welcome discussion with:
  - [ ] Getting started guide
  - [ ] How to contribute
  - [ ] Community guidelines
- [ ] Create public roadmap in Projects
- [ ] Add "good first issue" labels to beginner-friendly issues

### 7. Documentation
- [x] Main README with examples and badges
- [x] CONTRIBUTING guide (Python + TypeScript)
- [x] CODE_OF_CONDUCT
- [x] SECURITY policy
- [x] Comprehensive /docs folder
- [ ] Consider enabling GitHub Pages for docs hosting

### 8. Social & Marketing Prep
- [ ] Prepare launch announcement for:
  - [ ] GitHub Discussions
  - [ ] Twitter/X
  - [ ] LinkedIn
  - [ ] Dev.to / Hashnode
  - [ ] Hacker News (Show HN)
  - [ ] Product Hunt (optional)
- [ ] Create social preview image (1200x630px)
- [ ] Write launch blog post

### 9. Final Verification
- [ ] Test all README badges work
- [ ] Verify all documentation links work
- [ ] Run all examples to ensure they work
- [ ] Test installation: `pip install cascadeflow`
- [ ] Test installation: `npm install @cascadeflow/core`
- [ ] Verify workflows run successfully
- [ ] Check mobile/desktop README rendering
- [ ] Spell check all docs

### 10. Post-Launch Monitoring
- [ ] Monitor first workflow runs
- [ ] Watch for first issues/PRs
- [ ] Respond to community questions within 24h
- [ ] Track download metrics
- [ ] Gather early user feedback

---

## Launch Day Commands

### Make Repository Public
```bash
gh repo edit lemony-ai/CascadeFlow --visibility public
```

### Add Topics
```bash
gh repo edit lemony-ai/CascadeFlow \
  --add-topic ai \
  --add-topic llm \
  --add-topic openai \
  --add-topic anthropic \
  --add-topic claude \
  --add-topic gpt \
  --add-topic cost-optimization \
  --add-topic model-cascading \
  --add-topic python \
  --add-topic typescript \
  --add-topic n8n \
  --add-topic automation \
  --add-topic machine-learning \
  --add-topic artificial-intelligence \
  --add-topic api \
  --add-topic sdk
```

### Enable Discussions
```bash
gh repo edit lemony-ai/CascadeFlow --enable-discussions
```

### Disable Wiki
```bash
gh repo edit lemony-ai/CascadeFlow --enable-wiki=false
```

### Set Homepage
```bash
gh repo edit lemony-ai/CascadeFlow --homepage "https://docs.lemony.ai/cascadeflow"
```

### Create Release
```bash
gh release create v0.1.0 \
  --title "CascadeFlow v0.1.0 - Initial Release" \
  --notes-file RELEASE_NOTES.md \
  --latest
```

---

## Success Metrics to Track

- **Week 1**: GitHub stars, first contributors, first issues
- **Month 1**: Downloads (PyPI + npm), community discussions, documentation visits
- **Quarter 1**: Active contributors, production users, case studies

---

**Ready to launch? Run through this checklist systematically!** 🚀
