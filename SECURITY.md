# Security Policy

## Supported Versions

We release security updates for the following versions of CascadeFlow:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

We recommend always using the latest version for the best security and features.

---

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

**Please do NOT create a public GitHub issue for security vulnerabilities.**

Instead, report security issues via email to:

**security@lemony.ai**

### What to Include

Please include the following information in your report:

- Type of vulnerability (e.g., injection, authentication bypass, data exposure)
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it
- Any potential mitigations you've identified

### What to Expect

After you submit a report:

1. **Acknowledgment:** We will acknowledge receipt within 48 hours
2. **Assessment:** We will assess the vulnerability and determine its impact
3. **Updates:** We will keep you informed about our progress
4. **Fix:** We will work on a fix and coordinate disclosure timing with you
5. **Credit:** We will credit you in the security advisory (unless you prefer to remain anonymous)

### Timeline

- **48 hours:** Initial response acknowledging receipt
- **7 days:** Initial assessment of vulnerability severity
- **30 days:** Target for releasing a fix (may vary based on complexity)
- **90 days:** Public disclosure (coordinated with reporter)

---

## Security Update Policy

### How We Handle Security Issues

1. **Verify:** We verify the reported vulnerability
2. **Assess:** We assess the severity using CVSS scoring
3. **Fix:** We develop and test a fix
4. **Release:** We release a patched version
5. **Announce:** We publish a security advisory
6. **Notify:** We notify affected users

### Severity Levels

We classify vulnerabilities using the following severity levels:

- **Critical:** Immediate risk to user data or system integrity
- **High:** Significant risk that should be addressed quickly
- **Medium:** Moderate risk with limited impact
- **Low:** Minor issues with minimal impact

### Security Advisories

Security advisories will be published on:
- GitHub Security Advisories
- Release notes
- Project README (for critical issues)

---

## Security Best Practices

### For Users

When using CascadeFlow, follow these security practices:

#### API Key Management

**Never commit API keys to version control:**

```bash
# Always use .env files
echo "OPENAI_API_KEY=sk-..." >> .env

# Ensure .env is in .gitignore
echo ".env" >> .gitignore
```

**Use environment variables:**

```python
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")  # ✅ Secure
```

**Don't hardcode keys:**

```python
# ❌ NEVER DO THIS
api_key = "sk-proj-abc123..."

# ✅ DO THIS INSTEAD
api_key = os.getenv("OPENAI_API_KEY")
```

#### Input Validation

**Always validate user input:**

```python
# Validate before passing to models
def sanitize_input(user_input: str) -> str:
    # Remove dangerous characters
    # Limit length
    # Validate format
    return cleaned_input
```

#### Rate Limiting

**Implement rate limiting in production:**

```python
# Prevent abuse
from cascadeflow import CascadeAgent

agent = CascadeAgent(models=models)
# Add rate limiting middleware
```

#### Monitoring

**Monitor for unusual activity:**
- Unexpected API costs
- High volume of requests
- Failed authentication attempts
- Error rate spikes

### For Contributors

If you're contributing to CascadeFlow:

#### Code Review

- All code must be reviewed before merging
- Security-sensitive code requires additional review
- Use automated security scanning tools

#### Dependencies

- Keep dependencies up to date
- Review dependency security advisories
- Use `pip-audit` to check for vulnerabilities

```bash
pip install pip-audit
pip-audit
```

#### Testing

- Write tests for security-critical functionality
- Test with invalid/malicious inputs
- Test authentication and authorization

---

## Known Security Considerations

### API Key Exposure

**Risk:** API keys could be exposed in logs, error messages, or version control.

**Mitigation:**
- Never log API keys
- Use environment variables
- Add `.env` to `.gitignore`
- Rotate keys if exposed

### Prompt Injection

**Risk:** Malicious users could craft prompts to bypass safety measures.

**Mitigation:**
- Validate and sanitize all user inputs
- Implement content filtering
- Use system prompts to set boundaries
- Monitor for suspicious patterns

### Cost Control

**Risk:** Malicious users could cause excessive API costs.

**Mitigation:**
- Implement budget limits per user/session
- Set up cost alerts
- Use rate limiting
- Monitor usage patterns

```python
from cascadeflow import UserTier

# Set budget limits
tier = UserTier(
    name="free",
    max_budget=0.01,  # $0.01 limit
    quality_threshold=0.6
)
```

### Data Privacy

**Risk:** Sensitive data could be sent to external APIs.

**Mitigation:**
- Don't send PII without user consent
- Use local models (Ollama) for sensitive data
- Review provider privacy policies
- Implement data sanitization

### Dependency Vulnerabilities

**Risk:** Third-party dependencies may have security vulnerabilities.

**Mitigation:**
- Regular dependency updates
- Use `pip-audit` for scanning
- Pin dependency versions
- Review security advisories

---

## Scope

### In Scope

Security issues related to:
- API key exposure
- Authentication/authorization bypass
- Injection vulnerabilities (prompt injection, code injection)
- Data leakage
- Denial of Service (DoS)
- Dependency vulnerabilities
- Cryptographic weaknesses

### Out of Scope

The following are generally considered out of scope:
- Issues in third-party provider APIs (report to the provider)
- Social engineering attacks
- Physical security issues
- Issues requiring local system access
- Theoretical attacks without proof of concept
- Issues in unsupported versions

---

## Security Tools

We use the following tools to maintain security:

- **GitHub Security Scanning:** Automated vulnerability detection
- **Dependabot:** Dependency update alerts
- **pip-audit:** Python package vulnerability scanning
- **Bandit:** Python security linter
- **Safety:** Checks for known security vulnerabilities

### Running Security Checks

Contributors can run security checks locally:

```bash
# Install security tools
pip install bandit safety pip-audit

# Run security scan
bandit -r cascadeflow/

# Check for vulnerable dependencies
safety check
pip-audit

# Check for secrets in code
git secrets --scan
```

---

## Security Resources

### External Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Python Security Best Practices](https://python.readthedocs.io/en/stable/library/security_warnings.html)
- [OpenAI Security Best Practices](https://platform.openai.com/docs/guides/safety-best-practices)
- [Anthropic Safety Guidelines](https://www.anthropic.com/safety)

### Stay Informed

- Watch this repository for security updates
- Subscribe to security advisories
- Follow our security blog (coming soon)

---

## Contact

For security concerns:
- **Email:** security@lemony.ai
- **PGP Key:** Available upon request

For general questions:
- **Email:** hello@lemony.ai
- **GitHub Issues:** For non-security bugs

---

## Acknowledgments

We appreciate the security research community's efforts to keep CascadeFlow secure. Security researchers who responsibly disclose vulnerabilities will be acknowledged in our security advisories (unless they prefer to remain anonymous).

### Hall of Fame

Security researchers who have helped improve CascadeFlow security:

- _No vulnerabilities reported yet_

---

## Policy Updates

This security policy may be updated from time to time. Please check back regularly for updates.

**Last Updated:** October 2025  
**Version:** 1.0