#!/bin/bash

# GitHub Repository Setup Script for FaucetPlay Bot
# This script helps you push your repository to GitHub

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║        🎰 FaucetPlay Bot - GitHub Setup Helper              ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if gh CLI is installed
if command -v gh &> /dev/null; then
    echo "✅ GitHub CLI (gh) detected"
    echo ""
    echo "Option 1: Create repository using GitHub CLI"
    echo "==========================================="
    echo "Run these commands:"
    echo ""
    echo "  cd /Users/tempor/Documents/faucetplay"
    echo "  gh auth login"
    echo "  gh repo create faucetplay --public --source=. --remote=origin --push"
    echo ""
else
    echo "⚠️  GitHub CLI (gh) not found"
    echo ""
fi

echo "Option 2: Create repository manually on GitHub"
echo "=============================================="
echo ""
echo "1. Go to: https://github.com/new"
echo ""
echo "2. Repository settings:"
echo "   - Name: faucetplay"
echo "   - Description: Automated DuckDice Faucet Claiming & Betting Bot"
echo "   - Visibility: Public (or Private)"
echo "   - Do NOT initialize with README (we already have one)"
echo ""
echo "3. After creating, run these commands:"
echo ""
echo "   cd /Users/tempor/Documents/faucetplay"
echo "   git remote add origin https://github.com/YOUR_USERNAME/faucetplay.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "4. Enable GitHub Copilot:"
echo "   - Go to repository Settings"
echo "   - Navigate to 'Copilot' section"
echo "   - Enable Copilot for this repository"
echo ""
echo "═════════════════════════════════════════════════════════════"
echo ""
echo "📊 Current Repository Status"
echo "═════════════════════════════════════════════════════════════"
cd /Users/tempor/Documents/faucetplay
echo "Branch: $(git branch --show-current)"
echo "Commits: $(git rev-list --count HEAD)"
echo "Files: $(git ls-files | wc -l | tr -d ' ')"
echo ""
echo "Recent commits:"
git log --oneline -3
echo ""
echo "═════════════════════════════════════════════════════════════"
echo "✅ Repository is ready to be pushed to GitHub!"
echo "═════════════════════════════════════════════════════════════"
