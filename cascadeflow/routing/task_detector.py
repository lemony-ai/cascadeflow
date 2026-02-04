"""
Task-type detection for pre-routing decisions.

v17 (Feb 2026): Universal task-aware routing for ALL developers.

This module detects task types in queries BEFORE routing decisions,
enabling intelligent model selection based on task characteristics.

Supported Task Types:
- CLASSIFICATION: Multi-class categorization tasks
  - Simple: 2-10 classes (allow cascade)
  - Complex: 11+ classes (route to verifier)
- GENERAL: Standard queries (use complexity-based routing)

Universal Benefits:
- Banking77-like apps: 77 intents → verifier (75% accuracy vs 25%)
- Topic classification: varies by class count
- Sentiment analysis: 2-5 classes → cascade (cost savings)
- Intent classification for chatbots: depends on intent count

This is NOT a benchmark-specific fix - it benefits ANY developer doing
classification tasks by routing to the right model for the task.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Detected task type for routing decisions."""

    GENERAL = "general"
    CLASSIFICATION = "classification"
    FUNCTION_CALLING = "function_calling"


@dataclass
class TaskDetectionResult:
    """Result of task-type detection.

    Attributes:
        task_type: Detected task type
        confidence: Confidence in detection (0-1)
        category_count: Number of categories for classification tasks
        should_use_verifier: Recommended routing decision
        reason: Explanation for the recommendation
    """

    task_type: TaskType
    confidence: float
    category_count: Optional[int] = None
    should_use_verifier: bool = False
    reason: str = ""


