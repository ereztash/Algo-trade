#!/bin/bash

# Algo-Trade Repository Cleanup Script
# Generated: 2025-11-17
# Purpose: Clean cache files and prepare for branch cleanup

set -e

echo "🧹 Algo-Trade Repository Cleanup"
echo "=================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Count function
count_files() {
    find . -type "$1" -name "$2" 2>/dev/null | wc -l
}

# Phase 1: Cache Cleanup
echo "📦 Phase 1: Cleaning Python cache files"
echo "----------------------------------------"

echo -n "Finding __pycache__ directories... "
PYCACHE_COUNT=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l)
echo "${PYCACHE_COUNT} found"

if [ "$PYCACHE_COUNT" -gt 0 ]; then
    echo -n "Removing __pycache__ directories... "
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    echo -e "${GREEN}✓ Done${NC}"
else
    echo -e "${GREEN}✓ No __pycache__ directories found${NC}"
fi

echo -n "Finding *.pyc files... "
PYC_COUNT=$(find . -type f -name "*.pyc" 2>/dev/null | wc -l)
echo "${PYC_COUNT} found"

if [ "$PYC_COUNT" -gt 0 ]; then
    echo -n "Removing *.pyc files... "
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    echo -e "${GREEN}✓ Done${NC}"
else
    echo -e "${GREEN}✓ No .pyc files found${NC}"
fi

echo -n "Finding *.pyo files... "
PYO_COUNT=$(find . -type f -name "*.pyo" 2>/dev/null | wc -l)
echo "${PYO_COUNT} found"

if [ "$PYO_COUNT" -gt 0 ]; then
    echo -n "Removing *.pyo files... "
    find . -type f -name "*.pyo" -delete 2>/dev/null || true
    echo -e "${GREEN}✓ Done${NC}"
else
    echo -e "${GREEN}✓ No .pyo files found${NC}"
fi

echo ""

# Phase 2: Test Cache Cleanup (Optional)
echo "🧪 Phase 2: Test cache cleanup (optional)"
echo "----------------------------------------"

if [ -d ".pytest_cache" ]; then
    echo -n "Remove .pytest_cache? (y/N): "
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -rf .pytest_cache
        echo -e "${GREEN}✓ Removed .pytest_cache${NC}"
    else
        echo -e "${YELLOW}⊘ Skipped${NC}"
    fi
else
    echo -e "${GREEN}✓ No .pytest_cache found${NC}"
fi

if [ -d ".hypothesis" ]; then
    echo -n "Remove .hypothesis? (y/N): "
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -rf .hypothesis
        echo -e "${GREEN}✓ Removed .hypothesis${NC}"
    else
        echo -e "${YELLOW}⊘ Skipped${NC}"
    fi
else
    echo -e "${GREEN}✓ No .hypothesis found${NC}"
fi

echo ""

# Phase 3: Git Cleanup
echo "🌿 Phase 3: Git branch cleanup"
echo "----------------------------------------"

echo "Merged branches (safe to delete):"
git branch -r --merged origin/main 2>/dev/null | grep -v "main\|HEAD" | sed 's/origin\///' | while read -r branch; do
    echo "  - $branch"
done

echo ""
echo -e "${YELLOW}⚠️  WARNING: The following will DELETE merged remote branches!${NC}"
echo -n "Delete merged branches? (y/N): "
read -r response

if [[ "$response" =~ ^[Yy]$ ]]; then
    git branch -r --merged origin/main 2>/dev/null | grep -v "main\|HEAD" | sed 's/origin\///' | while read -r branch; do
        echo -n "Deleting $branch... "
        git push origin --delete "$branch" 2>/dev/null && echo -e "${GREEN}✓${NC}" || echo -e "${RED}✗${NC}"
    done
else
    echo -e "${YELLOW}⊘ Skipped branch deletion${NC}"
fi

echo ""

# Phase 4: Report unmerged branches
echo "📊 Phase 4: Unmerged branches report"
echo "----------------------------------------"

UNMERGED_COUNT=$(git branch -r --no-merged origin/main 2>/dev/null | grep -v "HEAD" | wc -l)
echo "Found $UNMERGED_COUNT unmerged branches:"
echo ""

git for-each-ref --sort=-committerdate refs/remotes/origin --format='%(committerdate:short) %(refname:short)' 2>/dev/null | \
    grep -v "/main" | head -10 | while read -r date branch; do
    echo "  $date - $branch"
done

echo ""
echo -e "${YELLOW}ℹ️  Review these branches manually using:${NC}"
echo "   git log --oneline <branch-name>"
echo "   git diff main...<branch-name>"
echo ""

# Phase 5: Check .gitignore
echo "📝 Phase 5: .gitignore validation"
echo "----------------------------------------"

GITIGNORE_ITEMS=(
    "__pycache__/"
    "*.py[cod]"
    ".pytest_cache/"
    ".hypothesis/"
    "*.env"
    "*.pem"
    "*.key"
)

echo "Checking .gitignore for essential entries:"
for item in "${GITIGNORE_ITEMS[@]}"; do
    if grep -q "$item" .gitignore 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $item"
    else
        echo -e "  ${RED}✗${NC} $item ${YELLOW}(MISSING!)${NC}"
    fi
done

echo ""

# Summary
echo "✅ Cleanup Complete!"
echo "===================="
echo ""
echo "Summary:"
echo "  - Removed $PYCACHE_COUNT __pycache__ directories"
echo "  - Removed $PYC_COUNT .pyc files"
echo "  - Removed $PYO_COUNT .pyo files"
echo "  - Found $UNMERGED_COUNT unmerged branches"
echo ""
echo "Next steps:"
echo "  1. Review unmerged branches: REPOSITORY_USER_GUIDE.md"
echo "  2. Run tests: pytest tests/ -v"
echo "  3. Update .gitignore if items are missing"
echo ""
