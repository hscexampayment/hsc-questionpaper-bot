#!/bin/bash
set -e

REPO_URL="https://github.com/hscexampayment/hsc-questionpaper-bot.git"

echo "==> Configuring git..."
git config user.email "bot@replit.com"
git config user.name "Replit Agent"

echo "==> Setting remote with token..."
git remote set-url origin "https://${GITHUB_PERSONAL_ACCESS_TOKEN}@github.com/hscexampayment/hsc-questionpaper-bot.git" 2>/dev/null \
  || git remote add origin "https://${GITHUB_PERSONAL_ACCESS_TOKEN}@github.com/hscexampayment/hsc-questionpaper-bot.git"

echo "==> Staging all files..."
git add -A

echo "==> Committing..."
git diff --cached --quiet && echo "Nothing new to commit." || git commit -m "Add Telegram bot with referral, point, and rank systems"

echo "==> Pushing to GitHub..."
git push -u origin main

echo ""
echo "Done! Check your repo at: https://github.com/hscexampayment/hsc-questionpaper-bot"