class TaskDetector:
    """
    Detects task type from query for pre-routing decisions.

    v17 (Feb 2026): Task-aware routing for improved accuracy on specialized tasks.

    This detector runs BEFORE the draft model is called, enabling intelligent
    routing based on task characteristics rather than just query complexity.

    Why This Matters:
    - Complex classification (77 classes): GPT-4o-mini gets 25%, Claude gets 75%
    - Simple classification (5 classes): Both models can handle it well
    - By detecting task type early, we can route to the right model

    Configuration:
        complex_class_threshold: Number of classes above which to use verifier
            Default: 15 (backed by empirical testing)
            - 2-15 classes: Cheap models handle well
            - 16+ classes: Better models significantly outperform

    Example:
        detector = TaskDetector(complex_class_threshold=15)
        result = detector.detect(query)
        if result.should_use_verifier:
            # Route to verifier model
    """

    # Classification instruction patterns (from alignment_scorer v11)
    CLASSIFICATION_INSTRUCTIONS = [
        "classify this",
        "classify the",
        "categorize this",
        "categorize the",
        "identify the intent",
        "determine the intent",
        "what is the intent",
        "which intent",
        "which category",
        "label this",
        "classify into",
        "categorize into",
    ]

    # List markers indicating category enumeration
    LIST_MARKERS = [
        "available intents:",
        "available categories:",
        "intent labels:",
        "category labels:",
        "possible intents:",
        "possible categories:",
        "choose from:",
        "one of the following:",
        "into one of",
        "from the following list",
        "options:",
        "choices:",
    ]

    # Output format markers
    OUTPUT_FORMAT_MARKERS = [
        "intent:",
        "category:",
        "label:",
        "format your response",
        "output the exact intent",
        "output the exact category",
    ]

    def __init__(
        self,
        complex_class_threshold: int = 15,
        verbose: bool = False,
    ):
        """
        Initialize task detector.

        Args:
            complex_class_threshold: Number of categories above which
                classification tasks should route to verifier.
                Default: 15 (empirically tested)
            verbose: Enable verbose logging
        """
        self.complex_class_threshold = complex_class_threshold
        self.verbose = verbose

        logger.info(
            f"TaskDetector initialized:\n"
            f"  Complex class threshold: {complex_class_threshold}\n"
            f"  Tasks with >{complex_class_threshold} categories → verifier"
        )

    def detect(self, query: str) -> TaskDetectionResult:
        """
        Detect task type from query.

        Args:
            query: User query text

        Returns:
            TaskDetectionResult with task type and routing recommendation
        """
        query_lower = query.lower()

        # Check for classification task
        classification_result = self._detect_classification(query, query_lower)
        if classification_result.task_type == TaskType.CLASSIFICATION:
            return classification_result

        # Default: general task
        return TaskDetectionResult(
            task_type=TaskType.GENERAL,
            confidence=1.0,
            should_use_verifier=False,
            reason="Standard query - use complexity-based routing",
        )

    def _detect_classification(
        self, query: str, query_lower: str
    ) -> TaskDetectionResult:
        """
        Detect if query is a classification task.

        Returns TaskDetectionResult with:
        - task_type: CLASSIFICATION if detected, GENERAL if not
        - category_count: Number of categories found
        - should_use_verifier: True if complex classification
        """
        # Check for classification instruction
        has_classification_instruction = any(
            instr in query_lower for instr in self.CLASSIFICATION_INSTRUCTIONS
        )

        # Check for list marker (indicates category enumeration)
        has_list_marker = any(marker in query_lower for marker in self.LIST_MARKERS)

        # Check for output format
        has_output_format = any(
            marker in query_lower for marker in self.OUTPUT_FORMAT_MARKERS
        )

        # Classification if has instruction + list OR instruction + output format
        is_classification = has_classification_instruction and (
            has_list_marker or has_output_format
        )

        if not is_classification:
            return TaskDetectionResult(
                task_type=TaskType.GENERAL,
                confidence=1.0,
                should_use_verifier=False,
                reason="Not a classification task",
            )

        # Count categories in the query
        category_count = self._count_categories(query)

        # Determine if complex classification
        is_complex = category_count > self.complex_class_threshold

        confidence = 0.9 if has_list_marker and has_classification_instruction else 0.7

        if is_complex:
            reason = (
                f"Complex classification with {category_count} categories "
                f"(>{self.complex_class_threshold}) → route to verifier for accuracy"
            )
        else:
            reason = (
                f"Simple classification with {category_count} categories "
                f"(≤{self.complex_class_threshold}) → cascade for cost savings"
            )

        result = TaskDetectionResult(
            task_type=TaskType.CLASSIFICATION,
            confidence=confidence,
            category_count=category_count,
            should_use_verifier=is_complex,
            reason=reason,
        )

        if self.verbose:
            print(
                f"[TaskDetector] Classification detected:\n"
                f"  Categories: {category_count}\n"
                f"  Complex: {is_complex}\n"
                f"  Route to verifier: {is_complex}\n"
                f"  Reason: {reason}"
            )

        logger.debug(
            f"Classification task detected: categories={category_count}, "
            f"complex={is_complex}, verifier={is_complex}"
        )

        return result

    def _count_categories(self, query: str) -> int:
        """
        Count the number of categories/intents in a classification query.

        Strategies:
        1. Count lines starting with "- " in list sections
        2. Count numbered items (1., 2., etc.)
        3. Count quoted items in comma-separated lists
        4. Count items in explicit lists after markers

        Returns:
            Estimated number of categories (minimum 2 for classification)
        """
        count = 0

        # Strategy 1: Count lines starting with "- " (markdown lists)
        dash_items = re.findall(r"^- \w+", query, re.MULTILINE)
        count = max(count, len(dash_items))

        # Strategy 2: Count lines starting with "* " (alternative markdown)
        star_items = re.findall(r"^\* \w+", query, re.MULTILINE)
        count = max(count, len(star_items))

        # Strategy 3: Count numbered items (1. item, 2. item)
        numbered_items = re.findall(r"^\d+\.\s+\w+", query, re.MULTILINE)
        count = max(count, len(numbered_items))

        # Strategy 4: Count items in newline-separated lists after markers
        # Look for sections like "Available intents:\n- item1\n- item2"
        list_section_pattern = (
            r"(?:intents?|categories?|labels?|options?|choices?):\s*\n"
            r"((?:[-*]\s*\w+.*\n)+)"
        )
        list_sections = re.findall(list_section_pattern, query, re.IGNORECASE)
        for section in list_sections:
            items = re.findall(r"[-*]\s*\w+", section)
            count = max(count, len(items))

        # Strategy 5: Count snake_case or lowercase items in lists
        # e.g., "activate_my_card, age_limit, apple_pay_or_google_pay"
        snake_case_items = re.findall(r"\b[a-z_]+_[a-z_]+\b", query)
        # Deduplicate
        unique_snake_case = set(snake_case_items)
        if len(unique_snake_case) > 5:  # Only if seems like a category list
            count = max(count, len(unique_snake_case))

        # Strategy 6: Count explicit intent names after "intents:" or similar
        # Pattern: lines that are just intent names (no spaces, underscores allowed)
        lines = query.split("\n")
        intent_lines = []
        in_list_section = False
        for line in lines:
            line_stripped = line.strip()
            if any(marker in line.lower() for marker in ["intents:", "categories:", "labels:"]):
                in_list_section = True
                continue
            if in_list_section:
                # Check if line looks like an intent name
                if line_stripped.startswith("- "):
                    intent_name = line_stripped[2:].strip()
                    if re.match(r"^[\w_]+$", intent_name):
                        intent_lines.append(intent_name)
                elif not line_stripped:
                    # Empty line might end the section
                    continue
                elif not re.match(r"^[\w_]+$", line_stripped):
                    # Non-intent content, might end section
                    end_markers = ("format", "output", "instruction", "respond")
                    if line_stripped.lower().startswith(end_markers):
                        in_list_section = False

        count = max(count, len(intent_lines))

        # Minimum for classification is 2
        return max(count, 2)


__all__ = [
    "TaskDetector",
    "TaskDetectionResult",
    "TaskType",
]
