#!/bin/bash

# Algo-Trade Branch Analysis Script
# Generated: 2025-11-17
# Purpose: Detailed analysis of all branches

set -e

echo "🔍 Algo-Trade Branch Analysis"
echo "=============================="
echo ""

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"
echo ""

# Section 1: Merged branches
echo "✅ MERGED BRANCHES (can be deleted)"
echo "-----------------------------------"
git branch -r --merged origin/main 2>/dev/null | grep -v "main\|HEAD" | sed 's/origin\///' | nl
echo ""

# Section 2: Unmerged branches by category
echo "🔄 UNMERGED BRANCHES (by category)"
echo "-----------------------------------"
echo ""

echo "📚 Documentation/README (6):"
git branch -r --no-merged origin/main 2>/dev/null | grep -E "explore-repo|update-readme|update-hebrew|language-support|gdt-trading" | sed 's/origin\//  - /'
echo ""

echo "🔒 Security/Secrets (4):"
git branch -r --no-merged origin/main 2>/dev/null | grep -E "security|secrets|secure-secrets" | sed 's/origin\//  - /'
echo ""

echo "🔧 Monitoring/Observability (2):"
git branch -r --no-merged origin/main 2>/dev/null | grep -E "monitoring" | sed 's/origin\//  - /'
echo ""

echo "🐳 Infrastructure/Docker (4):"
git branch -r --no-merged origin/main 2>/dev/null | grep -E "docker|kafka|3plane" | sed 's/origin\//  - /'
echo ""

echo "📈 IBKR Integration (2):"
git branch -r --no-merged origin/main 2>/dev/null | grep -E "ibkr.*integration|ibkr.*execution" | sed 's/origin\//  - /'
echo ""

echo "🧪 Testing (2):"
git branch -r --no-merged origin/main 2>/dev/null | grep -E "resilience-tests|expand-test|test-coverage" | sed 's/origin\//  - /'
echo ""

echo "🚀 Deployment/Environment (2):"
git branch -r --no-merged origin/main 2>/dev/null | grep -E "paper-trading|migrate-artifact" | sed 's/origin\//  - /'
echo ""

echo "🎯 Active Work (2):"
git branch -r --no-merged origin/main 2>/dev/null | grep -E "order-lifecycle|secrets-management-docs" | sed 's/origin\//  - /'
echo ""

echo "🔧 Miscellaneous (5):"
git branch -r --no-merged origin/main 2>/dev/null | grep -E "create-missing|fix-todo|optimize-performance|define-message|qa-readiness" | sed 's/origin\//  - /'
echo ""

# Section 3: Branch age analysis
echo "📅 BRANCH AGE ANALYSIS (Top 10 oldest)"
echo "--------------------------------------"
git for-each-ref --sort=committerdate refs/remotes/origin --format='%(committerdate:short) %(refname:short)' | grep -v "/main" | head -10
echo ""

# Section 4: Branch size analysis
echo "📊 BRANCH DIVERGENCE FROM MAIN"
echo "-------------------------------"
git branch -r --no-merged origin/main 2>/dev/null | grep -v "HEAD" | head -10 | while read -r branch; do
    branch_name=$(echo "$branch" | sed 's/origin\///')
    commits_ahead=$(git rev-list --count origin/main..${branch} 2>/dev/null || echo "?")
    commits_behind=$(git rev-list --count ${branch}..origin/main 2>/dev/null || echo "?")
    echo "  $branch_name: +$commits_ahead commits | -$commits_behind behind main"
done
echo ""

# Section 5: Recommendations
echo "💡 RECOMMENDATIONS"
echo "------------------"
echo ""

echo "🗑️  DELETE IMMEDIATELY (3 merged branches):"
git branch -r --merged origin/main 2>/dev/null | grep -v "main\|HEAD" | sed 's/origin\///' | while read -r branch; do
    echo "   git push origin --delete $branch"
done
echo ""

echo "⚠️  REVIEW FOR DELETION (probably obsolete):"
echo "   Documentation branches (6) - likely superseded by current docs"
echo "   Old monitoring branches (2) - check if work moved elsewhere"
echo "   Duplicate security branches (3) - keep only 'secrets-management-docs'"
echo ""

echo "✅ KEEP (active work):"
echo "   - claude/order-lifecycle-tests-01E45Pij5YY8x1ZvA3My36v8 (current)"
echo "   - claude/secrets-management-docs-019SAdCDfp6mQPwKn4rWfxqN (recent)"
echo ""

echo "❓ INVESTIGATE (potentially duplicate):"
echo "   - Multiple IBKR integration branches (2) - may overlap with order-lifecycle"
echo "   - Multiple testing branches (2) - may overlap with order-lifecycle chaos tests"
echo "   - Infrastructure branches (4) - verify if work completed elsewhere"
echo ""

# Section 6: Detailed branch info function
echo "🔧 DETAILED ANALYSIS COMMANDS"
echo "-----------------------------"
echo ""
echo "For detailed analysis of a specific branch, run:"
echo "  git log --oneline --graph origin/main..origin/<branch-name>"
echo "  git diff --stat origin/main...origin/<branch-name>"
echo ""
echo "To see what files changed:"
echo "  git diff --name-status origin/main...origin/<branch-name>"
echo ""
echo "To see commit messages:"
echo "  git log --oneline origin/<branch-name> --not origin/main"
echo ""
