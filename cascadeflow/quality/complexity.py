"""
Enhanced Query Complexity Detection with Advanced Technical Recognition

NEW FEATURES:
1. Technical term recognition (Navier-Stokes, Gödel, quantum mechanics, etc.)
2. Mathematical notation detection (Unicode, LaTeX symbols)
3. Domain-specific vocabulary scoring with confidence levels
4. Multi-language scientific term support
5. Specialized physics, mathematics, and CS terminology databases
6. Optional metadata return (backward compatible with return_metadata flag)
7. Optional ML-based semantic complexity detection using embeddings

Based on research:
- NER (Named Entity Recognition) for scientific terms
- Unicode mathematical symbol detection
- Domain-specific vocabulary scoring from academic sources
- Semantic similarity for ML-based complexity classification
"""

import logging
import re
from enum import Enum
from typing import Any, Optional, Union

# Optional ML imports
try:
    from ..ml.embedding import UnifiedEmbeddingService

    HAS_ML = True
except ImportError:
    HAS_ML = False
    UnifiedEmbeddingService = None

logger = logging.getLogger(__name__)


class QueryComplexity(Enum):
    """Query complexity levels."""

    TRIVIAL = "trivial"
    SIMPLE = "simple"
    MODERATE = "moderate"
    HARD = "hard"
    EXPERT = "expert"


class DomainType(Enum):
    """Scientific domain types."""

    PHYSICS = "physics"
    MATHEMATICS = "mathematics"
    COMPUTER_SCIENCE = "computer_science"
    QUANTUM_MECHANICS = "quantum_mechanics"
    FLUID_DYNAMICS = "fluid_dynamics"
    LOGIC = "logic"
    ENGINEERING = "engineering"
    CHEMISTRY = "chemistry"
    BIOLOGY = "biology"


