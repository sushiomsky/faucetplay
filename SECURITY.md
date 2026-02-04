# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability, please send an email to:
- **Email**: [your-email@example.com]

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### What to Expect

- **Response Time**: Within 48 hours
- **Updates**: Every 5-7 days on progress
- **Resolution**: We aim to patch critical issues within 7 days

## Security Best Practices

### For Users

1. **Never share your API key or cookie**
2. **Use strong passwords** for your DuckDice account
3. **Enable 2FA** on your DuckDice account
4. **Review withdrawal addresses** before enabling auto-withdrawal
5. **Keep the bot updated** to the latest version
6. **Use antivirus software** on Windows

### For Developers

1. **Never commit secrets** (API keys, cookies) to the repository
2. **Use encrypted storage** for sensitive data (already implemented)
3. **Validate all user inputs**
4. **Use HTTPS** for all API calls
5. **Review dependencies** regularly for vulnerabilities

## Security Features

- ✅ Encrypted credential storage (using `cryptography` library)
- ✅ Secure file permissions (Unix/Linux/Mac)
- ✅ No hardcoded credentials
- ✅ Input validation
- ✅ HTTPS API calls only

## Known Security Considerations

1. **Browser Cookie**: Required for faucet claiming. Cookie may expire and need updating.
2. **API Key**: Keep your API key private. Treat it like a password.
3. **Withdrawal**: Always verify withdrawal addresses before enabling auto-withdrawal.

## Vulnerability Disclosure

We follow responsible disclosure:
1. Reporter notifies us privately
2. We confirm and develop a fix
3. Fix is released
4. Public disclosure after users have time to update (typically 30 days)

---

Thank you for helping keep FaucetPlay Bot secure! 🔒
