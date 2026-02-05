"""
Domain Detection for Smart Routing

This module provides automatic domain detection to route queries to specialized
models based on the query content (code, medical, legal, general, etc.).

Key Features:
- Rule-based keyword matching
- Optional ML-based semantic detection (using embeddings)
- Hybrid mode (combines rule-based + ML)
- Confidence scoring
- Support for custom domains
- Domain-specific model selection

Example:
    >>> from cascadeflow.routing.domain import DomainDetector
    >>>
    >>> detector = DomainDetector()
    >>>
    >>> # Detect domain
    >>> domain, confidence = detector.detect("Write a Python function to sort a list")
    >>> print(f"Domain: {domain}, Confidence: {confidence:.0%}")
    # Output: Domain: code, Confidence: 95%
    >>>
    >>> # Get recommended models
    >>> models = detector.get_recommended_models(domain)
    >>> print(f"Recommended: {models[0]['name']}")
    # Output: Recommended: deepseek-coder
    >>>
    >>> # Optional: Use ML-based semantic detection
    >>> from cascadeflow.routing.domain import SemanticDomainDetector
    >>> ml_detector = SemanticDomainDetector()
    >>> if ml_detector.is_available:
    ...     domain, confidence = ml_detector.detect("Write a Python function to sort a list")
    ...     print(f"Domain: {domain}, Confidence: {confidence:.0%}")
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from cascadeflow.utils.messages import is_multi_turn_prompt

# Optional ML imports
try:
    from ..ml.embedding import UnifiedEmbeddingService

    HAS_ML = True
except ImportError:
    HAS_ML = False
    UnifiedEmbeddingService = None

logger = logging.getLogger(__name__)


class Domain(str, Enum):
    """Supported domains for query routing (15 production domains)."""

    CODE = "code"  # Programming, development, software engineering
    DATA = "data"  # Data analysis, SQL, analytics
    STRUCTURED = "structured"  # Structured data extraction (JSON, XML, forms)
    RAG = "rag"  # RAG/search queries, document retrieval
    CONVERSATION = "conversation"  # Multi-turn dialogue, chatbot
    TOOL = "tool"  # Tool/function calling, external APIs
    CREATIVE = "creative"  # Creative writing, content generation
    COMPARISON = "comparison"  # X vs Y, compare/contrast
    SUMMARY = "summary"  # Text summarization, condensing
    TRANSLATION = "translation"  # Language translation
    MATH = "math"  # Mathematical reasoning, calculations
    FACTUAL = "factual"  # Fact checking, verification, sources
    MEDICAL = "medical"  # Healthcare, medicine (high accuracy required)
    LEGAL = "legal"  # Law, contracts, compliance
    FINANCIAL = "financial"  # Financial analysis, market research
    MULTIMODAL = "multimodal"  # Vision + text queries
    GENERAL = "general"  # General knowledge, factual QA


@dataclass
class DomainKeywords:
    """Keywords for domain detection.

    Attributes:
        very_strong: Highly discriminative keywords (weight: 1.5) - Research-backed
        strong: High-confidence keywords (weight: 1.0)
        moderate: Medium-confidence keywords (weight: 0.7) - Increased from 0.5
        weak: Low-confidence keywords (weight: 0.3) - Increased from 0.25
    """

    very_strong: list[str] = field(default_factory=list)  # NEW: 1.5 weight
    strong: list[str] = field(default_factory=list)
    moderate: list[str] = field(default_factory=list)
    weak: list[str] = field(default_factory=list)


# Built-in domain keyword mappings (17 production domains)
DOMAIN_KEYWORDS: dict[Domain, DomainKeywords] = {
    Domain.CODE: DomainKeywords(
        very_strong=[  # Highly discriminative (Research: 77% accuracy)
            "async",
            "await",
            "import",
            "def",
            "const",
            "let",
            "npm",
            "pip",
            "docker",
            "kubernetes",
            "pytest",
            "unittest",
        ],
        strong=[
            "function",
            "class",
            "python",
            "javascript",
            "typescript",
            "java",
            "code",
            "algorithm",
            "api",
            "debug",
            "error",
            "exception",
            "compile",
            "runtime",
            "syntax",
            "refactor",
            "repository",
        ],
        moderate=[
            "program",
            "software",
            "implement",
            "develop",
            "build",
            "script",
            "test",
            "deploy",
            "git",
            "github",
            "lint",
            "regex",
            "recursion",
            "OOP",
            "frontend",
            "backend",
        ],
        weak=[],  # Removed generic terms per research
    ),
    Domain.DATA: DomainKeywords(
        very_strong=[  # Highly discriminative for DATA domain
            "pandas",
            "numpy",
            "ETL",
            "warehouse",
            "BI",
            "correlation",
        ],
        strong=[
            "sql",
            "database",
            "query",
            "dataframe",
            "analysis",
            "visualization",
            "dataset",
            "analytics",
            "select",
            "regression",
        ],
        moderate=[
            "data",
            "table",
            "column",
            "join",
            "filter",
            "aggregate",
            "chart",
            "graph",
            "metrics",
            "report",
            "pivot",
            "group by",
        ],
        weak=[],  # Removed generic math terms
    ),
    Domain.STRUCTURED: DomainKeywords(
        very_strong=[  # Format-specific keywords (Research-backed)
            "json",
            "xml",
            "yaml",
            "pydantic",
            "schema validation",
            "protobuf",
            "avro",
            "JSON Schema",
            "dataclass",
        ],
        strong=[
            "extract",
            "parse",
            "schema",
            "fields",
            "entity",
            "structure",
            "format",
            "convert",
            "normalize",
            "CSV",
            "Excel",
            "spreadsheet",
            "serialize",
            "deserialize",
            "validate",
            "attrs",
        ],
        moderate=[
            "form",
            "template",
            "transform",
            "map",
            "property",
            "field mapping",
            "record",
            "document structure",
            "nested",
            "flatten",
            "key-value",
            "attribute",
            "TOML",
            "msgpack",
        ],
        weak=[],  # Removed generic terms
    ),
    Domain.RAG: DomainKeywords(
        very_strong=[  # Retrieval-specific (Research-backed)
            "semantic search",
            "vector search",
            "embedding",
            "similar documents",
        ],
        strong=[
            "search",
            "retrieve",
            "lookup",
            "documentation",
            "knowledge base",
            "documents",
            "corpus",
            "index",
            "relevance",
        ],
        moderate=[
            "summarize",
            "review",
            "analyze",
            "compare documents",
            "reference",
            "citation",
            "source",
            "context",
            "passages",
        ],
        weak=[],  # Removed generic question words
    ),
    Domain.CONVERSATION: DomainKeywords(
        very_strong=[  # Multi-turn indicators AND greeting patterns
            "remember",
            "you said",
            "earlier you mentioned",
            "back to",
            "hello",
            "hi there",
            "hey there",
            "good morning",
            "good afternoon",
            "good evening",
            "good night",
            "how are you",
            "nice to meet",
            "thanks for",
            "thank you",
        ],
        strong=[
            "chat",
            "conversation",
            "discuss",
            "follow-up",
            "continue",
            "previous",
            "earlier",
            "dialogue",
            "multi-turn",
            "hey",
            "hi",
            "bye",
            "goodbye",
            "see you",
            "thanks",
            "sorry",
            "please",
            "excuse me",
            "what's up",
            "how's it going",
        ],
        moderate=[
            "help",
            "support",
            "assist",
            "question",
            "clarify",
            "understand",
            "context",
            "referring to",
            "opinion",
            "think about",
            "feel about",
            "believe",
        ],
        weak=[],  # Removed generic question words
    ),
    Domain.TOOL: DomainKeywords(
        very_strong=[  # API/Integration specific
            "API call",
            "webhook",
            "endpoint",
            "POST",
            "GET",
            "PUT",
        ],
        strong=[
            "fetch",
            "send",
            "create",
            "update",
            "delete",
            "action",
            "execute",
            "call",
            "invoke",
            "integration",
        ],
        moderate=[
            "check",
            "verify",
            "schedule",
            "book",
            "order",
            "submit",
            "run",
            "trigger",
            "perform",
            "external",
            "third-party",
        ],
        weak=[],  # Removed generic action words
    ),
    Domain.CREATIVE: DomainKeywords(
        strong=[
            "write",
            "story",
            "poem",
            "creative",
            "article",
            "essay",
            "narrative",
            "character",
            "plot",
            "compose",
            "draft",
        ],
        moderate=[
            "describe",
            "imagine",
            "design",
            "generate content",
            "marketing",
            "copy",
            "blog",
            "social media",
        ],
        weak=["create", "make", "new"],
    ),
    Domain.COMPARISON: DomainKeywords(
        very_strong=[
            "compare",
            "comparison",
            "versus",
            "vs",
            "difference between",
            "pros and cons",
            "tradeoffs",
            "trade-off",
        ],
        strong=[
            "differences",
            "similarities",
            "which is better",
            "better than",
            "worse than",
            "advantages",
            "disadvantages",
        ],
        moderate=[
            "contrast",
            "relative to",
            "vs.",
            "x vs y",
            "x versus y",
        ],
        weak=[
            "compare to",
            "compared with",
        ],
    ),
    Domain.SUMMARY: DomainKeywords(
        strong=[
            "summarize",
            "condense",
            "tldr",
            "executive summary",
            "key points",
            "main themes",
            "highlights",
            "overview",
        ],
        moderate=["brief", "abstract", "essence", "distill", "compress", "shorten", "extract main"],
        weak=["short", "simple", "quick"],
    ),
    Domain.TRANSLATION: DomainKeywords(
        strong=[
            "translate",
            "translation",
            "convert language",
            "localize",
            "spanish",
            "french",
            "german",
            "chinese",
            "japanese",
        ],
        moderate=[
            "language",
            "multilingual",
            "interpret",
            "international",
            "native language",
            "foreign",
        ],
        weak=["change", "switch", "different language"],
    ),
    Domain.MATH: DomainKeywords(
        very_strong=[  # Highly discriminative (math-specific)
            "derivative",
            "integral",
            "theorem",
            "proof",
            "eigenvalue",
            "differential equation",
            "matrix multiplication",
            "calculus",
            "trigonometry",
            "logarithm",
            # Word problem math indicators (GSM8K style)
            "how many did",
            "how much does",
            "how much in dollars",
            "how much money",
            "what is the total",
            "what percentage",
        ],
        strong=[
            "calculate",
            "equation",
            "formula",
            "mathematics",
            "algebra",
            "geometry",
            "statistics",
            "probability",
            "solve",
            "vector",
            "matrix",
            "optimization",
            "polynomial",
            # Word problem math (GSM8K style)
            "how much",
            "how many",
            "per day",
            "per hour",
            "per week",
            "each day",
            "remainder",
            "in total",
            "altogether",
        ],
        moderate=[
            "compute",
            "graph",
            "variable",
            "function",
            "coefficient",
            "expression",
            "numeric",
            "symbolic",
            "scientific notation",
            "exponent",
            "factorial",
            "summation",
            # Word problem (grade school)
            "left over",
            "start with",
            "end up with",
            "divided equally",
            "split evenly",
        ],
        weak=[
            "add",
            "subtract",
            "multiply",
            "divide",
            "number",
            "math",
            # Common math instruction phrases
            "show your work",
            "step by step",
            "calculate",
            "equals",
            "what is",
            "times",
            "plus",
            "minus",
        ],
    ),
    Domain.FACTUAL: DomainKeywords(
        very_strong=[
            "fact check",
            "fact-check",
            "is it true",
            "true or false",
            "verify",
            "verification",
            "what is the capital",
            "who invented",
            "when was",
            "where is",
            "how many",
            "population of",
        ],
        strong=[
            "factual",
            "accuracy",
            "accurate",
            "sources",
            "citations",
            "evidence",
            "debunk",
            "history",
            "geography",
            "country",
            "city",
            "planet",
            "continent",
            "ocean",
            "mountain",
            "river",
            "founded",
            "discovered",
            "born",
            "died",
        ],
        moderate=[
            "confirm",
            "validate",
            "myth",
            "hoax",
            "misinformation",
            "explain",
            "describe",
            "definition",
            "what is",
            "who is",
            "tell me about",
        ],
        weak=[
            "correct",
            "incorrect",
        ],
    ),
    Domain.MEDICAL: DomainKeywords(
        very_strong=[  # Highly discriminative medical terms
            "symptoms of",
            "diagnosis of",
            "treatment for",
            "blood test",
            "medical advice",
            "diabetes",
            "hypertension",
            "cardiovascular",
            "prescription drug",
        ],
        strong=[
            "diagnosis",
            "symptom",
            "treatment",
            "disease",
            "patient",
            "medical",
            "doctor",
            "medication",
            "surgery",
            "clinical",
            "pharmacy",
            "prescription",
            "healthcare",
            "prognosis",
            "chronic",
            "acute",
            "anatomy",
            "physiology",
            "organ",
            "body",
        ],
        moderate=[
            "health",
            "pain",
            "condition",
            "therapy",
            "hospital",
            "nurse",
            "drug",
            "dosage",
            "protocol",
            "interact",  # medication interactions
            "side effect",
            "heart",
            "liver",
            "kidney",
            "brain",
            "lung",
        ],
        weak=["feel", "hurt", "sick", "ill"],
    ),
    Domain.LEGAL: DomainKeywords(
        strong=[
            "law",
            "legal",
            "contract",
            "lawsuit",
            "court",
            "attorney",
            "regulation",
            "statute",
            "liability",
            "plaintiff",
            "defendant",
            "compliance",
            "litigation",
        ],
        moderate=[
            "rights",
            "agreement",
            "clause",
            "terms",
            "policy",
            "jurisdiction",
            "precedent",
            "case law",
        ],
        weak=["rule", "requirement", "must"],
    ),
    Domain.FINANCIAL: DomainKeywords(
        very_strong=[
            "compound interest",
            "tax implications",
            "p/e ratio",
            "retirement savings",
            "401k",
            "ira",
        ],
        strong=[
            "financial",
            "investment",
            "portfolio",
            "risk",
            "earnings",
            "revenue",
            "market",
            "stock",
            "trading",
            "valuation",
            "roi",
            "profit",
            "loss",
            "bond",
            "bonds",
            "equity",
            "equities",
            "interest rate",
            "yield",
            "coupon",
            "fixed income",
            "interest",
            "tax",
            "inflation",
            "mutual fund",
            "diversification",
            "retirement",
            "savings",
            "pension",
            "etf",
            "hedge fund",
        ],
        moderate=[
            "analysis",
            "forecast",
            "budget",
            "venture capital",  # More specific than just "capital"
            "asset",
            "liability",
            "cash flow",
            "dividend",
            "risk-return",
            "rate environment",
            "yield curve",
            "mortgage",
            "loan",
            "credit",
            "debt",
        ],
        weak=["money", "cost", "price", "pay"],
    ),
    # GENERAL domain - fallback for queries that don't match specific domains
    Domain.GENERAL: DomainKeywords(
        very_strong=[],  # No very_strong - let specific domains win
        strong=[
            "how does",
            "explain how",
            "why does",
            "information about",
        ],
        moderate=[
            "knowledge",
            "encyclopedia",
            "trivia",
            "general",
            "miscellaneous",
        ],
        weak=["simple", "basic"],
    ),
    Domain.MULTIMODAL: DomainKeywords(
        strong=[
            "image",
            "photo",
            "picture",
            "visual",
            "scan",
            "ocr",
            "chart",
            "graph",
            "diagram",
            "screenshot",
            "video",
        ],
        moderate=[
            "see",
            "view",
            "look at",
            "display",
            "caption",
            "describe image",
            "analyze photo",
            "show me the image",
            "show the picture",
        ],
        weak=["this", "that", "here"],
    ),
}


@dataclass
class DomainDetectionResult:
    """Result of domain detection.

    Attributes:
        domain: Detected domain
        confidence: Detection confidence (0-1)
        scores: Scores for all domains
        metadata: Additional detection metadata
    """

    domain: Domain
    confidence: float
    scores: dict[Domain, float] = field(default_factory=dict)
    metadata: dict[str, any] = field(default_factory=dict)


class DomainDetector:
    """
    Rule-based domain detector for query routing.

    Uses keyword matching with confidence scoring to detect the domain
    of a query. Supports custom domains and keywords.

    Attributes:
        keywords: Domain keyword mappings
        confidence_threshold: Minimum confidence for detection
    """

    # MCQ detection patterns
    MCQ_PATTERNS = [
        # Standard MCQ formats
        r"(?:answer|choose|select)\s+(?:the\s+)?(?:following\s+)?(?:multiple[- ]choice|mcq)",
        r"provide\s+your\s+answer\s+as\s+(?:a\s+)?(?:single\s+)?letter",
        r"^(?:question|q)\s*(?:\d+)?[:.]\s*",
        # Choice indicators (A. B. C. D. or A) B) C) D))
        r"(?:^|\n)\s*[ABCD]\s*[\.\)]\s+",
        # MMLU-style format
        r"answer:\s*$",
    ]

    # Subject-to-domain mapping for MCQ (MMLU categories)
    SUBJECT_DOMAIN_MAP = {
        # STEM subjects
        "math": Domain.MATH,
        "algebra": Domain.MATH,
        "calculus": Domain.MATH,
        "geometry": Domain.MATH,
        "statistics": Domain.MATH,
        "arithmetic": Domain.MATH,
        "mathematics": Domain.MATH,
        # Science subjects
        "physics": Domain.GENERAL,  # General knowledge for physics
        "chemistry": Domain.GENERAL,
        "biology": Domain.GENERAL,
        "astronomy": Domain.GENERAL,
        "science": Domain.GENERAL,
        "comparison": Domain.COMPARISON,
        "compare": Domain.COMPARISON,
        "versus": Domain.COMPARISON,
        "vs": Domain.COMPARISON,
        "factual": Domain.FACTUAL,
        "fact check": Domain.FACTUAL,
        "fact-check": Domain.FACTUAL,
        "verify": Domain.FACTUAL,
        "verification": Domain.FACTUAL,
        # Medical subjects
        "medicine": Domain.MEDICAL,
        "medical": Domain.MEDICAL,
        "anatomy": Domain.MEDICAL,
        "clinical": Domain.MEDICAL,
        "nutrition": Domain.MEDICAL,
        "health": Domain.MEDICAL,
        "virology": Domain.MEDICAL,
        # Legal subjects
        "law": Domain.LEGAL,
        "legal": Domain.LEGAL,
        "jurisprudence": Domain.LEGAL,
        # Financial subjects
        "accounting": Domain.FINANCIAL,
        "economics": Domain.FINANCIAL,
        "finance": Domain.FINANCIAL,
        "business": Domain.FINANCIAL,
        "marketing": Domain.FINANCIAL,
        "management": Domain.FINANCIAL,
        # Code/CS subjects
        "computer": Domain.CODE,
        "programming": Domain.CODE,
        "machine_learning": Domain.CODE,
        "security": Domain.CODE,  # Computer security
    }

    def __init__(
        self,
        confidence_threshold: float = 0.3,
        custom_keywords: Optional[dict[str, DomainKeywords]] = None,
    ):
        """
        Initialize domain detector.

        Args:
            confidence_threshold: Minimum confidence to return domain (default: 0.3)
            custom_keywords: Optional custom domain keywords
        """
        self.confidence_threshold = confidence_threshold
        self.keywords = DOMAIN_KEYWORDS.copy()

        # Add custom keywords if provided
        if custom_keywords:
            for domain_name, keywords in custom_keywords.items():
                try:
                    domain = Domain(domain_name)
                    self.keywords[domain] = keywords
                except ValueError:
                    logger.warning(f"Unknown domain: {domain_name}, skipping")

    def detect(self, query: str) -> tuple[Domain, float]:
        """
        Detect domain from query text.

        Args:
            query: Query text to analyze

        Returns:
            Tuple of (domain, confidence)

        Example:
            >>> detector = DomainDetector()
            >>> domain, conf = detector.detect("Write a Python sorting function")
            >>> print(f"{domain}: {conf:.0%}")
            # Output: code: 85%
        """
        result = self.detect_with_scores(query)
        return result.domain, result.confidence

    def detect_with_scores(self, query: str) -> DomainDetectionResult:
        """
        Detect domain with detailed scoring.

        Args:
            query: Query text to analyze

        Returns:
            DomainDetectionResult with scores for all domains
        """
        # Check for MCQ format and preprocess if detected
        is_mcq, extracted_content, subject_hint = self._detect_mcq_format(query)

        # Use extracted content for keyword matching if MCQ detected
        query_to_analyze = extracted_content if is_mcq else query
        query_lower = query_to_analyze.lower()

        # Calculate scores for each domain
        scores: dict[Domain, float] = {}

        for domain, keywords in self.keywords.items():
            score = self._calculate_domain_score(query_lower, keywords)
            scores[domain] = score

        # If MCQ detected, apply subject-based domain hint
        if is_mcq and subject_hint:
            # Boost the hinted domain score (capped at 1.0 to prevent confidence overflow)
            if subject_hint in scores:
                scores[subject_hint] = min(1.0, max(scores[subject_hint] + 0.5, 0.8))

        # If MCQ detected, penalize CONVERSATION domain (it's not a conversation)
        if is_mcq:
            scores[Domain.CONVERSATION] = max(0, scores.get(Domain.CONVERSATION, 0) - 0.5)

        # Boost conversation domain when multi-turn markers are present
        multi_turn_detected = is_multi_turn_prompt(query)
        if multi_turn_detected and not is_mcq:
            scores[Domain.CONVERSATION] = min(
                1.0, scores.get(Domain.CONVERSATION, 0) + 0.6
            )

        # Find domain with highest score
        if not scores or max(scores.values()) < self.confidence_threshold:
            # Default to GENERAL if no strong match
            detected_domain = Domain.GENERAL
            confidence = 0.5  # Low confidence for general
        else:
            detected_domain = max(scores, key=scores.get)
            confidence = scores[detected_domain]

        return DomainDetectionResult(
            domain=detected_domain,
            confidence=confidence,
            scores=scores,
            metadata={
                "query_length": len(query),
                "threshold": self.confidence_threshold,
                "is_mcq": is_mcq,
                "subject_hint": subject_hint.value if subject_hint else None,
                "multi_turn_detected": multi_turn_detected,
            },
        )

    def _detect_mcq_format(self, query: str) -> tuple[bool, str, Optional[Domain]]:
        """
        Detect if query is a multiple-choice question and extract content.

        Args:
            query: Original query text

        Returns:
            Tuple of (is_mcq, extracted_content, domain_hint)
        """
        query_lower = query.lower()

        # Check MCQ patterns
        is_mcq = False
        for pattern in self.MCQ_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE | re.MULTILINE):
                is_mcq = True
                break

        if not is_mcq:
            return False, query, None

        # Extract the actual question content (strip MCQ wrapper)
        extracted = query

        # Remove common MCQ instruction prefixes
        prefixes_to_remove = [
            r"^answer the following multiple[- ]?choice question[.:]?\s*",
            r"^provide your answer as a single letter[^.]*[.]\s*",
            r"^choose the (?:best|correct) answer[.:]?\s*",
            r"^select (?:one|the correct answer)[.:]?\s*",
        ]

        for prefix in prefixes_to_remove:
            extracted = re.sub(prefix, "", extracted, flags=re.IGNORECASE)

        # Extract content after "Question:" if present
        question_match = re.search(
            r"question[:\s]+(.+?)(?=\n[ABCD][\.\)]|\Z)", extracted, re.IGNORECASE | re.DOTALL
        )
        if question_match:
            extracted = question_match.group(1).strip()

        # Remove answer choices (A. B. C. D. lines)
        extracted = re.sub(r"\n[ABCD][\.\)]\s+[^\n]+", "", extracted)
        # Remove trailing "Answer:" prompt
        extracted = re.sub(r"\s*answer:\s*$", "", extracted, flags=re.IGNORECASE)

        # Try to detect domain from subject keywords in the question
        domain_hint = self._detect_subject_domain(query_lower)

        return True, extracted.strip(), domain_hint

    def _detect_subject_domain(self, query_lower: str) -> Optional[Domain]:
        """
        Detect domain hint from subject-related keywords in the query.

        Args:
            query_lower: Lowercase query text

        Returns:
            Domain hint if detected, None otherwise
        """
        for subject_keyword, domain in self.SUBJECT_DOMAIN_MAP.items():
            if subject_keyword in query_lower:
                return domain
        return None

    def get_recommended_models(
        self,
        domain: Domain,
        all_models: Optional[list[dict]] = None,
    ) -> list[dict]:
        """
        Get recommended models for a domain.

        Args:
            domain: Domain to get models for
            all_models: Optional list of all available models

        Returns:
            List of recommended models (sorted by relevance)
        """
        # Default domain-specific model recommendations (17 domains)
        domain_models = {
            Domain.CODE: [
                {"name": "deepseek-coder", "provider": "deepseek", "cost": 0.0014},
                {"name": "codellama-70b", "provider": "ollama", "cost": 0.0},
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
            ],
            Domain.DATA: [
                {"name": "gpt-4o-mini", "provider": "openai", "cost": 0.00015},
                {"name": "claude-3-5-sonnet", "provider": "anthropic", "cost": 0.003},
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
            ],
            Domain.STRUCTURED: [
                {"name": "gpt-4o-mini", "provider": "openai", "cost": 0.00015},
                {"name": "claude-3-5-haiku", "provider": "anthropic", "cost": 0.0008},
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
            ],
            Domain.RAG: [
                {"name": "claude-3-5-sonnet", "provider": "anthropic", "cost": 0.003},
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
            ],
            Domain.CONVERSATION: [
                {"name": "gpt-4o-mini", "provider": "openai", "cost": 0.00015},
                {"name": "claude-3-5-haiku", "provider": "anthropic", "cost": 0.0008},
                {"name": "llama-3-70b", "provider": "groq", "cost": 0.00059},
            ],
            Domain.TOOL: [
                {"name": "gpt-4o-mini", "provider": "openai", "cost": 0.00015},
                {"name": "claude-3-5-haiku", "provider": "anthropic", "cost": 0.0008},
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
            ],
            Domain.CREATIVE: [
                {"name": "claude-3-opus", "provider": "anthropic", "cost": 0.015},
                {"name": "claude-3-5-sonnet", "provider": "anthropic", "cost": 0.003},
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
            ],
            Domain.COMPARISON: [
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
                {"name": "claude-3-5-sonnet", "provider": "anthropic", "cost": 0.003},
                {"name": "gpt-4o-mini", "provider": "openai", "cost": 0.00015},
            ],
            Domain.SUMMARY: [
                {"name": "claude-3-5-haiku", "provider": "anthropic", "cost": 0.0008},
                {"name": "claude-3-5-sonnet", "provider": "anthropic", "cost": 0.003},
                {"name": "gpt-4o-mini", "provider": "openai", "cost": 0.00015},
            ],
            Domain.TRANSLATION: [
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
                {"name": "claude-3-5-sonnet", "provider": "anthropic", "cost": 0.003},
            ],
            Domain.MATH: [
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
                {"name": "claude-3-5-sonnet", "provider": "anthropic", "cost": 0.003},
            ],
            Domain.FACTUAL: [
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
                {"name": "claude-3-5-sonnet", "provider": "anthropic", "cost": 0.003},
                {"name": "gpt-4o-mini", "provider": "openai", "cost": 0.00015},
            ],
            Domain.MEDICAL: [
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
                {"name": "claude-3-opus", "provider": "anthropic", "cost": 0.015},
            ],
            Domain.LEGAL: [
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
                {"name": "claude-3-opus", "provider": "anthropic", "cost": 0.015},
            ],
            Domain.FINANCIAL: [
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
                {"name": "claude-3-5-sonnet", "provider": "anthropic", "cost": 0.003},
            ],
            Domain.MULTIMODAL: [
                {"name": "gpt-4o", "provider": "openai", "cost": 0.0025},
                {"name": "claude-3-5-sonnet", "provider": "anthropic", "cost": 0.003},
            ],
            Domain.GENERAL: [
                {"name": "gpt-4o-mini", "provider": "openai", "cost": 0.00015},
                {"name": "claude-3-5-haiku", "provider": "anthropic", "cost": 0.0008},
                {"name": "llama-3-70b", "provider": "groq", "cost": 0.00059},
            ],
        }

        # If all_models provided, filter to available models
        if all_models:
            recommended_names = {m["name"] for m in domain_models.get(domain, [])}
            return [m for m in all_models if m.get("name") in recommended_names]

        # Return default recommendations
        return domain_models.get(domain, domain_models[Domain.GENERAL])

    def _calculate_domain_score(
        self,
        query_lower: str,
        keywords: DomainKeywords,
    ) -> float:
        """
        Calculate domain score based on keyword matches.

        Uses research-backed weighting:
        - Very strong: 1.5 (highly discriminative)
        - Strong: 1.0 (domain-specific)
        - Moderate: 0.7 (contextual)
        - Weak: 0.3 (generic)

        Args:
            query_lower: Lowercase query text
            keywords: Domain keywords to match

        Returns:
            Domain score (0-1)
        """
        score = 0.0
        matches = 0

        # Check very strong keywords (weight: 1.5) - NEW
        for keyword in keywords.very_strong:
            if self._keyword_matches(query_lower, keyword):
                score += 1.5
                matches += 1

        # Check strong keywords (weight: 1.0)
        for keyword in keywords.strong:
            if self._keyword_matches(query_lower, keyword):
                score += 1.0
                matches += 1

        # Check moderate keywords (weight: 0.7) - Increased from 0.5
        for keyword in keywords.moderate:
            if self._keyword_matches(query_lower, keyword):
                score += 0.7
                matches += 1

        # Check weak keywords (weight: 0.3) - Increased from 0.25
        for keyword in keywords.weak:
            if self._keyword_matches(query_lower, keyword):
                score += 0.3
                matches += 1

        # Normalize score (max 1.0)
        if matches > 0:
            # Scale by number of matches (more matches = higher confidence)
            # Research: KeyBERT achieves 78% accuracy with semantic weighting
            normalized_score = min(1.0, score / (matches**0.5))
            return normalized_score

        return 0.0

    def _keyword_matches(self, text: str, keyword: str) -> bool:
        """
        Check if keyword matches in text (word boundary aware).

        Args:
            text: Text to search in
            keyword: Keyword to search for

        Returns:
            True if keyword found with word boundaries
        """
        # Use word boundaries to avoid partial matches
        pattern = r"\b" + re.escape(keyword) + r"\b"
        return bool(re.search(pattern, text))


# ============================================================================
# SEMANTIC DOMAIN DETECTION (ML-BASED)
# ============================================================================

# Domain exemplar queries for embedding-based detection
DOMAIN_EXEMPLARS: dict[Domain, list[str]] = {
    Domain.CODE: [
        "Write a Python function to sort a list",
        "Debug this JavaScript async/await code",
        "Implement a binary search algorithm in Java",
        "Create a React component for user authentication",
        "Write unit tests for this API endpoint",
    ],
    Domain.DATA: [
        "Analyze this sales data using pandas",
        "Write a SQL query to find top customers",
        "Calculate correlation between variables",
        "Build a data pipeline to process logs",
        "Create a pivot table from this dataset",
    ],
    Domain.STRUCTURED: [
        "Extract JSON from this text and validate schema",
        "Parse this XML configuration file and convert to YAML",
        "Convert this HTML form to Pydantic dataclass",
        "Extract key-value pairs from invoice using field mapping",
        "Normalize this nested JSON structure and flatten hierarchy",
        "Parse Protobuf definition and generate Python schema",
        "Deserialize Avro data and convert to CSV format",
        "Validate JSON against JSON Schema specification",
    ],
    Domain.RAG: [
        "Search documents for information about taxes",
        "Find relevant passages about climate change",
        "Retrieve documentation for this API",
        "Search knowledge base for troubleshooting steps",
        "Find similar documents to this query",
    ],
    Domain.CONVERSATION: [
        "Continue this conversation about travel plans",
        "Respond to this customer service inquiry",
        "Have a dialogue about book recommendations",
        "Chat about weekend activities",
        "Discuss pros and cons of remote work",
        "How are you today?",
        "Nice to meet you",
        "Let's chat about something",
        "What do you think?",
        "Tell me more",
        "Good morning, how's it going?",
        "Thanks for your help",
    ],
    Domain.TOOL: [
        "Call the weather API for New York",
        "Use the calculator to compute compound interest",
        "Search Wikipedia for information about Einstein",
        "Send an email notification to users",
        "Execute this database query",
    ],
    Domain.CREATIVE: [
        "Write a short story about space exploration",
        "Generate a marketing slogan for eco-friendly products",
        "Create a poem about autumn",
        "Write dialogue for a mystery novel",
        "Generate creative names for a coffee shop",
    ],
    Domain.COMPARISON: [
        "Compare Python vs Java for backend development",
        "What is the difference between TCP and UDP?",
        "iPhone vs Android: pros and cons",
        "Compare AWS and GCP pricing models",
        "Which is better for ML: PyTorch or TensorFlow?",
    ],
    Domain.SUMMARY: [
        "Summarize this research paper in 3 sentences",
        "Give me a brief overview of this article",
        "Condense this meeting transcript",
        "Provide key takeaways from this report",
        "Create an executive summary of this document",
    ],
    Domain.TRANSLATION: [
        "Translate this French text to English",
        "Convert this paragraph from Spanish to German",
        "Translate Japanese instructions to English",
        "How do you say 'thank you' in Mandarin?",
        "Translate this legal document from Italian",
    ],
    Domain.MATH: [
        # Simple arithmetic (for better detection of basic calculations)
        "What is 25 times 17?",
        "Calculate 156 divided by 12",
        "What is 48 + 73?",
        "Multiply 234 by 56",
        # Word problems (grade school / GSM8K style)
        "If I have 45 apples and give away 12, how many remain?",
        "A train travels 120 miles in 2 hours. What's its speed?",
        "Janet sells eggs at the market for $2 each. How much does she make if she sells 15 eggs?",
        "Tom has 20 marbles. He gives 5 to each of his 3 friends. How many does he have left?",
        "A store sells apples at $3 per pound. How much do 4 pounds cost?",
        "If Mary bakes 24 cookies and eats 3 per day, how many days will they last?",
        "John has $50. He buys 3 books at $8 each. How much money does he have left?",
        # Advanced math
        "Solve this differential equation: dy/dx = 2x + 3",
        "Calculate the probability of rolling two sixes",
        "Find the derivative of x^2 + 3x + 2",
        "Prove the Pythagorean theorem using geometric reasoning",
        "Compute the area under this curve using integration",
        "Solve the quadratic equation 3x^2 + 5x - 2 = 0",
    ],
    Domain.FACTUAL: [
        "Is this claim true? Provide sources.",
        "Fact check this statement about vaccines",
        "Verify whether this statistic is accurate",
        "Is it true that honey never spoils?",
        "Debunk this common myth with evidence",
        "What is the capital of France?",
        "When did World War II end?",
        "Who invented the telephone?",
        "What is the population of China?",
        "Is it true that the Earth is round?",
        "What year was the Declaration of Independence signed?",
        "How far is the Moon from Earth?",
    ],
    Domain.MEDICAL: [
        "Explain the symptoms of diabetes",
        "What are treatment options for hypertension?",
        "Describe the cardiovascular system",
        "Interpret this blood test result",
        "What medications interact with aspirin?",
    ],
    Domain.LEGAL: [
        "Analyze this employment contract clause",
        "Explain copyright law for software",
        "Review this non-disclosure agreement",
        "What are tenant rights in California?",
        "Interpret this legal precedent",
    ],
    Domain.FINANCIAL: [
        "Analyze quarterly earnings for tech stocks",
        "Calculate ROI for this investment",
        "Explain the concept of compound interest",
        "Evaluate risk for this portfolio",
        "Forecast revenue based on historical data",
        "Explain compound interest",
        "Calculate ROI on investment",
        "What are the tax implications",
        "Portfolio diversification strategy",
        "Explain P/E ratio",
        "How does inflation affect savings?",
        "What is a mutual fund?",
    ],
    Domain.MULTIMODAL: [
        "Describe what's in this image",
        "Analyze this chart and explain the trend",
        "Read the text from this screenshot",
        "What objects are visible in this photo?",
        "Interpret this diagram and explain it",
    ],
    Domain.GENERAL: [
        "Tell me something interesting",
        "Explain how photosynthesis works",
        "What are the benefits of exercise?",
        "Describe the water cycle",
        "Help me with something",
    ],
}

# Domain-specific confidence thresholds for semantic detection.
# Some domains (conversation, financial, factual) are harder to detect
# and benefit from lower thresholds to avoid falling back to GENERAL.
DOMAIN_THRESHOLDS: dict[Domain, float] = {
    Domain.CODE: 0.65,
    Domain.MEDICAL: 0.70,
    Domain.LEGAL: 0.70,
    Domain.CONVERSATION: 0.50,
    Domain.FINANCIAL: 0.55,
    Domain.FACTUAL: 0.50,
    Domain.GENERAL: 0.40,
}


# Candidate models benchmarked for semantic domain detection quality.
# Keep the default aligned with investigation report findings.
FASTEMBED_DOMAIN_MODELS: tuple[str, ...] = (
    "intfloat/e5-large-v2",
    "BAAI/bge-large-en-v1.5",
    "sentence-transformers/all-MiniLM-L6-v2",
)

# Hybrid tuning constants
HYBRID_RULE_LOCK_CONFIDENCE = 0.82
HYBRID_RULE_LOCK_MARGIN = 0.20
HYBRID_SEMANTIC_HIGH_CONFIDENCE = 0.74
HYBRID_SEMANTIC_MIN_MARGIN = 0.08


class SemanticDomainDetector:
    """
    Optional ML-based domain detector using semantic embeddings.

    Uses cosine similarity between query embedding and pre-computed domain
    exemplar embeddings to detect domain. More accurate than rule-based for
    nuanced queries, but requires FastEmbed installed.

    Features:
    - Semantic similarity-based detection
    - Lazy initialization (model loads on first use)
    - Graceful degradation without FastEmbed
    - Optional hybrid mode (combines with rule-based)

    Attributes:
        embedder: UnifiedEmbeddingService for embeddings
        domain_embeddings: Pre-computed exemplar embeddings per domain
        is_available: Whether ML detection is available
    """

    def __init__(
        self,
        embedder: Optional["UnifiedEmbeddingService"] = None,
        confidence_threshold: float = 0.6,
        use_hybrid: bool = True,
        model_name: str = "intfloat/e5-large-v2",
    ):
        """
        Initialize semantic domain detector.

        Args:
            embedder: Optional UnifiedEmbeddingService (creates new if None)
            confidence_threshold: Minimum similarity for detection (default: 0.6)
            use_hybrid: Whether to combine with rule-based detection (default: True)
            model_name: FastEmbed model used when embedder is not supplied
        """
        self.confidence_threshold = confidence_threshold
        self.use_hybrid = use_hybrid
        self.model_name = model_name

        # Use provided embedder or create new one
        if embedder is not None:
            self.embedder = embedder
        elif HAS_ML:
            self.embedder = UnifiedEmbeddingService(model_name=model_name)
        else:
            self.embedder = None

        # Initialize rule-based detector for hybrid mode
        self.rule_detector = DomainDetector() if use_hybrid else None

        # Domain embeddings (lazy-computed)
        self._domain_embeddings: Optional[dict[Domain, Any]] = None
        self._embeddings_computed = False

        # Check availability
        self.is_available = self.embedder is not None and self.embedder.is_available

        if not self.is_available:
            logger.warning(
                "⚠️ Semantic domain detection unavailable. "
                "Install FastEmbed: pip install fastembed"
            )

    def _compute_domain_embeddings(self):
        """Pre-compute embeddings for all domain exemplars (lazy)."""
        if self._embeddings_computed or not self.is_available:
            return

        logger.info("Computing domain exemplar embeddings...")
        self._domain_embeddings = {}

        for domain, exemplars in DOMAIN_EXEMPLARS.items():
            # Get embeddings for all exemplars
            embeddings = self.embedder.embed_batch(exemplars)
            if embeddings:
                # Average exemplar embeddings to get domain centroid
                try:
                    import numpy as np

                    domain_embedding = np.mean(embeddings, axis=0)
                    self._domain_embeddings[domain] = domain_embedding
                except Exception as e:
                    logger.warning(f"Failed to compute embedding for {domain}: {e}")

        self._embeddings_computed = True
        logger.info(f"✓ Computed embeddings for {len(self._domain_embeddings)} domains")

    def detect(self, query: str) -> tuple[Domain, float]:
        """
        Detect domain from query using semantic similarity.

        Args:
            query: Query text to analyze

        Returns:
            Tuple of (domain, confidence)

        Example:
            >>> detector = SemanticDomainDetector()
            >>> if detector.is_available:
            ...     domain, conf = detector.detect("Create a REST API endpoint")
            ...     print(f"{domain}: {conf:.0%}")
        """
        result = self.detect_with_scores(query)
        return result.domain, result.confidence

    def detect_with_scores(self, query: str) -> DomainDetectionResult:
        """
        Detect domain with detailed scoring.

        Args:
            query: Query text to analyze

        Returns:
            DomainDetectionResult with scores for all domains
        """
        if not self.is_available:
            # Fall back to rule-based if ML unavailable
            if self.rule_detector:
                return self.rule_detector.detect_with_scores(query)
            else:
                return DomainDetectionResult(
                    domain=Domain.GENERAL,
                    confidence=0.5,
                    metadata={"method": "fallback", "available": False},
                )

        # Compute domain embeddings if not done yet
        self._compute_domain_embeddings()

        # Get query embedding
        query_embedding = self.embedder.embed(query)
        if query_embedding is None:
            return DomainDetectionResult(
                domain=Domain.GENERAL,
                confidence=0.5,
                metadata={"method": "fallback", "error": "embedding_failed"},
            )

        # Calculate similarity to each domain
        scores: dict[Domain, float] = {}
        for domain, domain_embedding in self._domain_embeddings.items():
            similarity = self.embedder._cosine_similarity(query_embedding, domain_embedding)
            scores[domain] = float(similarity) if similarity is not None else 0.0

        def _top_domain_margin(domain_scores: dict[Domain, float]) -> tuple[Domain, float, float]:
            if not domain_scores:
                return Domain.GENERAL, 0.0, 0.0
            ranked = sorted(domain_scores.items(), key=lambda item: item[1], reverse=True)
            top_domain, top_score = ranked[0]
            second_score = ranked[1][1] if len(ranked) > 1 else 0.0
            return top_domain, top_score, max(0.0, top_score - second_score)

        # Find best match using domain-specific thresholds
        detected_domain = max(scores, key=scores.get) if scores else Domain.GENERAL
        confidence = scores.get(detected_domain, 0.0)
        domain_threshold = DOMAIN_THRESHOLDS.get(
            detected_domain, self.confidence_threshold
        )
        if not scores or confidence < domain_threshold:
            detected_domain = Domain.GENERAL
            confidence = 0.5

        # Optionally combine with rule-based (hybrid mode)
        if self.use_hybrid and self.rule_detector:
            rule_result = self.rule_detector.detect_with_scores(query)

            semantic_domain, semantic_confidence, semantic_margin = _top_domain_margin(scores)
            rule_domain, rule_confidence, rule_margin = _top_domain_margin(rule_result.scores)

            # Rule detector is currently strongest. Preserve high-confidence rule decisions.
            if (
                rule_domain != Domain.GENERAL
                and rule_confidence >= HYBRID_RULE_LOCK_CONFIDENCE
                and rule_margin >= HYBRID_RULE_LOCK_MARGIN
            ):
                return DomainDetectionResult(
                    domain=rule_result.domain,
                    confidence=rule_result.confidence,
                    scores=rule_result.scores,
                    metadata={
                        "method": "hybrid",
                        "source": "rule_lock",
                        "model_name": self.model_name,
                    },
                )

            # When semantic is confidently differentiating a domain, trust it more.
            semantic_override = (
                semantic_domain != Domain.GENERAL
                and semantic_confidence >= HYBRID_SEMANTIC_HIGH_CONFIDENCE
                and semantic_margin >= HYBRID_SEMANTIC_MIN_MARGIN
            )

            # Adaptive blending: semantic adds value primarily when rule confidence is weak
            # or when both methods agree.
            if semantic_override:
                ml_weight = 0.72
            elif rule_confidence < 0.62:
                ml_weight = 0.62
            elif semantic_domain == rule_domain:
                ml_weight = 0.58
            else:
                ml_weight = 0.40

            rule_weight = 1.0 - ml_weight

            hybrid_scores = {}
            for domain in Domain:
                ml_score = scores.get(domain, 0.0)
                rule_score = rule_result.scores.get(domain, 0.0)
                hybrid_scores[domain] = (ml_score * ml_weight) + (rule_score * rule_weight)

            detected_domain = max(hybrid_scores, key=hybrid_scores.get)
            confidence = hybrid_scores[detected_domain]
            scores = hybrid_scores  # Use hybrid scores

        return DomainDetectionResult(
            domain=detected_domain,
            confidence=confidence,
            scores=scores,
            metadata={
                "method": "hybrid" if self.use_hybrid else "semantic",
                "query_length": len(query),
                "threshold": self.confidence_threshold,
                "model_name": self.model_name,
            },
        )