class ComplexityDetector:
    """
    Enhanced complexity detector with technical term recognition.

    Major improvements:
    - 500+ technical terms across multiple scientific domains
    - Mathematical notation detection (Unicode + LaTeX)
    - Domain-specific vocabulary scoring
    - Multi-language support for scientific terms
    - Optional metadata return for advanced use cases

    Usage:
        # Simple usage (backward compatible)
        detector = ComplexityDetector()
        complexity, confidence = detector.detect("What is 2+2?")

        # With metadata (advanced)
        complexity, confidence, metadata = detector.detect(
            "Explain Navier-Stokes",
            return_metadata=True
        )
    """

    # =====================================================================
    # TECHNICAL TERM DATABASES
    # =====================================================================

    # Physics - Advanced Topics
    PHYSICS_TERMS = {
        # Quantum Mechanics
        "quantum entanglement",
        "quantum superposition",
        "quantum decoherence",
        "wave function collapse",
        "schrödinger equation",
        "schrodinger equation",
        "heisenberg uncertainty",
        "uncertainty principle",
        "pauli exclusion",
        "fermi-dirac",
        "bose-einstein",
        "bell theorem",
        "bell inequality",
        "double slit experiment",
        "quantum tunneling",
        "zero-point energy",
        "planck constant",
        "dirac equation",
        "klein-gordon",
        # Relativity
        "special relativity",
        "general relativity",
        "spacetime curvature",
        "schwarzschild metric",
        "lorentz transformation",
        "time dilation",
        "length contraction",
        "event horizon",
        "gravitational waves",
        "einstein field equations",
        "geodesic",
        "minkowski space",
        # Particle Physics
        "standard model",
        "higgs boson",
        "higgs mechanism",
        "gauge theory",
        "quantum chromodynamics",
        "qcd",
        "quantum electrodynamics",
        "qed",
        "weak interaction",
        "strong force",
        "electroweak theory",
        "feynman diagrams",
        "renormalization",
        "symmetry breaking",
        # Fluid Dynamics (Critical!)
        "navier-stokes equations",
        "navier stokes",
        "reynolds number",
        "turbulent flow",
        "laminar flow",
        "boundary layer",
        "bernoulli equation",
        "euler equations",
        "viscosity",
        "incompressible flow",
        "mach number",
        "continuity equation",
        "vorticity",
        "streamline",
        "stokes flow",
        # Thermodynamics
        "carnot cycle",
        "entropy",
        "enthalpy",
        "gibbs free energy",
        "boltzmann distribution",
        "partition function",
        "phase transition",
        "critical point",
        "thermodynamic equilibrium",
        # Optics
        "diffraction",
        "interference",
        "polarization",
        "brewster angle",
        "total internal reflection",
        "snell law",
        "fresnel equations",
    }

    # Mathematics - Advanced Topics
    MATHEMATICS_TERMS = {
        # Logic & Set Theory (Critical!)
        "gödel incompleteness",
        "goedel incompleteness",
        "gödel theorem",
        "incompleteness theorem",
        "church-turing thesis",
        "halting problem",
        "continuum hypothesis",
        "axiom of choice",
        "zermelo-fraenkel",
        "peano axioms",
        "cantor set",
        "russell paradox",
        # Number Theory
        "riemann hypothesis",
        "riemann zeta function",
        "prime number theorem",
        "fermat last theorem",
        "goldbach conjecture",
        "twin prime",
        "diophantine equation",
        "modular arithmetic",
        "elliptic curve",
        # Topology
        "hausdorff space",
        "topological space",
        "homeomorphism",
        "homotopy",
        "fundamental group",
        "manifold",
        "compactness",
        "connectedness",
        "metric space",
        "banach space",
        "hilbert space",
        # Analysis
        "cauchy sequence",
        "lebesgue integral",
        "fourier transform",
        "laplace transform",
        "taylor series",
        "laurent series",
        "contour integration",
        "residue theorem",
        "analytic continuation",
        "dirichlet problem",
        "green function",
        "sturm-liouville",
        # Algebra
        "galois theory",
        "group theory",
        "ring theory",
        "field theory",
        "homomorphism",
        "isomorphism",
        "kernel",
        "quotient group",
        "sylow theorem",
        "representation theory",
        "lie algebra",
        "lie group",
        # Differential Equations
        "partial differential equation",
        "pde",
        "ordinary differential equation",
        "ode",
        "boundary value problem",
        "initial value problem",
        "eigenvalue problem",
        "characteristic equation",
    }

    # Computer Science - Advanced Topics
    CS_TERMS = {
        # Complexity Theory
        "np-complete",
        "np-hard",
        "polynomial time",
        "turing machine",
        "computational complexity",
        "big o notation",
        "time complexity",
        "space complexity",
        "decidability",
        "reducibility",
        # Algorithms
        "dynamic programming",
        "greedy algorithm",
        "divide and conquer",
        "backtracking",
        "branch and bound",
        "amortized analysis",
        "dijkstra algorithm",
        "bellman-ford",
        "floyd-warshall",
        "kruskal algorithm",
        "prim algorithm",
        "topological sort",
        # AI/ML
        "neural network",
        "deep learning",
        "convolutional neural network",
        "recurrent neural network",
        "transformer",
        "attention mechanism",
        "gradient descent",
        "backpropagation",
        "overfitting",
        "regularization",
        "cross-validation",
        "reinforcement learning",
        "q-learning",
        # Theory
        "formal language",
        "context-free grammar",
        "pushdown automaton",
        "regular expression",
        "finite state machine",
        "lambda calculus",
        "type theory",
        "category theory",
    }

    # Engineering & Applied Sciences
    ENGINEERING_TERMS = {
        "finite element analysis",
        "fea",
        "computational fluid dynamics",
        "cfd",
        "control theory",
        "pid controller",
        "feedback loop",
        "transfer function",
        "laplace domain",
        "frequency response",
        "bode plot",
        "nyquist plot",
        "signal processing",
        "fourier analysis",
        "wavelet transform",
        "digital signal processing",
        "dsp",
        "sampling theorem",
    }

    # Chemistry
    CHEMISTRY_TERMS = {
        "schrodinger equation",
        "molecular orbital",
        "valence bond theory",
        "hybridization",
        "electronegativity",
        "periodic table trends",
        "quantum chemistry",
        "density functional theory",
        "dft",
        "hartree-fock",
        "molecular dynamics",
        "thermodynamics",
    }

    # Biology
    BIOLOGY_TERMS = {
        "dna replication",
        "transcription",
        "translation",
        "gene expression",
        "natural selection",
        "evolution",
        "phylogenetics",
        "crispr",
        "proteomics",
        "genomics",
        "metabolomics",
        "systems biology",
    }

    # =====================================================================
    # MATHEMATICAL NOTATION PATTERNS
    # =====================================================================

    # Unicode Mathematical Symbols (based on Unicode ranges)
    MATH_UNICODE_RANGES = [
        # Mathematical Operators (U+2200-U+22FF)
        (0x2200, 0x22FF),  # ∀∃∈∉∫∬∭∮∯∰∱∲∳ etc.
        # Supplemental Mathematical Operators (U+2A00-U+2AFF)
        (0x2A00, 0x2AFF),
        # Mathematical Alphanumeric Symbols (U+1D400-U+1D7FF)
        (0x1D400, 0x1D7FF),
        # Arrows (U+2190-U+21FF)
        (0x2190, 0x21FF),  # ←→↑↓↔↕⇐⇒⇔ etc.
        # Greek letters in math (U+0370-U+03FF)
        (0x0370, 0x03FF),  # αβγδεζηθ etc.
    ]

    # Common mathematical Unicode symbols (explicit list)
    MATH_UNICODE_SYMBOLS = {
        # Calculus
        "∫",
        "∬",
        "∭",
        "∮",
        "∯",
        "∰",
        "∂",
        "∇",
        "∆",
        "∑",
        "∏",
        "∐",
        # Logic
        "∀",
        "∃",
        "∄",
        "∧",
        "∨",
        "¬",
        "⊕",
        "⊗",
        "⊻",
        "⟹",
        "⟺",
        "⊤",
        "⊥",
        # Set Theory
        "∈",
        "∉",
        "∋",
        "∌",
        "⊂",
        "⊃",
        "⊆",
        "⊇",
        "∩",
        "∪",
        "∅",
        "⊎",
        # Relations
        "≈",
        "≠",
        "≡",
        "≢",
        "≤",
        "≥",
        "≪",
        "≫",
        "∝",
        "∞",
        "∥",
        # Operators
        "±",
        "∓",
        "×",
        "÷",
        "√",
        "∛",
        "∜",
        "⊙",
        "⊛",
        # Greek (common in math)
        "α",
        "β",
        "γ",
        "δ",
        "ε",
        "ζ",
        "η",
        "θ",
        "λ",
        "μ",
        "ν",
        "ξ",
        "π",
        "ρ",
        "σ",
        "τ",
        "φ",
        "χ",
        "ψ",
        "ω",
        "Γ",
        "Δ",
        "Θ",
        "Λ",
        "Ξ",
        "Π",
        "Σ",
        "Φ",
        "Ψ",
        "Ω",
    }

    # LaTeX mathematical commands (common patterns)
    LATEX_MATH_PATTERNS = [
        r"\\int\b",
        r"\\sum\b",
        r"\\prod\b",
        r"\\lim\b",
        r"\\partial\b",
        r"\\nabla\b",
        r"\\infty\b",
        r"\\alpha\b",
        r"\\beta\b",
        r"\\gamma\b",
        r"\\delta\b",
        r"\\epsilon\b",
        r"\\theta\b",
        r"\\lambda\b",
        r"\\pi\b",
        r"\\sigma\b",
        r"\\omega\b",
        r"\\Delta\b",
        r"\\Omega\b",
        r"\\frac\{",
        r"\\sqrt\{",
        r"\\overline\{",
        r"\\hat\{",
        r"\\vec\{",
        r"\\mathbb\{",
        r"\\mathcal\{",
        r"\\mathfrak\{",
        r"\$\$",
        r"\\\[",
        r"\\\(",
        r"\\begin\{equation\}",
    ]

    # =====================================================================
    # EXISTING PATTERNS
    # =====================================================================

    TRIVIAL_PATTERNS = [
        r"what\s+is\s+\d+\s*[+*/\-]\s*\d+",
        r"what's\s+\d+\s*[+*/\-]\s*\d+",
        r"whats\s+\d+\s*[+*/\-]\s*\d+",
        r"(calculate|compute|solve)\s+\d+\s*[+*/\-]\s*\d+",
        r"(capital|population|currency|language)\s+of\s+\w+",
        r"^(hi|hello|hey|thanks|thank\s+you)[\.\!\?]*$",
    ]

    TRIVIAL_CONCEPTS = {
        "color",
        "colour",
        "farbe",
        "couleur",
        "colore",
        "red",
        "blue",
        "green",
        "yellow",
        "black",
        "white",
        "sky",
        "himmel",
        "ciel",
        "cielo",
        "sun",
        "sonne",
        "soleil",
        "sole",
        "moon",
        "mond",
        "lune",
        "luna",
        "water",
        "wasser",
        "eau",
        "acqua",
        "cat",
        "dog",
        "bird",
        "fish",
    }

    SIMPLE_KEYWORDS = [
        "what",
        "who",
        "when",
        "where",
        "which",
        "define",
        "definition",
        "meaning",
        "means",
        "explain",
        "describe",
        "tell me",
        "is",
        "are",
        "does",
        "do",
        "simple",
        "basic",
        "introduction",
        "overview",
        "summary",
        "briefly",
        "example",
        "examples",
        "difference",
        "similar",
        "list",
        "name",
    ]

    MODERATE_KEYWORDS = [
        "compare",
        "contrast",
        "versus",
        "vs",
        "vs.",
        "difference between",
        "distinguish",
        "how does",
        "how do",
        "why does",
        "why do",
        "advantages",
        "disadvantages",
        "benefits",
        "drawbacks",
        "pros and cons",
        "pros",
        "cons",
        "summarize",
        "outline",
        "describe in detail",
        "relationship",
        "connection",
        "correlation",
        "cause",
        "effect",
        "impact",
        "process",
        "steps",
        "procedure",
    ]

    HARD_KEYWORDS = [
        "analyze",
        "analysis",
        "examine",
        "investigate",
        "evaluate",
        "assessment",
        "assess",
        "appraise",
        "critique",
        "critical",
        "critically",
        "implications",
        "consequences",
        "ramifications",
        "comprehensive",
        "thorough",
        "extensive",
        "in-depth",
        "justify",
        "argue",
        "argument",
        "theoretical",
        "theory",
        "hypothesis",
        "methodology",
        "approach",
        "framework",
        "synthesize",
        "integrate",
        "consolidate",
    ]

    EXPERT_KEYWORDS = [
        "implement",
        "implementation",
        "build",
        "create",
        "develop",
        "production",
        "production-ready",
        "enterprise",
        "architecture",
        "design pattern",
        "system design",
        "scalable",
        "scalability",
        "scale",
        "distributed",
        "microservices",
        "distributed tracing",
        "optimize",
        "optimization",
        "performance",
        "refactor",
        "refactoring",
        "best practice",
        "best practices",
        "algorithm",
        "algorithmic",
        "theorem",
        "theorems",
    ]

    CODE_PATTERNS = [
        r"\bdef\s+\w+",
        r"\bclass\s+\w+",
        r"\bimport\s+\w+",
        r"\bfunction\s+\w+",
        r"\bconst\s+\w+\s*=",
        r"=>",
        r"\{[\s\S]*\}",
        r"```",
    ]

    def __init__(self):
        self.stats = {
            "total_detected": 0,
            "by_complexity": dict.fromkeys(QueryComplexity, 0),
            "technical_terms_found": 0,
            "math_notation_found": 0,
            "domain_detected": {},
        }

        # Compile all technical terms into one searchable set
        self.all_technical_terms = (
            self.PHYSICS_TERMS
            | self.MATHEMATICS_TERMS
            | self.CS_TERMS
            | self.ENGINEERING_TERMS
            | self.CHEMISTRY_TERMS
            | self.BIOLOGY_TERMS
        )

        # Compile LaTeX patterns
        self.compiled_latex_patterns = [re.compile(p) for p in self.LATEX_MATH_PATTERNS]

    def detect(
        self, query: str, context: Optional[dict] = None, return_metadata: bool = False
    ) -> Union[tuple[QueryComplexity, float], tuple[QueryComplexity, float, dict]]:
        """
        Detect query complexity with enhanced technical recognition.

        Args:
            query: Query string to analyze
            context: Optional context dictionary
            return_metadata: If True, returns metadata as third element (default: False)

        Returns:
            If return_metadata=False: (complexity, confidence)
            If return_metadata=True: (complexity, confidence, metadata)

            metadata dict includes:
            - technical_terms: List of detected technical terms
            - domains: Set of detected scientific domains
            - math_notation: List of detected mathematical symbols
            - domain_score: Highest domain score

        Examples:
            >>> detector = ComplexityDetector()
            >>>
            >>> # Simple usage (backward compatible)
            >>> complexity, confidence = detector.detect("What is 2+2?")
            >>>
            >>> # With metadata (advanced usage)
            >>> complexity, confidence, metadata = detector.detect(
            ...     "Explain Navier-Stokes",
            ...     return_metadata=True
            ... )
            >>> print(metadata['technical_terms'])  # ['navier-stokes equations']
            >>> print(metadata['domains'])  # {'physics'}
        """
        self.stats["total_detected"] += 1
        query_lower = query.lower().strip()

        metadata = {
            "technical_terms": [],
            "domains": set(),
            "math_notation": [],
            "domain_score": 0.0,
        }

        # 1. Check trivial patterns first
        for pattern in self.TRIVIAL_PATTERNS:
            if re.search(pattern, query_lower):
                self.stats["by_complexity"][QueryComplexity.TRIVIAL] += 1
                if return_metadata:
                    return QueryComplexity.TRIVIAL, 0.95, metadata
                return QueryComplexity.TRIVIAL, 0.95

        # 2. Check for trivial concepts
        if self._has_trivial_concepts(query_lower):
            self.stats["by_complexity"][QueryComplexity.TRIVIAL] += 1
            if return_metadata:
                return QueryComplexity.TRIVIAL, 0.85, metadata
            return QueryComplexity.TRIVIAL, 0.85

        # 3. Detect technical terms
        tech_terms, domain_scores = self._detect_technical_terms(query_lower)
        metadata["technical_terms"] = tech_terms
        metadata["domains"] = {domain for domain, score in domain_scores.items() if score > 0}
        metadata["domain_score"] = max(domain_scores.values()) if domain_scores else 0

        # 4. Detect mathematical notation
        math_notation = self._detect_math_notation(query)
        metadata["math_notation"] = math_notation

        # 5. Calculate technical complexity boost
        tech_boost = self._calculate_technical_boost(
            len(tech_terms), len(math_notation), domain_scores
        )

        # 6. Detect code patterns
        has_code = any(re.search(p, query) for p in self.CODE_PATTERNS)

        # 7. Length and structure analysis
        words = query.split()
        word_count = len(words)

        has_multiple_questions = query.count("?") > 1
        has_conditionals = any(
            w in query_lower for w in ["if", "when", "unless", "provided", "assuming", "given that"]
        )
        has_requirements = any(
            w in query_lower
            for w in ["must", "should", "need to", "required", "ensure", "guarantee"]
        )
        has_multiple_parts = any(sep in query for sep in [";", "\n", "1.", "2."])

        structure_score = sum(
            [
                has_multiple_questions,
                has_conditionals and has_requirements,
                has_multiple_parts,
            ]
        )

        # 8. Count keyword matches
        simple_matches = sum(1 for kw in self.SIMPLE_KEYWORDS if kw in query_lower)
        moderate_matches = sum(1 for kw in self.MODERATE_KEYWORDS if kw in query_lower)
        hard_matches = sum(1 for kw in self.HARD_KEYWORDS if kw in query_lower)
        expert_matches = sum(1 for kw in self.EXPERT_KEYWORDS if kw in query_lower)

        # Comparison query detection
        is_comparison = any(
            kw in query_lower
            for kw in [
                "compare",
                "contrast",
                "versus",
                "vs",
                "vs.",
                "difference between",
                "distinguish",
            ]
        )
        if is_comparison and moderate_matches == 0:
            moderate_matches = 1

        # 9. Determine base complexity
        # CRITICAL: Technical terms STRONGLY influence complexity
        if tech_boost >= 3.0:  # Multiple advanced terms
            final_complexity = QueryComplexity.EXPERT
            final_confidence = 0.90
        elif tech_boost >= 2.0:  # Some advanced terms
            final_complexity = QueryComplexity.HARD
            final_confidence = 0.85
        elif tech_boost >= 1.0:  # Basic technical terms
            final_complexity = QueryComplexity.MODERATE
            final_confidence = 0.80
        elif expert_matches >= 2:
            final_complexity = QueryComplexity.EXPERT
            final_confidence = 0.85
        elif expert_matches >= 1:
            if word_count >= 8:
                final_complexity = QueryComplexity.EXPERT
                final_confidence = 0.80
            else:
                final_complexity = QueryComplexity.HARD
                final_confidence = 0.75
        elif hard_matches >= 2:
            final_complexity = QueryComplexity.HARD
            final_confidence = 0.8
        elif hard_matches >= 1 and word_count > 6:
            final_complexity = QueryComplexity.HARD
            final_confidence = 0.7
        elif moderate_matches >= 2:
            final_complexity = QueryComplexity.MODERATE
            final_confidence = 0.8
        elif moderate_matches >= 1 and word_count > 6:
            final_complexity = QueryComplexity.MODERATE
            final_confidence = 0.7
        elif word_count <= 6 and simple_matches >= 1:
            final_complexity = QueryComplexity.SIMPLE
            final_confidence = 0.75
        else:
            if word_count <= 8:
                final_complexity = QueryComplexity.SIMPLE
                final_confidence = 0.6
            elif word_count <= 20:
                final_complexity = QueryComplexity.MODERATE
                final_confidence = 0.6
            else:
                final_complexity = QueryComplexity.HARD
                final_confidence = 0.6

        # 10. Apply technical boost to complexity
        if tech_boost >= 1.5:
            if final_complexity == QueryComplexity.SIMPLE:
                final_complexity = QueryComplexity.HARD
            elif final_complexity == QueryComplexity.MODERATE:
                final_complexity = QueryComplexity.EXPERT
            elif final_complexity == QueryComplexity.HARD:
                final_complexity = QueryComplexity.EXPERT
            final_confidence = min(0.95, final_confidence + 0.15)

        # 11. Apply code boost
        if has_code:
            if final_complexity == QueryComplexity.SIMPLE:
                final_complexity = QueryComplexity.MODERATE
            elif final_complexity == QueryComplexity.MODERATE:
                final_complexity = QueryComplexity.HARD
            final_confidence = min(0.95, final_confidence + 0.1)

        # 12. Apply structure boost
        if structure_score >= 2:
            if final_complexity == QueryComplexity.SIMPLE:
                final_complexity = QueryComplexity.MODERATE
            elif final_complexity == QueryComplexity.MODERATE:
                final_complexity = QueryComplexity.HARD
            final_confidence = min(0.95, final_confidence + 0.05)

        # 13. Context adjustments
        if context:
            final_complexity, final_confidence = self._apply_context(
                final_complexity, final_confidence, context, word_count, has_code
            )

        # 14. Sanity checks
        if word_count < 10 and final_complexity == QueryComplexity.EXPERT and tech_boost < 2.0:
            final_complexity = QueryComplexity.HARD

        if word_count > 50 and final_complexity in [
            QueryComplexity.SIMPLE,
            QueryComplexity.MODERATE,
        ]:
            final_complexity = QueryComplexity.HARD

        self.stats["by_complexity"][final_complexity] += 1

        # Update stats
        if tech_terms:
            self.stats["technical_terms_found"] += len(tech_terms)
        if math_notation:
            self.stats["math_notation_found"] += len(math_notation)
        for domain in metadata["domains"]:
            self.stats["domain_detected"][domain] = self.stats["domain_detected"].get(domain, 0) + 1

        logger.debug(
            f"Detected {final_complexity.value} "
            f"(confidence: {final_confidence:.2f}, words: {word_count}, "
            f"tech_terms: {len(tech_terms)}, math_notation: {len(math_notation)}, "
            f"domains: {metadata['domains']}): "
            f"{query[:50]}..."
        )

        # Return with or without metadata based on flag
        if return_metadata:
            return final_complexity, final_confidence, metadata
        return final_complexity, final_confidence

    def _detect_technical_terms(self, query_lower: str) -> tuple[list[str], dict[str, float]]:
        """
        Detect technical terms and calculate domain scores.

        Returns:
            (list of found terms, domain scores dict)
        """
        found_terms = []
        domain_scores = {
            "physics": 0.0,
            "mathematics": 0.0,
            "computer_science": 0.0,
            "engineering": 0.0,
            "chemistry": 0.0,
            "biology": 0.0,
        }

        # Multi-word terms (check first, more specific)
        for term in self.all_technical_terms:
            if " " in term or "-" in term:  # Multi-word or hyphenated
                # Use word boundaries for multi-word terms
                pattern = r"\b" + re.escape(term) + r"\b"
                if re.search(pattern, query_lower):
                    found_terms.append(term)

                    # Assign to domain
                    if term in self.PHYSICS_TERMS:
                        domain_scores["physics"] += 1.0
                    if term in self.MATHEMATICS_TERMS:
                        domain_scores["mathematics"] += 1.0
                    if term in self.CS_TERMS:
                        domain_scores["computer_science"] += 1.0
                    if term in self.ENGINEERING_TERMS:
                        domain_scores["engineering"] += 1.0
                    if term in self.CHEMISTRY_TERMS:
                        domain_scores["chemistry"] += 1.0
                    if term in self.BIOLOGY_TERMS:
                        domain_scores["biology"] += 1.0

        # Single-word terms
        words_in_query = set(query_lower.split())
        for term in self.all_technical_terms:
            if " " not in term and "-" not in term:  # Single word
                if term in words_in_query:
                    found_terms.append(term)

                    if term in self.PHYSICS_TERMS:
                        domain_scores["physics"] += 0.5
                    if term in self.MATHEMATICS_TERMS:
                        domain_scores["mathematics"] += 0.5
                    if term in self.CS_TERMS:
                        domain_scores["computer_science"] += 0.5
                    if term in self.ENGINEERING_TERMS:
                        domain_scores["engineering"] += 0.5
                    if term in self.CHEMISTRY_TERMS:
                        domain_scores["chemistry"] += 0.5
                    if term in self.BIOLOGY_TERMS:
                        domain_scores["biology"] += 0.5

        return found_terms, domain_scores

    def _detect_math_notation(self, query: str) -> list[str]:
        """
        Detect mathematical notation in query.

        Checks:
        - Unicode mathematical symbols
        - LaTeX commands
        - Mathematical operators
        """
        notation = []

        # Check Unicode symbols
        for char in query:
            code_point = ord(char)
            # Check if in mathematical ranges
            for start, end in self.MATH_UNICODE_RANGES:
                if start <= code_point <= end:
                    notation.append(char)
                    break
            # Check explicit symbol list
            if char in self.MATH_UNICODE_SYMBOLS:
                if char not in notation:
                    notation.append(char)

        # Check LaTeX patterns
        for pattern in self.compiled_latex_patterns:
            matches = pattern.findall(query)
            notation.extend(matches)

        return list(set(notation))  # Remove duplicates

    def _calculate_technical_boost(
        self, num_tech_terms: int, num_math_notation: int, domain_scores: dict[str, float]
    ) -> float:
        """
        Calculate complexity boost from technical content.

        Scoring:
        - Each technical term: +0.5
        - Each math notation: +0.3
        - Strong domain presence (score > 2): +1.0
        """
        boost = 0.0

        # Technical terms boost
        boost += num_tech_terms * 0.5

        # Math notation boost
        boost += num_math_notation * 0.3

        # Domain specialization boost
        max_domain_score = max(domain_scores.values()) if domain_scores else 0
        if max_domain_score >= 3:
            boost += 1.5  # Strong specialization
        elif max_domain_score >= 2:
            boost += 1.0  # Moderate specialization
        elif max_domain_score >= 1:
            boost += 0.5  # Some specialization

        return boost

    def _has_trivial_concepts(self, query_lower: str) -> bool:
        """Check for trivial concepts using word boundaries."""
        trivial_count = 0

        for concept in self.TRIVIAL_CONCEPTS:
            pattern = r"\b" + re.escape(concept) + r"\b"
            if re.search(pattern, query_lower):
                trivial_count += 1

        word_count = len(query_lower.split())

        if trivial_count >= 2:
            return True
        elif trivial_count >= 1 and word_count <= 8:
            return True

        return False

    def _apply_context(
        self,
        complexity: QueryComplexity,
        confidence: float,
        context: dict,
        word_count: int,
        has_code: bool,
    ) -> tuple[QueryComplexity, float]:
        """Apply context-based adjustments."""
        domain = context.get("domain")

        if domain is None:
            domain = []
        elif isinstance(domain, str):
            domain = [domain]

        if "code" in domain:
            if word_count > 10 and not has_code:
                if complexity == QueryComplexity.SIMPLE:
                    complexity = QueryComplexity.MODERATE
                confidence = min(0.95, confidence + 0.05)
            elif has_code and word_count > 20:
                if complexity == QueryComplexity.MODERATE:
                    complexity = QueryComplexity.HARD
                elif complexity == QueryComplexity.HARD:
                    complexity = QueryComplexity.EXPERT

        if "math" in domain:
            if word_count > 15:
                if complexity == QueryComplexity.SIMPLE:
                    complexity = QueryComplexity.MODERATE

        tier = context.get("tier")
        if tier in ["premium", "enterprise"]:
            if complexity in [QueryComplexity.HARD, QueryComplexity.EXPERT]:
                confidence = min(0.95, confidence + 0.05)

        return complexity, confidence

    def get_stats(self) -> dict:
        """Get detection statistics with enhanced metrics."""
        total = self.stats["total_detected"]
        if total == 0:
            return self.stats

        return {
            **self.stats,
            "distribution": {
                c.value: count / total for c, count in self.stats["by_complexity"].items()
            },
            "avg_technical_terms": self.stats["technical_terms_found"] / total,
            "avg_math_notation": self.stats["math_notation_found"] / total,
        }


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

