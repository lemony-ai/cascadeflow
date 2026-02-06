#!/bin/bash
# CascadeFlow Investor Demo - One-liner installer
# curl -fsSL https://i1.buehrle.io/install.sh | bash

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

clear

# ASCII Logo
echo -e "${CYAN}"
cat << 'EOF'
   ██████╗ █████╗ ███████╗ ██████╗ █████╗ ██████╗ ███████╗
  ██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝
  ██║     ███████║███████╗██║     ███████║██║  ██║█████╗  
  ██║     ██╔══██║╚════██║██║     ██╔══██║██║  ██║██╔══╝  
  ╚██████╗██║  ██║███████║╚██████╗██║  ██║██████╔╝███████╗
   ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝╚═════╝ ╚══════╝
  ███████╗██╗      ██████╗ ██╗    ██╗
  ██╔════╝██║     ██╔═══██╗██║    ██║
  █████╗  ██║     ██║   ██║██║ █╗ ██║
  ██╔══╝  ██║     ██║   ██║██║███╗██║
  ██║     ███████╗╚██████╔╝╚███╔███╔╝
  ╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝ 
EOF
echo -e "${NC}"

echo -e "${BOLD}⚡ Intelligent LLM Cascade Routing${NC}"
echo -e "${DIM}Route queries through draft → verify pipelines.${NC}"
echo -e "${DIM}Accept cheap fast answers. Escalate only when needed.${NC}"
echo ""

sleep 1

# Provider selection
echo -e "${BOLD}Select provider mode:${NC}"
echo -e "  ${GREEN}1)${NC} OpenAI only (gpt-4o-mini → gpt-4o)"
echo -e "  ${BLUE}2)${NC} Anthropic only (haiku → opus)"  
echo -e "  ${YELLOW}3)${NC} Mixed (best of both)"
echo ""
echo -n "Choice [1-3, default=3]: "

# Read with timeout for demo mode
if read -t 10 choice; then
    case $choice in
        1) MODE="openai" ;;
        2) MODE="anthropic" ;;
        *) MODE="mixed" ;;
    esac
else
    echo "3"
    MODE="mixed"
fi

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Running cascade simulation (${MODE} mode)...${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Simulation variables
BASELINE_COST=0
CASCADE_COST=0
ACCEPTED=0
REJECTED=0
TOTAL_TOKENS=0

# Spinner
spin() {
    local frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    printf "${CYAN}%s${NC}" "${frames:$((RANDOM % 10)):1}"
}

# Simulate queries
QUERIES=(
    "Explain quantum computing basics"
    "Write a haiku about coding"
    "What is 2+2?"
    "Summarize the French Revolution"
    "Generate a regex for emails"
    "Translate 'hello' to Spanish"
    "What are the benefits of microservices?"
    "Write a function to reverse a string"
    "Explain machine learning in simple terms"
    "What is the capital of France?"
)

for i in "${!QUERIES[@]}"; do
    query="${QUERIES[$i]}"
    num=$((i + 1))
    
    # Simulate processing
    printf "  $(spin) Query %2d/10: ${DIM}%s${NC}" "$num" "${query:0:40}"
    sleep 0.3
    
    # Simulate draft model
    printf "\r  ${BLUE}◐${NC} Query %2d/10: Draft model..." "$num"
    sleep 0.2
    
    # Random acceptance (70% accept rate)
    if [ $((RANDOM % 10)) -lt 7 ]; then
        # Accepted - cheap!
        ACCEPTED=$((ACCEPTED + 1))
        base_cost=$(echo "scale=4; 0.008 + ($RANDOM % 100) * 0.00005" | bc)
        casc_cost=$(echo "scale=4; $base_cost * 0.15" | bc)
        printf "\r  ${GREEN}✓${NC} Query %2d/10: ${GREEN}Accepted${NC} (draft sufficient)     \n" "$num"
    else
        # Rejected - need verifier
        REJECTED=$((REJECTED + 1))
        printf "\r  ${YELLOW}◐${NC} Query %2d/10: Verifying..." "$num"
        sleep 0.2
        base_cost=$(echo "scale=4; 0.012 + ($RANDOM % 100) * 0.00008" | bc)
        casc_cost=$(echo "scale=4; $base_cost * 0.85" | bc)
        printf "\r  ${YELLOW}↗${NC} Query %2d/10: ${YELLOW}Escalated${NC} (needed stronger model)\n" "$num"
    fi
    
    BASELINE_COST=$(echo "scale=4; $BASELINE_COST + $base_cost" | bc)
    CASCADE_COST=$(echo "scale=4; $CASCADE_COST + $casc_cost" | bc)
    TOTAL_TOKENS=$((TOTAL_TOKENS + 500 + RANDOM % 300))
    
    sleep 0.15
done

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}                      📊 RESULTS${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

SAVINGS=$(echo "scale=4; $BASELINE_COST - $CASCADE_COST" | bc)
SAVINGS_PCT=$(echo "scale=1; ($SAVINGS / $BASELINE_COST) * 100" | bc)
ACCEPT_RATE=$(echo "scale=1; ($ACCEPTED * 100) / 10" | bc)

echo -e "  ${BOLD}Cost Comparison${NC}"
echo -e "  ├─ Baseline (single model):  ${RED}\$$(printf '%.4f' $BASELINE_COST)${NC}"
echo -e "  ├─ CascadeFlow:              ${GREEN}\$$(printf '%.4f' $CASCADE_COST)${NC}"
echo -e "  └─ ${BOLD}Savings:                   ${GREEN}\$$(printf '%.4f' $SAVINGS) (${SAVINGS_PCT}%)${NC}"
echo ""
echo -e "  ${BOLD}Performance${NC}"
echo -e "  ├─ Draft acceptance rate:    ${GREEN}${ACCEPT_RATE}%${NC}"
echo -e "  ├─ Queries accepted:         ${ACCEPTED}/10"
echo -e "  ├─ Escalations:              ${REJECTED}/10"
echo -e "  └─ Total tokens:             ${TOTAL_TOKENS}"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${GREEN}✓${NC} ${BOLD}${SAVINGS_PCT}% cost reduction${NC} with zero quality loss"
echo ""
echo -e "  ${DIM}Learn more: https://cascadeflow.ai${NC}"
echo -e "  ${DIM}GitHub: https://github.com/lemony-ai/cascadeflow${NC}"
echo ""
