## 🎯 Description

<!-- Provide a clear and concise description of what this PR does -->



## 🔗 Related Issues

<!-- Link to related issues using keywords: Fixes #123, Closes #456, Related to #789 -->

- Fixes #
- Related to #

## 🔄 Type of Change

<!-- Check all that apply -->

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📝 Documentation update
- [ ] 🎨 Code style/refactoring (no functional changes)
- [ ] ⚡ Performance improvement
- [ ] ✅ Test additions/improvements
- [ ] 🔧 Configuration/build changes
- [ ] 🚀 New provider integration
- [ ] 🤖 Tool calling / function support

## 🧪 Testing

<!-- Describe how you tested your changes -->

### Test cases added
- [ ] Unit tests
- [ ] Integration tests
- [ ] End-to-end tests
- [ ] Manual testing

### Test coverage
- Current coverage: _%
- Coverage after changes: _%

### How to test
<!-- Provide clear instructions for reviewers to test your changes -->

```python
# Example code to test the changes
from cascadeflow import CascadeAgent

# Your test code here
```

## 📸 Screenshots/Examples (if applicable)

<!-- Add screenshots, logs, or example outputs -->

**Before:**
```
<!-- Output before your changes -->
```

**After:**
```
<!-- Output after your changes -->
```

## 📋 Checklist

### Code Quality
- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] My changes generate no new warnings
- [ ] I have added type hints where appropriate
- [ ] I have run `black` to format my code
- [ ] I have run `ruff` and fixed all linting issues
- [ ] I have run `mypy` for type checking

### Testing
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] I have tested with multiple providers (OpenAI, Anthropic, Groq, Ollama, etc.)
- [ ] I have tested both sequential and semantic routing strategies
- [ ] I have tested error cases and edge conditions

### Documentation
- [ ] I have updated the README if needed
- [ ] I have updated relevant documentation
- [ ] I have added docstrings to new functions/classes
- [ ] I have updated the CHANGELOG.md (if applicable)
- [ ] I have added examples if this is a new feature

### Dependencies
- [ ] I have minimized new dependencies
- [ ] If I added dependencies, I have updated `requirements.txt` and `pyproject.toml`
- [ ] I have tested with the minimum supported Python version (3.9)

### Breaking Changes
- [ ] This PR includes NO breaking changes
- [ ] OR: I have documented all breaking changes below
- [ ] OR: I have provided a migration guide

### Performance
- [ ] I have considered the performance impact of my changes
- [ ] I have benchmarked critical code paths (if applicable)
- [ ] I have not introduced any memory leaks or resource issues

## 💥 Breaking Changes (if any)

<!-- If your PR includes breaking changes, describe them here and provide migration instructions -->

### What breaks
<!-- Describe what will no longer work -->

### Migration path
<!-- Provide clear instructions on how users should update their code -->

```python
# Before (old API)

# After (new API)
```

## 📊 Performance Impact (if applicable)

<!-- If your changes affect performance, provide benchmarks -->

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Latency | - | - | - |
| Memory | - | - | - |
| Cost | - | - | - |

## 🔐 Security Considerations

<!-- Have you considered security implications? -->

- [ ] This PR does not introduce security vulnerabilities
- [ ] I have not exposed sensitive information (API keys, credentials, etc.)
- [ ] I have validated all user inputs
- [ ] I have considered rate limiting and abuse prevention

## 🚀 Deployment Notes (if applicable)

<!-- Any special deployment considerations? -->

- [ ] Requires environment variable changes
- [ ] Requires database migrations
- [ ] Requires dependency updates
- [ ] Should be deployed at a specific time

## 📝 Additional Notes

<!-- Any additional information that reviewers should know -->



## 🙏 Reviewers

<!-- Tag specific people if you want their review: @username -->

- [ ] Code review completed
- [ ] Tests passing
- [ ] Documentation reviewed
- [ ] Ready to merge

---

**By submitting this PR, I confirm that:**
- [ ] I have read and followed the [CONTRIBUTING.md](../CONTRIBUTING.md) guidelines
- [ ] My contribution is my own original work or properly attributed
- [ ] I agree to license my contribution under the project's MIT license
- [ ] I have tested my changes thoroughly