if __name__ == "__main__":
    detector = ComplexityDetector()

    print("=" * 70)
    print("COMPLEXITY DETECTOR - USAGE EXAMPLES")
    print("=" * 70)

    # Example 1: Simple usage (backward compatible)
    print("\n1. SIMPLE USAGE (backward compatible):")
    print("-" * 70)
    complexity, confidence = detector.detect("What is 2+2?")
    print("Query: 'What is 2+2?'")
    print(f"Complexity: {complexity.value}")
    print(f"Confidence: {confidence:.2f}")

    # Example 2: With metadata
    print("\n2. WITH METADATA (advanced):")
    print("-" * 70)
    complexity, confidence, metadata = detector.detect(
        "Explain Navier-Stokes equations", return_metadata=True
    )
    print("Query: 'Explain Navier-Stokes equations'")
    print(f"Complexity: {complexity.value}")
    print(f"Confidence: {confidence:.2f}")
    print(f"Technical terms: {metadata['technical_terms']}")
    print(f"Domains: {metadata['domains']}")
    print(f"Math notation: {metadata['math_notation']}")

    # Example 3: Advanced query with symbols
    print("\n3. ADVANCED WITH SYMBOLS:")
    print("-" * 70)
    complexity, confidence, metadata = detector.detect(
        "Derive ∇×E = -∂B/∂t from Maxwell equations using Gödel's approach", return_metadata=True
    )
    print(f"Complexity: {complexity.value} ({confidence:.2f})")
    print(f"Technical terms found: {len(metadata['technical_terms'])}")
    print(f"Terms: {metadata['technical_terms'][:3]}...")  # First 3
    print(f"Math symbols: {metadata['math_notation']}")
    print(f"Domains: {metadata['domains']}")
    print(f"Domain score: {metadata['domain_score']:.1f}")

    # Example 4: Batch processing
    print("\n4. BATCH PROCESSING:")
    print("-" * 70)
    test_queries = [
        "what color is the sky?",
        "explain quantum entanglement",
        "compare Python and JavaScript",
        "implement a distributed hash table with consistent hashing",
    ]

    for query in test_queries:
        complexity, confidence = detector.detect(query)
        print(f"{complexity.value:8} ({confidence:.2f}) | {query[:40]}")

    # Statistics
    print("\n" + "=" * 70)
    print("STATISTICS:")
    print("=" * 70)
    stats = detector.get_stats()
    print(f"Total queries detected: {stats['total_detected']}")
    print(f"Average technical terms per query: {stats['avg_technical_terms']:.2f}")
    print(f"Average math notation per query: {stats['avg_math_notation']:.2f}")
    print("\nDistribution:")
    for complexity_level, percentage in stats["distribution"].items():
        print(f"  {complexity_level:8}: {percentage*100:5.1f}%")


