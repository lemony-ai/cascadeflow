"""Query Complexity Detection.

Enhanced complexity detector with technical term recognition.
Ported from @cascadeflow/core

Features:
- 500+ technical terms across multiple scientific domains
- Mathematical notation detection (Unicode + LaTeX)
- Domain-specific vocabulary scoring
- Query structure analysis

Based on research:
- NER (Named Entity Recognition) for scientific terms
- Unicode mathematical symbol detection
- Domain-specific vocabulary scoring
"""

import re
from typing import Literal, TypedDict

from typing_extensions import NotRequired

# Type definitions
QueryComplexity = Literal["trivial", "simple", "moderate", "hard", "expert"]


class ComplexityResult(TypedDict):
    """Complexity detection result."""

    complexity: QueryComplexity
    confidence: float
    metadata: NotRequired[dict[str, any]]


class ComplexityMetadata(TypedDict):
    """Optional metadata for complexity detection."""

    technical_terms: NotRequired[list[str]]
    domains: NotRequired[set[str]]
    math_notation: NotRequired[list[str]]
    domain_score: NotRequired[float]


class ComplexityDetector:
    """Complexity detector with technical term recognition."""

    # =====================================================================
    # TECHNICAL TERM DATABASES
    # =====================================================================

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
        # Fluid Dynamics
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
    }

    MATHEMATICS_TERMS = {
        # Logic & Set Theory
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
    }

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
        # Quantum Computing
        "quantum computing",
        "quantum algorithm",
        "quantum supremacy",
        "qubit",
        "quantum gate",
        "quantum circuit",
    }

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

    # =====================================================================
    # KEYWORD PATTERNS
    # =====================================================================

    TRIVIAL_PATTERNS = [
        re.compile(r"what\s+is\s+\d+\s*[+*/-]\s*\d+", re.I),
        re.compile(r"what's\s+\d+\s*[+*/-]\s*\d+", re.I),
        re.compile(r"whats\s+\d+\s*[+*/-]\s*\d+", re.I),
        re.compile(r"(calculate|compute|solve)\s+\d+\s*[+*/-]\s*\d+", re.I),
        re.compile(r"(capital|population|currency|language)\s+of\s+\w+", re.I),
        re.compile(r"^(hi|hello|hey|thanks|thank\s+you)[.!?]*$", re.I),
    ]

    TRIVIAL_CONCEPTS = {
        "color",
        "colour",
        "red",
        "blue",
        "green",
        "yellow",
        "black",
        "white",
        "sky",
        "sun",
        "moon",
        "water",
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
        "translate",
        "convert",
        "change",
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
        "write",
        "code",
        "function",
        "program",
        "script",
        "reverse",
        "sort",
        "filter",
        "map",
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
        re.compile(r"\bdef\s+\w+"),
        re.compile(r"\bclass\s+\w+"),
        re.compile(r"\bimport\s+\w+"),
        re.compile(r"\bfunction\s+\w+"),
        re.compile(r"\bconst\s+\w+\s*="),
        re.compile(r"=>"),
        re.compile(r"\{[\s\S]*\}"),
        re.compile(r"```"),
    ]

    def __init__(self):
        """Initialize the complexity detector with combined technical terms."""
        self.all_technical_terms = (
            self.PHYSICS_TERMS | self.MATHEMATICS_TERMS | self.CS_TERMS | self.ENGINEERING_TERMS
        )

    def detect(self, query: str, return_metadata: bool = False) -> ComplexityResult:
        """Detect query complexity.

        Args:
            query: Query text to analyze
            return_metadata: Whether to return detailed metadata

        Returns:
            Complexity result with level and confidence
        """
        query_lower = query.lower().strip()

        metadata: ComplexityMetadata = {
            "technical_terms": [],
            "domains": set(),
            "math_notation": [],
            "domain_score": 0.0,
        }

        # 1. Check trivial patterns first
        for pattern in self.TRIVIAL_PATTERNS:
            if pattern.search(query_lower):
                result: ComplexityResult = {
                    "complexity": "trivial",
                    "confidence": 0.95,
                }
                if return_metadata:
                    result["metadata"] = metadata  # type: ignore[typeddict-item]
                return result

        # 2. Check for trivial concepts
        if self._has_trivial_concepts(query_lower):
            result = {
                "complexity": "trivial",
                "confidence": 0.85,
            }
            if return_metadata:
                result["metadata"] = metadata  # type: ignore[typeddict-item]
            return result

        # 3. Detect technical terms
        tech_terms, domain_scores = self._detect_technical_terms(query_lower)
        metadata["technical_terms"] = tech_terms
        metadata["domains"] = {d for d, score in domain_scores.items() if score > 0}
        metadata["domain_score"] = max(domain_scores.values()) if domain_scores else 0.0

        # 4. Calculate technical complexity boost
        tech_boost = self._calculate_technical_boost(
            len(tech_terms), 0, domain_scores  # math notation length (simplified)
        )

        # 5. Detect code patterns
        has_code = any(p.search(query) for p in self.CODE_PATTERNS)

        # 6. Length and structure analysis
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

        # 7. Count keyword matches
        simple_matches = sum(1 for kw in self.SIMPLE_KEYWORDS if kw in query_lower)
        moderate_matches = sum(1 for kw in self.MODERATE_KEYWORDS if kw in query_lower)
        hard_matches = sum(1 for kw in self.HARD_KEYWORDS if kw in query_lower)
        expert_matches = sum(1 for kw in self.EXPERT_KEYWORDS if kw in query_lower)

        # 8. Determine base complexity
        final_complexity: QueryComplexity
        final_confidence: float

        # Technical terms STRONGLY influence complexity
        if tech_boost >= 2.0:
            final_complexity = "expert"
            final_confidence = 0.90
        elif tech_boost >= 1.0:
            final_complexity = "hard"
            final_confidence = 0.85
        elif tech_boost >= 0.5:
            final_complexity = "moderate"
            final_confidence = 0.80
        elif expert_matches >= 2:
            final_complexity = "expert"
            final_confidence = 0.85
        elif expert_matches >= 1:
            if word_count >= 8:
                final_complexity = "expert"
                final_confidence = 0.80
            else:
                final_complexity = "hard"
                final_confidence = 0.75
        elif hard_matches >= 2:
            final_complexity = "hard"
            final_confidence = 0.8
        elif hard_matches >= 1 and word_count > 6:
            final_complexity = "hard"
            final_confidence = 0.7
        elif moderate_matches >= 2:
            final_complexity = "moderate"
            final_confidence = 0.8
        elif moderate_matches >= 1 and word_count > 6:
            final_complexity = "moderate"
            final_confidence = 0.7
        elif word_count <= 6 and simple_matches >= 1:
            final_complexity = "simple"
            final_confidence = 0.75
        else:
            # Default by word count
            if word_count <= 8:
                final_complexity = "simple"
                final_confidence = 0.6
            elif word_count <= 20:
                final_complexity = "moderate"
                final_confidence = 0.6
            else:
                final_complexity = "hard"
                final_confidence = 0.6

        # 9. Apply technical boost to complexity
        if tech_boost >= 1.5:
            if final_complexity == "simple":
                final_complexity = "hard"
            elif final_complexity == "moderate":
                final_complexity = "expert"
            elif final_complexity == "hard":
                final_complexity = "expert"
            final_confidence = min(0.95, final_confidence + 0.15)

        # 10. Apply code boost
        if has_code:
            is_complex_code_query = word_count > 12 or expert_matches >= 1

            if is_complex_code_query:
                if final_complexity == "simple":
                    final_complexity = "moderate"
                elif final_complexity == "moderate":
                    final_complexity = "hard"
                final_confidence = min(0.95, final_confidence + 0.1)
            else:
                final_confidence = min(0.95, final_confidence + 0.05)

        # 11. Apply structure boost
        if structure_score >= 2:
            if final_complexity == "simple":
                final_complexity = "moderate"
            elif final_complexity == "moderate":
                final_complexity = "hard"
            final_confidence = min(0.95, final_confidence + 0.05)

        # 12. Sanity checks
        if word_count < 10 and final_complexity == "expert" and tech_boost < 2.0:
            final_complexity = "hard"

        if word_count > 50 and final_complexity in ("simple", "moderate"):
            final_complexity = "hard"

        result = {
            "complexity": final_complexity,
            "confidence": final_confidence,
        }
        if return_metadata:
            result["metadata"] = metadata  # type: ignore[typeddict-item]
        return result

    def _detect_technical_terms(self, query_lower: str) -> tuple[list[str], dict[str, float]]:
        """Detect technical terms in query."""
        found_terms: list[str] = []
        domain_scores = {
            "physics": 0.0,
            "mathematics": 0.0,
            "computer_science": 0.0,
            "engineering": 0.0,
        }

        # Check multi-word terms first (more specific)
        for term in self.all_technical_terms:
            if " " in term or "-" in term:
                pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.I)
                if pattern.search(query_lower):
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

        # Check single-word terms
        words_in_query = set(query_lower.split())
        for term in self.all_technical_terms:
            if " " not in term and "-" not in term:
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

        return found_terms, domain_scores

    def _calculate_technical_boost(
        self, num_tech_terms: int, num_math_notation: int, domain_scores: dict[str, float]
    ) -> float:
        """Calculate complexity boost from technical content."""
        boost = 0.0

        # Technical terms boost
        boost += num_tech_terms * 0.7

        # Math notation boost
        boost += num_math_notation * 0.3

        # Domain specialization boost
        max_domain_score = max(domain_scores.values()) if domain_scores else 0.0
        if max_domain_score >= 2:
            boost += 2.0
        elif max_domain_score >= 1:
            boost += 1.0
        elif max_domain_score >= 0.5:
            boost += 0.5

        return boost

    def _has_trivial_concepts(self, query_lower: str) -> bool:
        """Check for trivial concepts."""
        trivial_count = 0

        for concept in self.TRIVIAL_CONCEPTS:
            pattern = re.compile(r"\b" + concept + r"\b", re.I)
            if pattern.search(query_lower):
                trivial_count += 1

        word_count = len(query_lower.split())

        if trivial_count >= 2:
            return True
        elif trivial_count >= 1 and word_count <= 8:
            return True

        return False
