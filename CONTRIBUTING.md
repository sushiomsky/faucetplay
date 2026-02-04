# Contributing to FaucetPlay Bot

Thank you for your interest in contributing to FaucetPlay Bot! 🎉

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version)
- Relevant logs/screenshots

### Suggesting Features

We welcome feature suggestions! Please:
- Check if the feature is already in the ROADMAP.md
- Open an issue with detailed description
- Explain the use case and benefits

### Code Contributions

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow existing code style
   - Add comments for complex logic
   - Update documentation if needed

4. **Test your changes**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Test the bot
   python faucetplay.py
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add: brief description of your changes"
   ```
   
   Use conventional commits:
   - `Add:` for new features
   - `Fix:` for bug fixes
   - `Update:` for improvements
   - `Docs:` for documentation
   - `Refactor:` for code refactoring

6. **Push to your fork**
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request**
   - Describe what you changed and why
   - Reference any related issues
   - Wait for review

## Development Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/faucetplay.git
cd faucetplay

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the bot
python faucetplay.py
```

## Code Style

- Use meaningful variable names
- Keep functions focused and small
- Add docstrings to functions/classes
- Follow PEP 8 style guide
- Use type hints where appropriate

## Testing

Before submitting:
- Test on your local machine
- Verify no console errors
- Check that existing features still work
- Test on multiple currencies if possible

## Questions?

Feel free to open an issue for any questions or clarifications!

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Help others learn and grow
- Keep discussions focused and professional

---

Thank you for contributing! 🙏