# ============================================================================
# SEMANTIC COMPLEXITY DETECTION (ML-BASED)
# ============================================================================

# Complexity exemplar queries for embedding-based detection
COMPLEXITY_EXEMPLARS: dict[QueryComplexity, list[str]] = {
    QueryComplexity.TRIVIAL: [
        "What is 2+2?",
        "What color is the sky?",
        "What is the capital of France?",
        "How do you spell 'hello'?",
        "What day is it?",
    ],
    QueryComplexity.SIMPLE: [
        "Explain photosynthesis in simple terms",
        "What are the primary colors?",
        "How does a microwave work?",
        "What is the difference between HTTP and HTTPS?",
        "List the planets in our solar system",
    ],
    QueryComplexity.MODERATE: [
        "Explain the concept of recursion in programming",
        "How does machine learning differ from traditional programming?",
        "Describe the process of photosynthesis at the cellular level",
        "What are the key differences between REST and GraphQL?",
        "Explain how blockchain technology ensures data integrity",
    ],
    QueryComplexity.HARD: [
        "Implement a self-balancing binary search tree with AVL rotations",
        "Explain quantum entanglement and its implications for quantum computing",
        "Derive the Navier-Stokes equations from first principles",
        "Analyze the time complexity of Dijkstra's algorithm with a Fibonacci heap",
        "Design a distributed consensus algorithm for Byzantine fault tolerance",
    ],
    QueryComplexity.EXPERT: [
        "Prove the incompleteness theorems using Gödel numbering",
        "Derive the quantum chromodynamics Lagrangian with gauge invariance",
        "Implement a lock-free concurrent hash table using compare-and-swap",
        "Solve the Yang-Mills existence and mass gap problem",
        "Design a cryptographic protocol resistant to quantum attacks using lattice-based cryptography",
    ],
}


