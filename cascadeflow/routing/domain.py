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
    SUMMARY = "summary"  # Text summarization, condensing
    TRANSLATION = "translation"  # Language translation
    MATH = "math"  # Mathematical reasoning, calculations
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


# Built-in domain keyword mappings (15 production domains)
DOMAIN_KEYWORDS: dict[Domain, DomainKeywords] = {
    Domain.CODE: DomainKeywords(
        very_strong=[  # Highly discriminative (Research: 77% accuracy)
            "async",
            "await",
            "import",
            "def",
            "return",
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
        very_strong=[  # Multi-turn indicators
            "remember",
            "you said",
            "earlier you mentioned",
            "back to",
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
        ],
        moderate=[
            "help",
            "support",
            "assist",
            "question",
            "clarify",
            "explain",
            "understand",
            "context",
            "referring to",
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
        ],
        weak=["add", "subtract", "multiply", "divide", "number", "math"],
    ),
    Domain.MEDICAL: DomainKeywords(
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
        ],
        moderate=[
            "analysis",
            "forecast",
            "budget",
            "capital",
            "asset",
            "liability",
            "cash flow",
            "dividend",
        ],
        weak=["money", "cost", "price", "pay"],
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
            "look",
            "show",
            "display",
            "caption",
            "describe image",
            "analyze photo",
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
        query_lower = query.lower()

        # Calculate scores for each domain
        scores: dict[Domain, float] = {}

        for domain, keywords in self.keywords.items():
            score = self._calculate_domain_score(query_lower, keywords)
            scores[domain] = score

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
            },
        )

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
        # Default domain-specific model recommendations (15 domains)
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
        "Solve this differential equation: dy/dx = 2x + 3",
        "Calculate the probability of rolling two sixes",
        "Find the derivative of x^2 + 3x + 2",
        "Prove the Pythagorean theorem using geometric reasoning",
        "Compute the area under this curve using integration",
        "Calculate the eigenvalues of matrix [[1,2],[3,4]]",
        "Solve the quadratic equation 3x^2 + 5x - 2 = 0",
        "Find the limit as x approaches infinity of (x^2+1)/x",
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
    ],
    Domain.MULTIMODAL: [
        "Describe what's in this image",
        "Analyze this chart and explain the trend",
        "Read the text from this screenshot",
        "What objects are visible in this photo?",
        "Interpret this diagram and explain it",
    ],
    Domain.GENERAL: [
        "What is the capital of France?",
        "Who invented the telephone?",
        "Explain how photosynthesis works",
        "What are the benefits of exercise?",
        "Describe the water cycle",
    ],
}


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
        use_hybrid: bool = False,
    ):
        """
        Initialize semantic domain detector.

        Args:
            embedder: Optional UnifiedEmbeddingService (creates new if None)
            confidence_threshold: Minimum similarity for detection (default: 0.6)
            use_hybrid: Whether to combine with rule-based detection (default: False)
        """
        self.confidence_threshold = confidence_threshold
        self.use_hybrid = use_hybrid

        # Use provided embedder or create new one
        if embedder is not None:
            self.embedder = embedder
        elif HAS_ML:
            self.embedder = UnifiedEmbeddingService()
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

        # Find best match
        if not scores or max(scores.values()) < self.confidence_threshold:
            detected_domain = Domain.GENERAL
            confidence = 0.5
        else:
            detected_domain = max(scores, key=scores.get)
            confidence = scores[detected_domain]

        # Optionally combine with rule-based (hybrid mode)
        if self.use_hybrid and self.rule_detector:
            rule_result = self.rule_detector.detect_with_scores(query)

            # Average ML and rule-based scores
            hybrid_scores = {}
            for domain in Domain:
                ml_score = scores.get(domain, 0.0)
                rule_score = rule_result.scores.get(domain, 0.0)
                hybrid_scores[domain] = (ml_score + rule_score) / 2

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
            },
        )
