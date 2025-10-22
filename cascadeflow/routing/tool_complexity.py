"""
Tool Call Complexity Analysis

Analyzes complexity of TOOL CALLS specifically using 8 research-backed indicators.
NOT used for text queries (use cascadeflow.complexity for that).

This module serves TWO purposes:
1. PRIMARY: Pre-routing decisions (CASCADE vs DIRECT)
2. SECONDARY: Adaptive quality thresholds (reused by quality/tool_validator.py)

Based on research:
- Berkeley Function Calling Leaderboard (BFCL)
- Gorilla OpenFunctions benchmark
- Multi-step tool calling papers

Usage:
    from cascadeflow.routing import ToolComplexityAnalyzer

    analyzer = ToolComplexityAnalyzer()
    result = analyzer.analyze_tool_call(
        query="What's the weather in Paris?",
        tools=[weather_tool]
    )
    # result.complexity_level = ToolComplexityLevel.TRIVIAL
    # result.score = 0.0
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ToolComplexityLevel(Enum):
    """
    5 complexity clusters for tool calls.

    Each cluster maps to a routing strategy and quality threshold:
    - TRIVIAL (0-3):   CASCADE with 0.70 threshold
    - SIMPLE (3-6):    CASCADE with 0.75 threshold
    - MODERATE (6-9):  CASCADE with 0.85 threshold
    - HARD (9-13):     DIRECT to large model
    - EXPERT (13+):    DIRECT to large model
    """

    TRIVIAL = "trivial"  # 0-3:   Single tool, clear params
    SIMPLE = "simple"  # 3-6:   Single tool, might need inference
    MODERATE = "moderate"  # 6-9:   Maybe 2 tools, some reasoning
    HARD = "hard"  # 9-13:  Multi-step OR complex reasoning
    EXPERT = "expert"  # 13+:   Multi-step AND complex reasoning


@dataclass
class ToolAnalysisResult:
    """
    Result of tool call complexity analysis.

    Contains complexity level, score, triggered signals, and reasoning.
    Used by both router (for decisions) and validator (for thresholds).
    """

    complexity_level: ToolComplexityLevel
    score: float
    signals: dict[str, bool] = field(default_factory=dict)
    reasoning: list[str] = field(default_factory=list)
    indicator_scores: dict[str, float] = field(default_factory=dict)

    def __str__(self) -> str:
        """Human-readable summary."""
        return (
            f"ToolComplexity(level={self.complexity_level.value}, "
            f"score={self.score:.1f}, signals={sum(self.signals.values())})"
        )


class ToolComplexityAnalyzer:
    """
    Analyzes tool call complexity using 8 indicators.

    ONLY for tool calls - use cascadeflow.complexity for text queries.

    8 Indicators (Research-Backed):
    1. Multi-step reasoning: +8.0 (CRITICAL - requires sequential calls)
    2. Ambiguous parameters: +4.0 (needs interpretation/inference)
    3. Nested structures: +3.0 (complex nested objects/arrays)
    4. Tool selection difficulty: +2.0 (many similar tools)
    5. Context requirements: +2.5 (needs conversation history)
    6. Conditional logic: +2.0 (if-then reasoning)
    7. Iterative operations: +1.5 (loops/repeated operations)
    8. High parameter count: +1.0 (many parameters to fill)

    Score → Cluster Mapping:
    - 0-3:   TRIVIAL   (single tool, clear params)
    - 3-6:   SIMPLE    (single tool, some inference)
    - 6-9:   MODERATE  (maybe 2 tools, reasoning)
    - 9-13:  HARD      (multi-step OR complex)
    - 13+:   EXPERT    (multi-step AND complex)

    Reused by quality/tool_validator.py for adaptive thresholds:
    - TRIVIAL:  0.70 (more lenient)
    - SIMPLE:   0.75
    - MODERATE: 0.85 (more strict)
    """

    # Multi-step indicators (keywords suggesting sequential operations)
    MULTI_STEP_KEYWORDS = {
        "then",
        "after",
        "next",
        "following",
        "once",
        "subsequent",
        "first",
        "second",
        "finally",
        "before",
        "and then",
        "sequence",
        "step",
        "stage",
        "phase",
        "process",
    }

    # Conditional logic indicators
    CONDITIONAL_KEYWORDS = {
        "if",
        "when",
        "unless",
        "only if",
        "in case",
        "provided",
        "depending on",
        "based on",
        "according to",
        "whether",
        "should",
        "would",
        "could",
        "might",
    }

    # Iterative operation indicators
    ITERATIVE_KEYWORDS = {
        "all",
        "each",
        "every",
        "for each",
        "iterate",
        "loop",
        "multiple",
        "several",
        "various",
        "compare",
        "across",
        "between",
        "among",
    }

    # Ambiguity indicators (vague/uncertain language)
    AMBIGUOUS_KEYWORDS = {
        "appropriate",
        "relevant",
        "best",
        "optimal",
        "suitable",
        "related",
        "similar",
        "like",
        "about",
        "around",
        "roughly",
        "approximately",
        "recent",
        "latest",
        "current",
    }

    def __init__(
        self,
        multi_step_weight: float = 8.0,
        ambiguous_weight: float = 4.0,
        nested_weight: float = 3.0,
        tool_selection_weight: float = 2.0,
        context_weight: float = 2.5,
        conditional_weight: float = 2.0,
        iterative_weight: float = 1.5,
        parameter_weight: float = 1.0,
    ):
        """
        Initialize analyzer with customizable weights.

        Args:
            multi_step_weight: Weight for multi-step reasoning (default: 8.0)
            ambiguous_weight: Weight for ambiguous parameters (default: 4.0)
            nested_weight: Weight for nested structures (default: 3.0)
            tool_selection_weight: Weight for tool selection difficulty (default: 2.0)
            context_weight: Weight for context requirements (default: 2.5)
            conditional_weight: Weight for conditional logic (default: 2.0)
            iterative_weight: Weight for iterative operations (default: 1.5)
            parameter_weight: Weight for high parameter count (default: 1.0)
        """
        self.weights = {
            "multi_step": multi_step_weight,
            "ambiguous": ambiguous_weight,
            "nested": nested_weight,
            "tool_selection": tool_selection_weight,
            "context": context_weight,
            "conditional": conditional_weight,
            "iterative": iterative_weight,
            "parameter": parameter_weight,
        }

    def analyze_tool_call(
        self, query: str, tools: list[dict], context: Optional[dict] = None
    ) -> ToolAnalysisResult:
        """
        Analyze tool call complexity.

        Args:
            query: User query string
            tools: Available tools (REQUIRED)
            context: Optional conversation context

        Returns:
            ToolAnalysisResult with level, score, signals, reasoning

        Example:
            >>> analyzer = ToolComplexityAnalyzer()
            >>> result = analyzer.analyze_tool_call(
            ...     query="What's the weather in Paris?",
            ...     tools=[weather_tool]
            ... )
            >>> result.complexity_level
            ToolComplexityLevel.TRIVIAL
            >>> result.score
            0.0
        """
        if not tools:
            raise ValueError("tools parameter is required for tool complexity analysis")

        score = 0.0
        signals = {}
        reasoning = []
        indicator_scores = {}

        query_lower = query.lower()

        # ═══════════════════════════════════════════════════════
        # 1. Multi-Step Reasoning (CRITICAL: +8.0)
        # ═══════════════════════════════════════════════════════
        multi_step_detected, multi_step_score = self._detect_multi_step(query_lower, tools)
        if multi_step_detected:
            score += multi_step_score
            signals["multi_step"] = True
            reasoning.append(f"Multi-step reasoning detected (+{multi_step_score:.1f})")
            indicator_scores["multi_step"] = multi_step_score

        # ═══════════════════════════════════════════════════════
        # 2. Ambiguous Parameters (+4.0)
        # ═══════════════════════════════════════════════════════
        ambiguous_detected, ambiguous_score = self._detect_ambiguous_params(query_lower, tools)
        if ambiguous_detected:
            score += ambiguous_score
            signals["ambiguous_params"] = True
            reasoning.append(f"Ambiguous parameters detected (+{ambiguous_score:.1f})")
            indicator_scores["ambiguous_params"] = ambiguous_score

        # ═══════════════════════════════════════════════════════
        # 3. Nested Structures (+3.0)
        # ═══════════════════════════════════════════════════════
        nested_detected, nested_score = self._detect_nested_structures(query_lower, tools)
        if nested_detected:
            score += nested_score
            signals["nested_structures"] = True
            reasoning.append(f"Nested structures required (+{nested_score:.1f})")
            indicator_scores["nested_structures"] = nested_score

        # ═══════════════════════════════════════════════════════
        # 4. Tool Selection Difficulty (+2.0)
        # ═══════════════════════════════════════════════════════
        selection_detected, selection_score = self._detect_tool_selection_difficulty(
            query_lower, tools
        )
        if selection_detected:
            score += selection_score
            signals["tool_selection_difficulty"] = True
            reasoning.append(f"Tool selection difficulty (+{selection_score:.1f})")
            indicator_scores["tool_selection_difficulty"] = selection_score

        # ═══════════════════════════════════════════════════════
        # 5. Context Requirements (+2.5)
        # ═══════════════════════════════════════════════════════
        context_detected, context_score = self._detect_context_requirements(query_lower, context)
        if context_detected:
            score += context_score
            signals["context_requirements"] = True
            reasoning.append(f"Context requirements detected (+{context_score:.1f})")
            indicator_scores["context_requirements"] = context_score

        # ═══════════════════════════════════════════════════════
        # 6. Conditional Logic (+2.0)
        # ═══════════════════════════════════════════════════════
        conditional_detected, conditional_score = self._detect_conditional_logic(query_lower)
        if conditional_detected:
            score += conditional_score
            signals["conditional_logic"] = True
            reasoning.append(f"Conditional logic detected (+{conditional_score:.1f})")
            indicator_scores["conditional_logic"] = conditional_score

        # ═══════════════════════════════════════════════════════
        # 7. Iterative Operations (+1.5)
        # ═══════════════════════════════════════════════════════
        iterative_detected, iterative_score = self._detect_iterative_operations(query_lower)
        if iterative_detected:
            score += iterative_score
            signals["iterative_operations"] = True
            reasoning.append(f"Iterative operations detected (+{iterative_score:.1f})")
            indicator_scores["iterative_operations"] = iterative_score

        # ═══════════════════════════════════════════════════════
        # 8. High Parameter Count (+1.0)
        # ═══════════════════════════════════════════════════════
        param_detected, param_score = self._detect_high_parameter_count(query_lower, tools)
        if param_detected:
            score += param_score
            signals["high_parameter_count"] = True
            reasoning.append(f"High parameter count (+{param_score:.1f})")
            indicator_scores["high_parameter_count"] = param_score

        # ═══════════════════════════════════════════════════════
        # Map Score to Complexity Level
        # ═══════════════════════════════════════════════════════
        if score >= 13.0:
            level = ToolComplexityLevel.EXPERT
        elif score >= 9.0:
            level = ToolComplexityLevel.HARD
        elif score >= 6.0:
            level = ToolComplexityLevel.MODERATE
        elif score >= 3.0:
            level = ToolComplexityLevel.SIMPLE
        else:
            level = ToolComplexityLevel.TRIVIAL

        # Add level to reasoning
        reasoning.insert(0, f"Complexity level: {level.value} (score: {score:.1f})")

        return ToolAnalysisResult(
            complexity_level=level,
            score=score,
            signals=signals,
            reasoning=reasoning,
            indicator_scores=indicator_scores,
        )

    # ═══════════════════════════════════════════════════════════
    # Detection Methods
    # ═══════════════════════════════════════════════════════════

    def _detect_multi_step(self, query: str, tools: list[dict]) -> tuple[bool, float]:
        """
        Detect if query requires multiple sequential tool calls.

        This is the MOST CRITICAL indicator for complexity.

        Indicators:
        - Sequential keywords (then, after, next, first, second)
        - Multiple verbs suggesting different actions
        - Multiple tool invocations needed
        - Chain of dependencies

        Examples:
        - "Analyze sales, identify trends, then forecast Q4" → True (+8.0)
        - "Get weather and book restaurant" → True (+8.0)
        - "What's the weather?" → False (+0.0)
        """
        # Check for sequential keywords
        sequential_keywords_found = any(keyword in query for keyword in self.MULTI_STEP_KEYWORDS)

        # Check for multiple action verbs
        action_verbs = [
            "get",
            "find",
            "search",
            "analyze",
            "create",
            "update",
            "delete",
            "send",
            "fetch",
            "calculate",
            "generate",
            "identify",
            "compare",
            "evaluate",
            "process",
            "transform",
        ]
        verb_count = sum(1 for verb in action_verbs if verb in query)

        # Check for conjunction suggesting multiple operations
        has_and = " and " in query and verb_count >= 2
        has_comma_separated = "," in query and verb_count >= 2

        # Multi-step detected if:
        # 1. Sequential keywords present, OR
        # 2. Multiple verbs with conjunctions, OR
        # 3. More than 2 action verbs
        if sequential_keywords_found or has_and or has_comma_separated or verb_count > 2:
            return True, self.weights["multi_step"]

        return False, 0.0

    def _detect_ambiguous_params(self, query: str, tools: list[dict]) -> tuple[bool, float]:
        """
        Detect if tool parameters need interpretation or inference.

        Indicators:
        - Vague language (best, appropriate, relevant)
        - Missing explicit parameters
        - Implicit references (recent, current, latest)
        - Relative terms (around, approximately)

        Examples:
        - "Find relevant documents" → True (+4.0)
        - "Get recent sales data" → True (+4.0)
        - "Get weather for Paris, France" → False (+0.0)
        """
        # Check for ambiguous keywords
        ambiguous_found = any(keyword in query for keyword in self.AMBIGUOUS_KEYWORDS)

        # Check for implicit references
        implicit_refs = ["this", "that", "it", "them", "those", "these"]
        has_implicit = any(ref in query for ref in implicit_refs)

        # Check if query is too short (likely missing details)
        words = query.split()
        is_too_short = len(words) <= 5 and len(tools) > 1

        if ambiguous_found or has_implicit or is_too_short:
            return True, self.weights["ambiguous"]

        return False, 0.0

    def _detect_nested_structures(self, query: str, tools: list[dict]) -> tuple[bool, float]:
        """
        Detect if query requires complex nested objects or arrays.

        Indicators:
        - Multiple related entities
        - Hierarchical data structures
        - Complex filtering/grouping
        - Nested parameters in tool schemas

        Examples:
        - "Get all tasks with subtasks and their assignees" → True (+3.0)
        - "Create project with team members and their roles" → True (+3.0)
        - "Get weather" → False (+0.0)
        """
        # Check for hierarchical keywords
        hierarchical_keywords = {
            "with",
            "including",
            "along with",
            "and their",
            "nested",
            "subtasks",
            "subcategories",
            "children",
            "parent",
            "hierarchy",
            "tree",
            "structure",
        }

        has_hierarchical = any(keyword in query for keyword in hierarchical_keywords)

        # Check if tools have nested parameters
        has_nested_params = False
        for tool in tools:
            params = tool.get("parameters", {})
            if isinstance(params, dict):
                properties = params.get("properties", {})
                for prop_value in properties.values():
                    if isinstance(prop_value, dict):
                        # Check for nested objects or arrays
                        if prop_value.get("type") in ["object", "array"]:
                            has_nested_params = True
                            break

        if has_hierarchical or has_nested_params:
            return True, self.weights["nested"]

        return False, 0.0

    def _detect_tool_selection_difficulty(
        self, query: str, tools: list[dict]
    ) -> tuple[bool, float]:
        """
        Detect if choosing the right tool is difficult.

        Indicators:
        - Many similar tools available
        - Overlapping tool capabilities
        - Unclear which tool to use

        Examples:
        - Query: "Send a message" with tools: [send_email, send_sms, send_slack] → True (+2.0)
        - Query: "Get weather" with tools: [get_weather] → False (+0.0)
        """
        # If only 1-2 tools, selection is easy
        if len(tools) <= 2:
            return False, 0.0

        # Extract tool names and look for similar patterns
        tool_names = [tool.get("name", "").lower() for tool in tools]

        # Check for similar prefixes (get_*, send_*, create_*, etc.)
        prefixes = {}
        for name in tool_names:
            if "_" in name:
                prefix = name.split("_")[0]
                prefixes[prefix] = prefixes.get(prefix, 0) + 1

        # If multiple tools share a prefix, selection might be difficult
        has_similar_tools = any(count >= 2 for count in prefixes.values())

        # If many tools available and query is vague
        is_vague = len(query.split()) <= 5
        has_many_tools = len(tools) >= 5

        if has_similar_tools or (is_vague and has_many_tools):
            return True, self.weights["tool_selection"]

        return False, 0.0

    def _detect_context_requirements(
        self, query: str, context: Optional[dict]
    ) -> tuple[bool, float]:
        """
        Detect if query needs conversation context or state.

        Indicators:
        - References to previous messages
        - Pronouns without antecedents
        - Continuation phrases
        - Stateful operations

        Examples:
        - "Update it" → True (+2.5)
        - "Continue from where we left off" → True (+2.5)
        - "Get weather for Paris" → False (+0.0)
        """
        # Check for context-dependent pronouns
        context_pronouns = ["it", "that", "this", "them", "those", "these"]
        has_pronoun = any(f" {pron} " in f" {query} " for pron in context_pronouns)

        # Check for continuation phrases
        continuation_phrases = [
            "continue",
            "resume",
            "previous",
            "last",
            "earlier",
            "mentioned",
            "discussed",
            "said",
            "told",
            "above",
        ]
        has_continuation = any(phrase in query for phrase in continuation_phrases)

        # Check if context is empty (might need it but don't have it)
        lacks_context = context is None or not context

        if (has_pronoun or has_continuation) and lacks_context:
            return True, self.weights["context"]

        return False, 0.0

    def _detect_conditional_logic(self, query: str) -> tuple[bool, float]:
        """
        Detect if query requires conditional reasoning.

        Indicators:
        - If-then statements
        - Conditional keywords
        - Decision-making based on conditions

        Examples:
        - "If weather is nice, book restaurant" → True (+2.0)
        - "Send email only if approved" → True (+2.0)
        - "Get weather" → False (+0.0)
        """
        has_conditional = any(keyword in query for keyword in self.CONDITIONAL_KEYWORDS)

        if has_conditional:
            return True, self.weights["conditional"]

        return False, 0.0

    def _detect_iterative_operations(self, query: str) -> tuple[bool, float]:
        """
        Detect if query requires loops or repeated operations.

        Indicators:
        - Keywords suggesting iteration (all, each, every)
        - Multiple similar operations
        - Comparison across items

        Examples:
        - "Compare prices across all vendors" → True (+1.5)
        - "Send email to each team member" → True (+1.5)
        - "Get weather" → False (+0.0)
        """
        has_iterative = any(keyword in query for keyword in self.ITERATIVE_KEYWORDS)

        if has_iterative:
            return True, self.weights["iterative"]

        return False, 0.0

    def _detect_high_parameter_count(self, query: str, tools: list[dict]) -> tuple[bool, float]:
        """
        Detect if tools require many parameters.

        Indicators:
        - Tools have many required parameters
        - Query mentions many details

        Examples:
        - Query mentions 5+ specific details → True (+1.0)
        - Simple query with simple tool → False (+0.0)
        """
        # Count entities/details in query (rough heuristic)
        query.split()

        # Look for numbers, dates, names (capitalized), quoted strings
        detail_count = 0
        detail_count += len(re.findall(r"\d+", query))  # Numbers
        detail_count += len(re.findall(r"[A-Z][a-z]+", query))  # Capitalized words
        detail_count += len(re.findall(r'["\'].*?["\']', query))  # Quoted strings

        # Check if any tool has many required parameters
        max_required_params = 0
        for tool in tools:
            params = tool.get("parameters", {})
            required = params.get("required", [])
            max_required_params = max(max_required_params, len(required))

        if detail_count >= 5 or max_required_params >= 5:
            return True, self.weights["parameter"]

        return False, 0.0