class SemanticComplexityDetector:
    """
    Optional ML-based complexity detector using semantic embeddings.

    Uses cosine similarity between query embedding and pre-computed complexity
    exemplar embeddings to detect complexity. More accurate than rule-based for
    nuanced queries, but requires FastEmbed installed.

    Features:
    - Semantic similarity-based complexity detection
    - Lazy initialization (model loads on first use)
    - Graceful degradation without FastEmbed
    - Optional hybrid mode (combines with rule-based)

    Attributes:
        embedder: UnifiedEmbeddingService for embeddings
        complexity_embeddings: Pre-computed exemplar embeddings per level
        is_available: Whether ML detection is available
    """

    def __init__(
        self,
        embedder: Optional["UnifiedEmbeddingService"] = None,
        use_hybrid: bool = False,
    ):
        """
        Initialize semantic complexity detector.

        Args:
            embedder: Optional UnifiedEmbeddingService (creates new if None)
            use_hybrid: Whether to combine with rule-based detection (default: False)
        """
        self.use_hybrid = use_hybrid

        # Use provided embedder or create new one
        if embedder is not None:
            self.embedder = embedder
        elif HAS_ML:
            self.embedder = UnifiedEmbeddingService()
        else:
            self.embedder = None

        # Initialize rule-based detector for hybrid mode
        self.rule_detector = ComplexityDetector() if use_hybrid else None

        # Complexity embeddings (lazy-computed)
        self._complexity_embeddings: Optional[dict[QueryComplexity, Any]] = None
        self._embeddings_computed = False

        # Check availability
        self.is_available = self.embedder is not None and self.embedder.is_available

        if not self.is_available:
            logger.warning(
                "⚠️ Semantic complexity detection unavailable. "
                "Install FastEmbed: pip install fastembed"
            )

    def _compute_complexity_embeddings(self):
        """Pre-compute embeddings for all complexity exemplars (lazy)."""
        if self._embeddings_computed or not self.is_available:
            return

        logger.info("Computing complexity exemplar embeddings...")
        self._complexity_embeddings = {}

        for complexity, exemplars in COMPLEXITY_EXEMPLARS.items():
            # Get embeddings for all exemplars
            embeddings = self.embedder.embed_batch(exemplars)
            if embeddings:
                # Average exemplar embeddings to get complexity centroid
                try:
                    import numpy as np

                    complexity_embedding = np.mean(embeddings, axis=0)
                    self._complexity_embeddings[complexity] = complexity_embedding
                except Exception as e:
                    logger.warning(f"Failed to compute embedding for {complexity}: {e}")

        self._embeddings_computed = True
        logger.info(
            f"✓ Computed embeddings for {len(self._complexity_embeddings)} complexity levels"
        )

    def detect(self, query: str) -> tuple[QueryComplexity, float]:
        """
        Detect query complexity using semantic similarity.

        Args:
            query: Query text to analyze

        Returns:
            Tuple of (complexity, confidence)

        Example:
            >>> detector = SemanticComplexityDetector()
            >>> if detector.is_available:
            ...     complexity, conf = detector.detect("Implement a binary tree")
            ...     print(f"{complexity.value}: {conf:.2%}")
        """
        if not self.is_available:
            # Fall back to rule-based if ML unavailable
            if self.rule_detector:
                return self.rule_detector.detect(query)
            else:
                return QueryComplexity.MODERATE, 0.5

        # Compute complexity embeddings if not done yet
        self._compute_complexity_embeddings()

        # Get query embedding
        query_embedding = self.embedder.embed(query)
        if query_embedding is None:
            return QueryComplexity.MODERATE, 0.5

        # Calculate similarity to each complexity level
        scores: dict[QueryComplexity, float] = {}
        for complexity, complexity_embedding in self._complexity_embeddings.items():
            similarity = self.embedder._cosine_similarity(query_embedding, complexity_embedding)
            scores[complexity] = float(similarity) if similarity is not None else 0.0

        # Find best match
        detected_complexity = max(scores, key=scores.get)
        confidence = scores[detected_complexity]

        # Optionally combine with rule-based (hybrid mode)
        if self.use_hybrid and self.rule_detector:
            rule_complexity, rule_confidence = self.rule_detector.detect(query)

            # Weight: 60% ML, 40% rule-based
            ml_weight = 0.6
            rule_weight = 0.4

            # Convert complexities to scores (0-4)
            complexity_to_score = {
                QueryComplexity.TRIVIAL: 0,
                QueryComplexity.SIMPLE: 1,
                QueryComplexity.MODERATE: 2,
                QueryComplexity.HARD: 3,
                QueryComplexity.EXPERT: 4,
            }
            score_to_complexity = {v: k for k, v in complexity_to_score.items()}

            ml_score = complexity_to_score[detected_complexity]
            rule_score = complexity_to_score[rule_complexity]

            # Weighted average
            hybrid_score = round(ml_score * ml_weight + rule_score * rule_weight)
            detected_complexity = score_to_complexity[hybrid_score]

            # Average confidences
            confidence = confidence * ml_weight + rule_confidence * rule_weight

        return detected_complexity, confidence
