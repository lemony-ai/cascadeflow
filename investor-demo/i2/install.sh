#!/bin/bash
# CascadeFlow Investor Demo - Ink CLI Version (Claude Code)
# curl -fsSL https://i2.buehrle.io/install.sh | bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

DEMO_URL="https://i2.buehrle.io/demo-ink.tar.gz"
INSTALL_DIR="${CASCADEFLOW_DIR:-$HOME/.cascadeflow-demo-ink}"

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}   ${BOLD}CascadeFlow${NC} - Ink CLI Demo (Built by Claude Code)      ${CYAN}║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check for Node.js
check_node() {
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
        if [ "$NODE_VERSION" -ge 18 ]; then
            echo -e "  ${GREEN}✓${NC} Node.js $(node -v) found"
            return 0
        fi
    fi
    return 1
}

install_node() {
    echo -e "  ${CYAN}⚡${NC} Installing Node.js via fnm..."
    curl -fsSL https://fnm.vercel.app/install | bash -s -- --skip-shell
    export PATH="$HOME/.local/share/fnm:$PATH"
    eval "$(fnm env)"
    fnm install 20
    fnm use 20
    echo -e "  ${GREEN}✓${NC} Node.js installed"
}

download_demo() {
    echo -e "  ${CYAN}↓${NC} Downloading Ink CLI demo..."
    mkdir -p "$INSTALL_DIR"
    curl -fsSL "$DEMO_URL" | tar -xz -C "$INSTALL_DIR" --strip-components=1
    echo -e "  ${GREEN}✓${NC} Demo downloaded"
}

install_deps() {
    echo -e "  ${CYAN}◐${NC} Installing dependencies..."
    cd "$INSTALL_DIR"
    npm install --silent 2>/dev/null
    echo -e "  ${GREEN}✓${NC} Dependencies ready"
}

run_demo() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${BOLD}Launching interactive Ink CLI...${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    cd "$INSTALL_DIR"
    node dist/index.js
}

main() {
    if ! check_node; then
        install_node
    fi
    download_demo
    install_deps
    run_demo
}

main
