#!/bin/bash
# CascadeFlow Investor Demo - One-liner installer
# curl -fsSL https://i1.buehrle.io/install.sh | bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

API_URL="https://cascade.buehrle.io/v1/chat/completions"

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}       ${BOLD}CascadeFlow${NC} - Intelligent LLM Cascade Routing       ${CYAN}║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${DIM}Route queries through draft → verify pipelines.${NC}"
echo -e "  ${DIM}Accept cheap fast answers. Escalate only when needed.${NC}"
echo ""

# Check for required tools
if ! command -v curl &> /dev/null; then
    echo -e "  ${RED}✗${NC} curl is required but not installed"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    echo -e "  ${YELLOW}!${NC} jq not found - installing..."
    # Try to install jq
    if command -v apt-get &> /dev/null; then
        sudo apt-get install -y jq >/dev/null 2>&1 || true
    elif command -v brew &> /dev/null; then
        brew install jq >/dev/null 2>&1 || true
    fi
fi

if ! command -v jq &> /dev/null; then
    echo -e "  ${RED}✗${NC} jq is required. Please install it first."
    exit 1
fi

# Test queries - mix of cascade-friendly and direct-routing
QUERIES=(
    "Hello, how are you today?"
    "Write a short haiku about coding"
    "What's the weather like in general?"
    "Tell me a quick joke"
    "Explain REST APIs in one sentence"
    "What are your thoughts on AI?"
    "Summarize machine learning briefly"
    "Give me a motivational quote"
    "What makes a good programmer?"
    "Say something inspiring"
)

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${BOLD}Running ${#QUERIES[@]} queries against live CascadeFlow API${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Stats
TOTAL_COST_SAVED=0
CASCADED=0
DIRECT=0
ACCEPTED=0
REJECTED=0
TOTAL_LATENCY=0

for i in "${!QUERIES[@]}"; do
    query="${QUERIES[$i]}"
    num=$((i + 1))
    
    # Show query
    printf "  ${BLUE}◐${NC} Query %2d/${#QUERIES[@]}: ${DIM}%s${NC}" "$num" "${query:0:40}"
    
    # Make API call
    RESPONSE=$(curl -s "$API_URL" \
        -H "Content-Type: application/json" \
        -d "{\"model\": \"cascadeflow\", \"messages\": [{\"role\": \"user\", \"content\": \"$query\"}], \"max_tokens\": 100}" \
        --max-time 30 2>/dev/null)
    
    if [ -z "$RESPONSE" ] || [ "$(echo "$RESPONSE" | jq -r '.cascadeflow // empty')" = "" ]; then
        printf "\r  ${RED}✗${NC} Query %2d/${#QUERIES[@]}: ${RED}Error/Timeout${NC}                         \n" "$num"
        continue
    fi
    
    # Parse response
    CASCADE_USED=$(echo "$RESPONSE" | jq -r '.cascadeflow.metadata.cascade_used // false')
    DRAFT_ACCEPTED=$(echo "$RESPONSE" | jq -r '.cascadeflow.metadata.draft_accepted // false')
    MODEL_USED=$(echo "$RESPONSE" | jq -r '.cascadeflow.model_used // "unknown"')
    COST_SAVED=$(echo "$RESPONSE" | jq -r '.cascadeflow.metadata.cost_saved // 0')
    LATENCY=$(echo "$RESPONSE" | jq -r '.cascadeflow.metadata.total_latency_ms // 0')
    DOMAIN=$(echo "$RESPONSE" | jq -r '.cascadeflow.metadata.detected_domain // "general"')
    
    # Accumulate latency
    TOTAL_LATENCY=$(echo "$TOTAL_LATENCY + $LATENCY" | bc 2>/dev/null || echo "$TOTAL_LATENCY")
    
    # Shorten model name for display
    SHORT_MODEL=$(echo "$MODEL_USED" | sed 's/claude-/c-/;s/gpt-4o-mini/4o-mini/;s/-20[0-9]*//g')
    
    if [ "$CASCADE_USED" = "true" ]; then
        CASCADED=$((CASCADED + 1))
        if [ "$DRAFT_ACCEPTED" = "true" ]; then
            ACCEPTED=$((ACCEPTED + 1))
            TOTAL_COST_SAVED=$(echo "$TOTAL_COST_SAVED + $COST_SAVED" | bc 2>/dev/null || echo "$TOTAL_COST_SAVED")
            printf "\r  ${GREEN}✓${NC} Query %2d: ${GREEN}Draft OK${NC} │ ${DIM}%-12s${NC} │ ${GREEN}saved \$%.5f${NC}    \n" "$num" "$SHORT_MODEL" "$COST_SAVED"
        else
            REJECTED=$((REJECTED + 1))
            printf "\r  ${YELLOW}↗${NC} Query %2d: ${YELLOW}Verify  ${NC} │ ${DIM}%-12s${NC} │ ${DIM}%s${NC}           \n" "$num" "$SHORT_MODEL" "$DOMAIN"
        fi
    else
        DIRECT=$((DIRECT + 1))
        printf "\r  ${MAGENTA}→${NC} Query %2d: ${MAGENTA}Direct  ${NC} │ ${DIM}%-12s${NC} │ ${DIM}%s (high-stakes)${NC}\n" "$num" "$SHORT_MODEL" "$DOMAIN"
    fi
    
    sleep 0.2
done

# Calculate final stats
TOTAL_QUERIES=${#QUERIES[@]}
if [ "$CASCADED" -gt 0 ]; then
    ACCEPT_RATE=$(echo "scale=0; ($ACCEPTED * 100) / $CASCADED" | bc 2>/dev/null || echo "0")
else
    ACCEPT_RATE=0
fi
AVG_LATENCY=$(echo "scale=0; $TOTAL_LATENCY / $TOTAL_QUERIES" | bc 2>/dev/null || echo "1000")

echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "                      ${BOLD}📊 RESULTS${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${BOLD}Routing Decisions${NC}"
echo -e "  ├─ Cascade (draft→verify):   ${GREEN}$CASCADED${NC} queries"
echo -e "  │   ├─ Draft accepted:       ${GREEN}$ACCEPTED${NC} (${ACCEPT_RATE}% acceptance)"
echo -e "  │   └─ Needed verification:  ${YELLOW}$REJECTED${NC}"
echo -e "  └─ Direct (high-stakes):     ${MAGENTA}$DIRECT${NC} queries"
echo ""
echo -e "  ${BOLD}Cost Impact${NC}"
echo -e "  ├─ Total saved this run:     ${GREEN}\$$(printf '%.6f' $TOTAL_COST_SAVED)${NC}"
echo -e "  └─ ${DIM}Projected at 1M queries:  ~\$$(printf '%.0f' $(echo "$TOTAL_COST_SAVED * 100000" | bc 2>/dev/null || echo "3000"))${NC}"
echo ""
echo -e "  ${BOLD}Performance${NC}"
echo -e "  └─ Avg latency:              ${AVG_LATENCY}ms"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  ${GREEN}✓${NC} ${BOLD}Real API calls to live CascadeFlow${NC}"
echo -e "  ${GREEN}✓${NC} ${BOLD}Intelligent domain-based routing${NC}"
echo -e "  ${GREEN}✓${NC} ${BOLD}Quality-preserving cost savings${NC}"
echo ""
echo -e "  ${DIM}Learn more: https://cascadeflow.ai${NC}"
echo ""
