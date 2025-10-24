#!/bin/bash
# CascadeFlow Repository Configuration Script
# Run this script to configure GitHub repository for launch

set -e  # Exit on error

echo "🚀 Configuring CascadeFlow repository for launch..."
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to prompt user
confirm() {
    read -p "$1 (y/n) " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# 1. Add repository topics
echo -e "${YELLOW}📌 Adding repository topics for discoverability...${NC}"
if confirm "Add repository topics?"; then
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
    echo -e "${GREEN}✅ Topics added${NC}"
fi

# 2. Set homepage URL
echo ""
echo -e "${YELLOW}🏠 Setting homepage URL...${NC}"
if confirm "Set homepage to https://docs.lemony.ai/cascadeflow?"; then
    gh repo edit lemony-ai/CascadeFlow --homepage "https://docs.lemony.ai/cascadeflow"
    echo -e "${GREEN}✅ Homepage URL set${NC}"
fi

# 3. Enable GitHub Discussions
echo ""
echo -e "${YELLOW}💬 Enabling GitHub Discussions for community...${NC}"
if confirm "Enable GitHub Discussions?"; then
    gh repo edit lemony-ai/CascadeFlow --enable-discussions
    echo -e "${GREEN}✅ Discussions enabled${NC}"
fi

# 4. Disable Wiki (use /docs instead)
echo ""
echo -e "${YELLOW}📚 Disabling Wiki (using /docs folder instead)...${NC}"
if confirm "Disable Wiki?"; then
    gh repo edit lemony-ai/CascadeFlow --enable-wiki=false
    echo -e "${GREEN}✅ Wiki disabled${NC}"
fi

# 5. Keep Projects enabled
echo ""
echo -e "${GREEN}✅ Projects already enabled (keep for roadmap transparency)${NC}"

# 6. Make repository public (IMPORTANT - do this last!)
echo ""
echo -e "${YELLOW}⚠️  MAKE REPOSITORY PUBLIC${NC}"
echo "This will make your repository visible to everyone!"
echo "Make sure you've:"
echo "  - Reviewed all code and removed any secrets"
echo "  - Published packages to PyPI and npm"
echo "  - Created GitHub release"
echo "  - Prepared launch announcement"
echo ""
if confirm "Make repository PUBLIC? (THIS CANNOT BE EASILY UNDONE)"; then
    gh repo edit lemony-ai/CascadeFlow --visibility public
    echo -e "${GREEN}✅ Repository is now PUBLIC! 🎉${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Repository configuration complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Add GitHub secrets (PYPI_API_TOKEN, NPM_TOKEN)"
echo "2. Publish packages to PyPI and npm"
echo "3. Create v0.1.0 release"
echo "4. Set up GitHub Discussions categories"
echo "5. Launch announcement!"
echo ""
echo "See .github/LAUNCH_CHECKLIST.md for full details."
