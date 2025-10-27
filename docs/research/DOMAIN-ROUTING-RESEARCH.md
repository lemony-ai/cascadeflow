# Domain Understanding and Domain-Aware Routing for LLM Systems - Research Report

## Executive Summary

This research compiles practical, lightweight approaches to domain detection and routing for LLM systems. The focus is on production-ready implementations with minimal overhead, avoiding over-engineered academic solutions.

**Key Findings:**
- Hybrid rule-based + ML approaches outperform pure solutions in production
- BERT-based classifiers achieve sub-20ms latency at scale (25K+ requests/sec)
- Semantic routing using embeddings eliminates LLM latency for intent detection
- Domain-specific models often outperform general models by 2-10x cost savings with comparable accuracy
- Uncertainty-based cascading can reduce costs by 60-85% while maintaining 95%+ performance

---

## 1. Domain Detection Techniques

### 1.1 Text Classification for Domain/Intent Detection

#### Modern Approaches (2024-2025)
Production systems predominantly use three strategies:

**1. LLM-based Classification**
- Uses structured output with function calling
- Gives unambiguous responses and educates LLMs about their options
- Best for: Complex, nuanced domain boundaries
- Latency: 200-1000ms depending on model
- Cost: Higher but most flexible

**2. Embedding-based Semantic Routing**
- Encodes queries into semantic vector space
- Matches against pre-defined route embeddings using cosine similarity
- Best for: Well-defined domains with clear semantic boundaries
- Latency: 10-50ms
- Cost: Minimal (only embedding model)

**3. Supervised Classifier (BERT/DistilBERT)**
- Fine-tuned classifier on domain labels
- Highest accuracy for known domains
- Best for: High-volume, fixed domain sets
- Latency: 5-100ms depending on hardware
- Cost: Low after initial training

#### Production Examples

**MoDEM (Mixture of Domain Expert Models):**
- Fine-tunes DeBERTa-v3-large for domain classification
- Domains: Math, Health, Science, Coding, Other
- Routes to specialized models: Palmyra-Med-70B (Health), Qwen2.5-72B-Instruct (Coding)
- Achieves 30% cost reduction, 40% latency reduction vs standalone models

**NVIDIA LLM Router:**
- Rust-based NVIDIA Triton Inference Server
- Uses prompt-task-and-complexity-classifier
- OpenAI API compliant
- Minimal latency addition (~5-10ms)

### 1.2 Zero-Shot Classification Models

#### facebook/bart-large-mnli
- **Size:** 500MB
- **Architecture:** BART pre-trained on MNLI (Natural Language Inference)
- **Accuracy:** 88.19% on general classification tasks
- **Use Case:** No training data available, dynamic domain sets
- **How it works:** Poses sequence as NLI premise, constructs hypothesis from each candidate label

#### DistilBERT Variants

**Lightweight Options:**
- **valhalla/distilbart-mnli-12-3:** Distilled BART, comparable accuracy to full BART
- **DistilBERT-base-uncased:** 127MB (4x smaller than BART)
- **Performance:** 75.92% accuracy (vs 88.19% for BART)
- **Latency:** 50-100ms on CPU, 5-10ms on GPU (optimized)
- **Memory:** <300MB

**Production Optimization:**
- ONNX quantization: <100MB memory, <50ms inference
- TensorRT (GPU): 1.2ms on A100, 2.2ms on T4
- Apache TVM (CPU): 9.5ms for sequence length 128

#### DeBERTa Models
- **Performance:** Significantly outperforms BART-large and DistilBERT
- **Use Case:** When accuracy > speed/cost
- **Production example:** MoDEM uses DeBERTa-v3-large for domain classification

### 1.3 Rule-Based vs ML-Based Domain Detection

#### Decision Framework

| Criterion | Rule-Based | ML-Based | Hybrid (Recommended) |
|-----------|------------|----------|---------------------|
| **Speed** | Instant (<1ms) | 5-100ms | 1-100ms |
| **Accuracy (known patterns)** | High (95-99%) | High (90-98%) | Highest (95-99%) |
| **Accuracy (unknown patterns)** | Low (0-30%) | High (70-95%) | High (80-97%) |
| **Maintenance** | Manual, labor-intensive | Automatic retraining | Manual rules + auto ML |
| **Interpretability** | Complete | Low (black box) | Partial |
| **Cold start** | No data needed | Requires labeled data | Minimal data for ML |
| **Cost** | Minimal | Training + inference | Low |

#### Production Best Practices

**Cascading Approach (Recommended):**
```
1. Rule-based filter (regex/keywords) → Direct routing if match
2. Semantic router (embeddings) → Fast, cheap for known intents
3. LLM fallback → Flexible catch-all for ambiguous cases
```

**Performance:**
- Rule-based handles 40-60% of queries instantly
- Semantic routing covers 30-40% with 10-50ms latency
- LLM fallback for remaining 10-20% with higher latency

**Real-World Implementation:**
- Hybrid system achieves within 2% of pure LLM accuracy
- 50% less latency than pure LLM approach
- Reduces LLM API calls by 80-90%

#### When to Use Each Approach

**Rule-Based (Use When):**
- Domain terms are well-defined and stable
- Compliance/regulatory requirements demand transparency
- Budget is extremely limited
- Latency must be <1ms
- Example: "refund", "cancel order", "track shipment"

**ML-Based (Use When):**
- Patterns are complex or subtle
- Domain boundaries overlap
- Language is natural and varied
- New patterns emerge over time
- Example: Distinguishing "medical advice" vs "health insurance" vs "fitness tips"

**Hybrid (Use When):**
- Production system with SLA requirements
- Need balance of speed and accuracy
- Budget allows for ML but needs cost optimization
- Most production use cases

### 1.4 Keyword Extraction + Domain Mapping

#### Lightweight Algorithms Comparison

| Algorithm | Speed | Accuracy | Unsupervised | Language-Agnostic | Best For |
|-----------|-------|----------|--------------|-------------------|----------|
| **YAKE** | Fast | High | Yes | Yes | Balanced, production-ready |
| **RAKE** | Fastest | Medium | Yes | Yes | High-volume, speed-critical |
| **TextRank** | Medium | Medium-High | Yes | Yes | Graph-based relationships |
| **KeyBERT** | Slow | Highest | Semi | Yes | Accuracy-critical tasks |

#### YAKE (Yet Another Keyword Extractor) - RECOMMENDED

**Characteristics:**
- Lightweight unsupervised method
- No training needed, no external corpora required
- Domain-independent, language-independent
- Significantly outperforms other unsupervised methods

**Performance:**
- Processes 2000 documents in ~2 seconds
- Works on texts of different sizes, languages, domains

**Use Case:**
```python
import yake

kw_extractor = yake.KeywordExtractor(top=10)
keywords = kw_extractor.extract_keywords(text)

# Domain mapping
domain_keywords = {
    "medical": ["diagnosis", "treatment", "symptoms", "patient"],
    "legal": ["contract", "lawsuit", "attorney", "court"],
    "finance": ["investment", "trading", "portfolio", "dividend"],
    "code": ["function", "variable", "algorithm", "debug"]
}

detected_domains = []
for domain, terms in domain_keywords.items():
    if any(kw[0] in terms for kw in keywords):
        detected_domains.append(domain)
```

#### RAKE (Rapid Automatic Keyword Extraction)

**Characteristics:**
- Extremely fast: Processes 2000 documents in 2 seconds
- More computationally efficient than TextRank
- Higher precision, comparable recall to TextRank
- Configurable for specific domains

**Limitations:**
- Accuracy lower than YAKE or KeyBERT
- Best for speed-critical applications

#### Production Recommendations

**For Domain Detection Pipeline:**

1. **High-volume, low-latency:** RAKE + domain keyword dictionary
2. **Balanced performance:** YAKE + domain mapping
3. **Accuracy-critical:** KeyBERT embeddings + semantic similarity

**Integration with ML Routing:**
```
User Query
    ↓
Keyword Extraction (YAKE) → Domain Keywords
    ↓
Quick Domain Match?
    ├─ Yes → Route directly (60% of queries)
    └─ No → Embedding classifier (30% of queries)
           └─ Still ambiguous? → LLM routing (10% of queries)
```

**Benefits:**
- Reduces ML inference calls by 60%
- Provides explainable routing decisions
- Enables real-time logging of domain keywords for monitoring

---

## 2. Domain-Aware Routing Patterns

### 2.1 Production Routing Systems

#### Semantic Layer Approach
- Compares embeddings of semantic representations
- Uses cosine similarity or Manhattan distance
- Performs preselection of models or tools
- **Latency:** 10-50ms including embedding generation
- **Accuracy:** 85-95% for well-defined domains

#### Router Pattern (Dispatcher)
- Lightweight LLM acts as "router" or "dispatcher"
- Analyzes incoming request and determines best specialist
- Forwards request to appropriate expert
- **Implementation:** Small model (e.g., Mistral-7B, GPT-3.5-turbo) as router
- **Cost:** Router calls are 10-100x cheaper than expert models

#### Pattern Matching + LLM Escalation
- Runs lightweight pattern matching (regex, keywords)
- Direct routing on match
- Escalates to LLM for deeper reasoning if no match
- **Performance:** Handles 40-60% of queries with <1ms latency
- **Fallback:** LLM handles remaining 40-60% with semantic understanding

### 2.2 Domain-Specific Model Selection

#### Major Domain Categories with Specialized Models

**1. Code/Programming**
- **Models:** CodeLlama (7B-70B), StarCoder, DeepSeek-Coder
- **Performance:** CodeLlama-70B approaches GPT-4 on code tasks
- **Use Cases:** Code generation, debugging, code review
- **Cost Savings:** 5-10x cheaper than GPT-4 for code tasks
- **Caveat:** Performance degrades on domain-specific code (51.48% drop in CodeBLEU)

**2. Medical/Healthcare**
- **Models:** Med-PaLM 2, BioLlama-7B, Palmyra-Med-70B
- **Performance:** Med-PaLM 2 scores 86.5% on MedQA (vs ~60% for GPT-3.5)
- **Use Cases:** Medical Q&A, clinical decision support, medical literature
- **Requirements:** Extreme accuracy, no hallucinations tolerated

**3. Legal**
- **Models:** Domain-fine-tuned models on legal corpora
- **Challenges:** Single word changes can alter meaning drastically
- **Use Cases:** Contract analysis, case law research, compliance

**4. Finance**
- **Models:** BloombergGPT (50B parameters)
- **Training:** 363 billion tokens of financial data
- **Use Cases:** Market analysis, risk assessment, financial Q&A
- **Performance:** Outperforms general models on financial benchmarks

**5. Translation**
- **Models:** NLLB-200, specialized translation models
- **Use Cases:** High-quality translation for specific language pairs

#### Routing Decision Framework

```python
# Example routing logic
def route_to_model(query, domain_classifier):
    domain, confidence = domain_classifier.predict(query)

    if confidence < 0.6:
        # Multi-domain or unclear - use general model
        return "gpt-4-turbo"

    if domain == "code":
        complexity = estimate_code_complexity(query)
        if complexity > 20:  # High cyclomatic complexity
            return "gpt-4-turbo"
        else:
            return "codellama-70b"

    elif domain == "medical":
        # Medical requires high accuracy - use specialized
        return "med-palm-2"

    elif domain == "finance":
        return "bloomberggpt-50b"

    else:
        # Default to general model
        return "gpt-3.5-turbo"
```

### 2.3 Multi-Domain Handling

#### Challenge: Queries Spanning Multiple Domains

**Example:** "How do I implement a medical diagnosis algorithm in Python?"
- Domains: Code + Medical
- Requires: Programming expertise + medical domain knowledge

#### Strategies

**1. LLM-Based Multi-Selection**
- Use LLM to identify ALL relevant domains
- Route to multiple specialized models
- Synthesize responses
- **Cost:** Higher (multiple model calls)
- **Accuracy:** Best for complex multi-domain queries

**2. Hierarchy-Based Routing**
- Identify primary domain (Code)
- Use general model with domain context
- **Cost:** Moderate (single general model call)
- **Accuracy:** Good for simple multi-domain queries

**3. Domain Priority Scoring**
```python
domains = {
    "medical": 0.7,  # High confidence
    "code": 0.8      # Very high confidence
}

# Route to highest confidence domain
primary_domain = max(domains, key=domains.get)

# If multiple domains > 0.6, use multi-routing
if sum(1 for score in domains.values() if score > 0.6) > 1:
    return "multi_route"  # Call multiple specialists
else:
    return route_to_specialist(primary_domain)
```

**4. Cascading with Domain Context**
- Start with domain-specific model
- If uncertainty high, cascade to general model with domain context
- General model can leverage both domain-specific and broad knowledge

#### Production Examples

**PolyRouter (Multi-LLM Querying)**
- Query multiple LLMs in parallel
- Aggregate responses based on confidence
- Use voting or consensus mechanisms

**Lookahead Routing**
- Predicts potential model outputs' latent representations
- Enables informed routing without full inference
- Better handles multi-domain queries by modeling output space

### 2.4 Fallback Strategies When Domain Unclear

#### Uncertainty Detection Methods

**1. Confidence Thresholds**
```python
domain, confidence = classifier.predict(query)

if confidence < 0.6:
    # Low confidence - unclear domain
    fallback_strategy = "general_model"
elif confidence < 0.8:
    # Medium confidence - use cascade
    fallback_strategy = "start_specific_cascade_to_general"
else:
    # High confidence - direct routing
    fallback_strategy = "route_to_specialist"
```

**2. Semantic Entropy**
- Measures model uncertainty in semantic space
- High entropy = high uncertainty
- Route to stronger model when entropy exceeds threshold

**3. Token Probability Analysis**
- Token probability & entropy more reflective than self-explained confidence
- Low token probability = high uncertainty
- Aggregate metrics: arithmetic average, minimum, perplexity

#### Fallback Patterns

**Pattern 1: Default to General Model**
- Safest approach
- Higher cost but maintains quality
- **When to use:** High-stakes applications (healthcare, finance)

**Pattern 2: Multi-Model Voting**
- Query multiple models
- Use consensus or highest confidence response
- **When to use:** Critical decisions, budget allows

**Pattern 3: Iterative Refinement**
- Start with general model
- If response uncertain, route to specialist with context
- **When to use:** Cost-sensitive applications

**Pattern 4: Human-in-the-Loop**
- Escalate high-uncertainty queries to human
- Log for future training data
- **When to use:** Mission-critical, regulated domains

#### Production Recommendations

**Threshold Calibration:**
- **High confidence (>0.8):** Direct routing to specialist
- **Medium confidence (0.6-0.8):** Cascade from specialist to general
- **Low confidence (<0.6):** Start with general model or multi-route

**Coverage Monitoring:**
- Track "unclear domain" rate
- Should be <10% for well-calibrated system
- If >20%, retrain classifier or expand domain definitions

**Dynamic Thresholds:**
- Adjust based on query volume and cost constraints
- Higher thresholds during peak hours (cost optimization)
- Lower thresholds during off-peak (quality optimization)

---

## 3. Code Complexity Detection

### 3.1 AST-Based Complexity Analysis

#### Abstract Syntax Tree (AST) Metrics

**What AST Provides:**
- Structural representation of code
- Enables complexity analysis without execution
- Supports multiple programming languages

**Key AST-Based Metrics:**
1. **Node Count:** Total AST nodes
2. **Depth:** Maximum nesting level
3. **Branching Factor:** Average children per node
4. **Control Flow:** Decision points count

**Python Implementation:**
```python
import ast

def analyze_ast_complexity(code):
    tree = ast.parse(code)

    metrics = {
        "node_count": sum(1 for _ in ast.walk(tree)),
        "depth": calculate_depth(tree),
        "branches": count_branches(tree),
        "functions": len([n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)])
    }

    return metrics

def calculate_depth(node, current_depth=0):
    if not list(ast.iter_child_nodes(node)):
        return current_depth
    return max(calculate_depth(child, current_depth + 1)
               for child in ast.iter_child_nodes(node))

def count_branches(tree):
    branches = sum(1 for node in ast.walk(tree)
                  if isinstance(node, (ast.If, ast.For, ast.While, ast.Try)))
    return branches
```

### 3.2 Cyclomatic Complexity

#### Definition
- Number of linearly independent paths through code
- Formula: `CC = E - N + 2P`
  - E = edges in control flow graph
  - N = nodes
  - P = connected components
- Simplified: `CC = decision_points + 1`

#### Threshold Guidelines

| Complexity | Range | Risk Level | Recommendation |
|------------|-------|------------|----------------|
| Simple | 1-10 | Low | Small model (GPT-3.5, Codex) |
| Moderate | 11-20 | Medium | Medium model (GPT-4-mini) |
| Complex | 21-50 | High | Large model (GPT-4, Claude) |
| Very Complex | 50+ | Very High | Human review + large model |

#### Production Standards

**General Guidelines:**
- **McCabe's Original:** CC ≤ 10
- **Permissive (experienced teams):** CC ≤ 15
- **Warning Threshold:** CC = 10-15
- **Critical Threshold:** CC > 20
- **Model-Based Code:** CC ≤ 30 (higher than manual code due to graphical modeling advantages)

### 3.3 When Does Complexity Justify Cascading?

#### Decision Framework

**Cascade to Larger Model When:**

1. **Cyclomatic Complexity > 15**
   - Multiple nested control structures
   - Complex business logic
   - High maintenance risk

2. **Code Length > 200 lines**
   - Requires maintaining context
   - Multiple functions/classes interacting
   - Larger models have longer context windows

3. **Domain-Specific Code with CC > 10**
   - Specialized APIs or frameworks
   - Requires deep domain knowledge
   - Example: Kubernetes operators, GraphQL resolvers

4. **Error-Prone Code Patterns**
   - Concurrency/async code
   - Memory management (C/C++)
   - Security-critical code (auth, crypto)

5. **Test Coverage < 80% and CC > 10**
   - Indicates complex, under-tested code
   - Higher risk of bugs
   - Larger model better at edge case handling

#### Cost-Benefit Analysis

```python
def should_cascade_to_larger_model(code_metrics, task_type):
    cc = code_metrics['cyclomatic_complexity']
    lines = code_metrics['lines_of_code']
    test_coverage = code_metrics['test_coverage']

    # Simple heuristic
    complexity_score = (
        (cc / 10) * 0.4 +           # Weight CC heavily
        (lines / 200) * 0.2 +        # Consider code length
        (1 - test_coverage) * 0.2 +  # Low coverage = higher complexity
        (is_domain_specific(task_type)) * 0.2  # Domain specificity
    )

    if complexity_score > 0.7:
        return "gpt-4-turbo"  # Large model
    elif complexity_score > 0.4:
        return "gpt-4-mini"   # Medium model
    else:
        return "gpt-3.5-turbo"  # Small model
```

#### Real-World Thresholds

**Based on Research & Production Systems:**

- **Cost-Effective Threshold:** CC = 15
  - Below: 95% of queries handled by small model
  - Above: Cascade to large model
  - Cost savings: 60-70%

- **Quality-Focused Threshold:** CC = 10
  - More conservative
  - Better code quality
  - Cost savings: 40-50%

- **Balanced Threshold:** CC = 12
  - Middle ground
  - Cost savings: 50-60%
  - Quality maintained at 95%+

### 3.4 Production Tools

#### Radon (Python)

**Features:**
- Cyclomatic Complexity (McCabe)
- Raw metrics (LOC, comments, blanks)
- Halstead metrics
- Maintainability Index

**Installation:**
```bash
pip install radon
```

**Usage:**
```bash
# Cyclomatic complexity
radon cc mycode.py -a

# Maintainability Index
radon mi mycode.py

# Raw metrics
radon raw mycode.py
```

**Integration:**
```python
from radon.complexity import cc_visit
from radon.metrics import mi_visit

def get_code_complexity(code):
    # Cyclomatic Complexity
    cc_results = cc_visit(code)
    avg_cc = sum(r.complexity for r in cc_results) / len(cc_results) if cc_results else 0
    max_cc = max((r.complexity for r in cc_results), default=0)

    # Maintainability Index
    mi_score = mi_visit(code, multi=True)

    return {
        "avg_cyclomatic_complexity": avg_cc,
        "max_cyclomatic_complexity": max_cc,
        "maintainability_index": mi_score
    }
```

**Used In:**
- Codacy (code quality platform)
- CodeFactor (automated code review)
- Code Climate (engineering intelligence platform)

#### Lizard (Multi-Language)

**Features:**
- Supports 15+ languages (C/C++, Java, Python, JavaScript, Go, etc.)
- Cyclomatic Complexity (CCN)
- Cognitive Complexity (rare in tools)
- Token count
- Parameter count
- Lines of code
- Duplicate code detection (code clones)

**Installation:**
```bash
pip install lizard
```

**Usage:**
```bash
# Analyze directory
lizard ./src

# With thresholds
lizard -C 15 -W ./src  # Warn if CC > 15

# Export to CSV
lizard -o report.csv ./src
```

**Advantages:**
- No header files needed (C/C++)
- No import resolution (Java)
- Fast processing
- Cognitive complexity (better metric than CC for readability)

#### SonarQube

**Features:**
- Comprehensive code quality platform
- Multi-language support
- Cyclomatic Complexity
- Cognitive Complexity (proprietary metric)
- Security vulnerabilities
- Code smells
- Technical debt calculation

**Cognitive Complexity (SonarQube):**
- Better than CC for measuring understandability
- Penalizes nested structures more heavily
- Ignores shorthand structures that don't affect readability

**Thresholds:**
- CC: Similar to standard (10-15 warning, 20+ critical)
- Cognitive: 15 warning, 25 critical

**Integration:**
```python
# Using SonarQube API
import requests

def get_sonar_metrics(project_key):
    url = f"http://sonarqube/api/measures/component"
    params = {
        "component": project_key,
        "metricKeys": "complexity,cognitive_complexity"
    }
    response = requests.get(url, params=params)
    return response.json()
```

#### Comparison Matrix

| Tool | Languages | CC | Cognitive | Free | Speed | Best For |
|------|-----------|----|-----------| -----|-------|----------|
| **Radon** | Python | ✓ | ✗ | ✓ | Fast | Python projects, CI/CD |
| **Lizard** | 15+ | ✓ | ✓ | ✓ | Very Fast | Multi-language, quick scans |
| **SonarQube** | 25+ | ✓ | ✓ | Partial | Medium | Enterprise, comprehensive analysis |

#### Production Integration Example

```python
import subprocess
import json

def analyze_code_for_routing(file_path):
    # Use Lizard for fast analysis
    result = subprocess.run(
        ['lizard', '-l', 'python', '--json', file_path],
        capture_output=True,
        text=True
    )

    data = json.loads(result.stdout)

    max_cc = max(func['cyclomatic_complexity']
                 for func in data['function_list'])
    avg_cc = sum(func['cyclomatic_complexity']
                 for func in data['function_list']) / len(data['function_list'])

    # Routing decision
    if max_cc > 20 or avg_cc > 15:
        return "gpt-4-turbo"  # Complex code
    elif max_cc > 10 or avg_cc > 8:
        return "gpt-4-mini"
    else:
        return "gpt-3.5-turbo"
```

---

## 4. Cascading Pipelines Research

### 4.1 LangChain Routing

#### LCEL (LangChain Expression Language) Patterns

**Core Routing Approaches:**

1. **Custom Functions with RunnableLambda (Recommended)**
2. **RunnableBranch (Legacy)**

#### Implementation Example

```python
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.schema.runnable import RunnableLambda

# Define specialized chains
coding_chain = PromptTemplate.from_template(
    "You are an expert programmer. {question}"
) | ChatOpenAI(model="gpt-3.5-turbo")

medical_chain = PromptTemplate.from_template(
    "You are a medical expert. {question}"
) | ChatOpenAI(model="gpt-4-turbo")

general_chain = PromptTemplate.from_template(
    "{question}"
) | ChatOpenAI(model="gpt-3.5-turbo")

# Domain classifier
classifier = PromptTemplate.from_template(
    "Classify this query into: coding, medical, or general. Query: {question}"
) | ChatOpenAI(model="gpt-3.5-turbo")

# Router function
def route(info):
    topic = info["topic"].lower()
    if "coding" in topic or "code" in topic:
        return coding_chain
    elif "medical" in topic or "health" in topic:
        return medical_chain
    else:
        return general_chain

# Full chain with routing
full_chain = {
    "topic": classifier,
    "question": lambda x: x["question"]
} | RunnableLambda(route)

# Execute
result = full_chain.invoke({"question": "How do I sort a list in Python?"})
```

#### Semantic Similarity Routing

```python
from langchain.embeddings import OpenAIEmbeddings
from sklearn.metrics.pairwise import cosine_similarity

embeddings = OpenAIEmbeddings()

prompt_templates = {
    "coding": "You are an expert programmer. Help with: {query}",
    "medical": "You are a medical professional. Answer: {query}",
    "finance": "You are a financial advisor. Advise on: {query}"
}

# Pre-compute embeddings
prompt_embeddings = embeddings.embed_documents(list(prompt_templates.keys()))

def prompt_router(input_query):
    query_embedding = embeddings.embed_query(input_query)
    similarities = cosine_similarity([query_embedding], prompt_embeddings)[0]
    most_similar_idx = similarities.argmax()
    domain = list(prompt_templates.keys())[most_similar_idx]
    return PromptTemplate.from_template(prompt_templates[domain])

# Use in chain
routed_chain = RunnableLambda(prompt_router) | ChatOpenAI()
```

#### Best Practices

- **Prefer custom functions** over RunnableBranch for new implementations
- Use semantic similarity routing for flexible, intent-based dispatch
- Leverage LCEL's composable syntax for clean chain construction
- Structure routing logic around domain-specific categorization
- **Non-deterministic chains:** Output of previous step defines next step

### 4.2 Semantic Router Library

**GitHub:** https://github.com/aurelio-labs/semantic-router

#### Core Concept

- Lightweight decision-making without LLM latency
- Uses semantic vector space for routing decisions
- Eliminates need for slow LLM generations

#### How It Works

**1. Define Routes with Utterances:**
```python
from semantic_router import Route

routes = [
    Route(
        name="politics",
        utterances=[
            "isn't politics the best thing ever",
            "why don't you tell me about your political opinions",
            "what's your view on the election"
        ]
    ),
    Route(
        name="chitchat",
        utterances=[
            "how's the weather today",
            "what's your favorite color",
            "do you like pizza"
        ]
    ),
    Route(
        name="coding",
        utterances=[
            "how do I write a function in Python",
            "debug my code",
            "what's a for loop"
        ]
    )
]
```

**2. Initialize Router:**
```python
from semantic_router.routers import SemanticRouter
from semantic_router.encoders import OpenAIEncoder

encoder = OpenAIEncoder()
router = SemanticRouter(encoder=encoder, routes=routes)

# Route query
result = router("don't you love politics?")
print(result)  # Output: 'politics'
```

#### Key Features

- **Multi-modal support:** Text, images, mixed modalities
- **Multiple encoders:** OpenAI, Cohere, HuggingFace, FastEmbed
- **Vector databases:** Pinecone, Qdrant integration
- **Fully local:** HuggingFaceEncoder + LlamaCppLLM
- **Dynamic routes:** Parameter generation, function calling

#### Performance

- **Latency:** 10-50ms (vs 200-1000ms for LLM routing)
- **Local models:** Mistral-7B outperforms GPT-3.5 in most tests
- **Production example:** 10ms latency achieved with ollama/gemma2

#### Production Use Cases

- Intent classification without LLM latency
- Chatbot conversation flow management
- Tool-use decision-making for agents
- 5G network orchestration (IEEE GlobeCom 2024)

#### Integration Example

```python
from semantic_router import SemanticRouter
from semantic_router.encoders import HuggingFaceEncoder

# Lightweight local encoder
encoder = HuggingFaceEncoder(name="sentence-transformers/all-MiniLM-L6-v2")

router = SemanticRouter(encoder=encoder, routes=routes)

def route_query(query):
    route_name = router(query)

    if route_name == "coding":
        return call_codellama(query)
    elif route_name == "medical":
        return call_medpalm(query)
    else:
        return call_gpt35(query)
```

### 4.3 LlamaIndex Query Routing

**Docs:** https://docs.llamaindex.ai/en/stable/module_guides/querying/router/

#### Core Concept

Routers take user query + set of "choices" (defined by metadata) and return one or more selected choices.

#### Router Types

**Selector Implementations:**
- **LLM Selectors:** Use text completion with choices as text
- **Pydantic Selectors:** Pass choices as Pydantic schemas to function-calling APIs

**Selection Strategies:**
- **Single:** `PydanticSingleSelector`, `LLMSingleSelector`
- **Multi:** `PydanticMultiSelector`, `LLMMultiSelector`

#### Use Cases

1. **Data Source Selection:** Choose among diverse data sources
2. **Retrieval Method Selection:** Summarization vs semantic search
3. **Multi-routing:** Combine results from multiple routes
4. **Retrieval-augmented routing:** Beta feature

#### Implementation Patterns

**Query Engine Routing:**
```python
from llama_index.core.query_engine import RouterQueryEngine
from llama_index.core.tools import QueryEngineTool

# Define query engines
sql_tool = QueryEngineTool.from_defaults(
    query_engine=sql_query_engine,
    description="Useful for structured data queries"
)

vector_tool = QueryEngineTool.from_defaults(
    query_engine=vector_query_engine,
    description="Useful for semantic search"
)

# Create router
router = RouterQueryEngine.from_defaults(
    tools=[sql_tool, vector_tool],
    select_multi=False
)

# Query
response = router.query("What is the revenue for Q3?")
```

**Retriever Routing:**
```python
from llama_index.core.retrievers import RouterRetriever
from llama_index.core.tools import RetrieverTool

# Multiple retrieval strategies
tools = [
    RetrieverTool.from_defaults(
        retriever=keyword_retriever,
        description="Use for keyword matching"
    ),
    RetrieverTool.from_defaults(
        retriever=semantic_retriever,
        description="Use for semantic similarity"
    )
]

router_retriever = RouterRetriever.from_defaults(tools=tools)
nodes = router_retriever.retrieve("What are the best practices?")
```

#### Query Pipelines

**LlamaIndex Query Pipeline:**
- Declarative API for orchestrating workflows
- DAG (Directed Acyclic Graph) structure
- Composable modules: LLMs, prompts, query engines, retrievers

```python
from llama_index.core.query_pipeline import QueryPipeline

# Build pipeline
pipeline = QueryPipeline()
pipeline.add_modules({
    "rewriter": query_rewriter,
    "retriever": retriever,
    "reranker": reranker,
    "synthesizer": response_synthesizer
})

# Connect stages
pipeline.add_link("rewriter", "retriever")
pipeline.add_link("retriever", "reranker")
pipeline.add_link("reranker", "synthesizer")

# Execute
response = pipeline.run(query="What is the capital of France?")
```

### 4.4 DSPy Program Optimization

**GitHub:** https://github.com/stanfordnlp/dspy

#### Core Concept

DSPy treats prompts as code - optimizes entire program rather than individual prompts.

#### Key Optimizers

**1. MIPROv2**
- Generates instructions and few-shot examples
- Data-aware and demonstration-aware generation
- Uses Bayesian Optimization
- Searches over instruction/demonstration space across modules

**2. GEPA (Gradient-based)**
- Uses LMs to reflect on program trajectory
- Identifies what worked and what didn't
- Leverages domain-specific textual feedback
- Rapid improvement iteration

#### Domain Routing with DSPy

**Routing Agent Example:**
```python
import dspy

class DomainRouter(dspy.Module):
    def __init__(self):
        super().__init__()
        self.classify = dspy.ChainOfThought("query -> domain, confidence")

    def forward(self, query):
        result = self.classify(query=query)
        return result.domain, float(result.confidence)

# Optimize router
optimizer = dspy.MIPROv2()
optimized_router = optimizer.compile(
    DomainRouter(),
    trainset=training_data,
    max_bootstrapped_demos=4,
    max_labeled_demos=16
)
```

#### Joint Optimization for Routing

**Key Insight:** DSPy doesn't just optimize individual modules - it optimizes how routing decisions set up downstream modules for success.

**Process:**
1. Traces entire program execution
2. Identifies all learnable parameters (routing logic, response generation, context flow)
3. Searches for improvements maximizing behavioral consistency
4. Learns how routing decisions preserve context for downstream tasks

**Benefits:**
- Routing decisions optimized for end-to-end performance
- Not just accuracy of routing, but impact on final output
- Context flow maintained across cascade

#### Production Use Case: Multi-Agent Routing

```python
class RoutingAgent(dspy.Module):
    def __init__(self, agents):
        super().__init__()
        self.agents = agents
        self.router = dspy.ChainOfThought("query, context -> agent_name")

    def forward(self, query, context):
        # Router selects agent
        selection = self.router(query=query, context=context)
        agent_name = selection.agent_name

        # Execute selected agent
        selected_agent = self.agents[agent_name]
        return selected_agent(query, context)

# Optimize entire routing + execution
optimizer = dspy.BootstrapFewShotWithRandomSearch(
    metric=end_to_end_quality_metric,
    max_bootstrapped_demos=8
)

optimized_system = optimizer.compile(
    RoutingAgent(agents),
    trainset=training_data
)
```

#### Key Advantages

- **Holistic optimization:** Routes + execution optimized together
- **Data-driven:** Learns from examples, not hand-crafted prompts
- **Adaptable:** Retrain when new domains added
- **Transparent:** Code-based, not prompt-based

#### Production Recommendations

- Use DSPy when you have training data
- Optimize for end-to-end metrics (not just routing accuracy)
- Re-optimize when adding new domains or models
- Monitor performance and re-compile periodically

---

## 5. Domain-Specific Models Landscape

### 5.1 Models by Domain

#### Code/Programming

**Major Models:**

| Model | Size | Performance | Use Case | Cost vs GPT-4 |
|-------|------|-------------|----------|---------------|
| CodeLlama | 7B-70B | HumanEval: 53% (70B) | General coding | 5-10x cheaper |
| StarCoder | 15B | HumanEval: 40% | Open source code | 8x cheaper |
| DeepSeek-Coder | 1B-33B | Outperforms StarCoder | Specialized coding | 10x cheaper |
| GPT-4 | ~1.7T | HumanEval: 67% | General + code | Baseline |

**Performance Notes:**
- CodeLlama-70B approaches GPT-4 on code benchmarks
- Domain-specific code: Performance drops 51.48% (CodeBLEU) for general models
- StarCoder: Beats PaLM, LaMDA, LLaMA despite smaller size

**When to Use:**
- ✅ General code generation, completion
- ✅ Common frameworks (React, Django, Express)
- ✅ Standard algorithms and data structures
- ❌ Domain-specific APIs without docs
- ❌ Novel/emerging frameworks
- ❌ Complex system design (use GPT-4)

#### Medical/Healthcare

**Major Models:**

| Model | Size | Performance | Use Case | Cost |
|-------|------|-------------|----------|------|
| Med-PaLM 2 | Unknown | MedQA: 86.5% | Medical Q&A | High |
| BioLlama | 7B | Biomedical text | Research literature | Low |
| Palmyra-Med | 70B | Clinical tasks | Healthcare apps | Medium |
| GPT-4 | ~1.7T | MedQA: ~67% | General medical | Very High |

**Performance Notes:**
- Med-PaLM 2: 86.5% on MedQA (vs ~60% for GPT-3.5)
- Specialized terminology and context essential
- Zero tolerance for hallucinations

**When to Use:**
- ✅ Medical Q&A (patient-facing)
- ✅ Clinical decision support
- ✅ Medical literature analysis
- ✅ Symptoms → possible conditions
- ❌ Final diagnosis (human required)
- ❌ Treatment plans (human required)

**Critical Requirements:**
- Extreme accuracy (lives at stake)
- Explainability and citations
- Regulatory compliance (HIPAA, FDA)
- Human oversight mandatory

#### Legal

**Major Models:**
- Domain-fine-tuned models on legal corpora
- No dominant open-source model yet
- Most use GPT-4 with legal RAG systems

**Challenges:**
- Single word changes alter meaning drastically
- Ambiguities, synonyms, context-specific interpretations
- Requires understanding precedents and statutes

**When to Use Domain Models:**
- ✅ Contract analysis (routine clauses)
- ✅ Legal research (case law search)
- ✅ Compliance checking
- ❌ Novel legal arguments (GPT-4 better)
- ❌ Cross-jurisdiction issues
- ❌ Final legal advice (human required)

#### Finance

**Major Models:**

| Model | Size | Training Data | Performance | Use Case |
|-------|------|---------------|-------------|----------|
| BloombergGPT | 50B | 363B tokens financial | Beats general models on FinBen | Financial analysis |
| GPT-4 | ~1.7T | General | Good general, poor on finance-specific | General + finance |

**Performance Notes:**
- BloombergGPT outperforms general models on financial benchmarks
- 363 billion tokens of financial data
- Excels at: market analysis, risk assessment, financial Q&A
- Struggles: Forecasting, complex reasoning (latest GPT-4 still better)

**When to Use:**
- ✅ Financial Q&A
- ✅ Market sentiment analysis
- ✅ Risk assessment
- ✅ Earnings call summarization
- ❌ Investment decisions (human required)
- ❌ Regulatory compliance (domain + legal)

#### Translation

**Major Models:**
- NLLB-200 (Meta): 200 languages
- Specialized translation models for specific pairs
- GPT-4: Good for common languages, less for rare

**When to Use Domain Models:**
- ✅ High-volume translation (cost savings)
- ✅ Rare language pairs
- ✅ Domain-specific translation (medical, legal)
- ❌ Creative translation (GPT-4 better)
- ❌ Context-heavy translation

### 5.2 Performance vs General Models

#### Benchmark Comparisons (2024)

**Domain-Specific Advantages:**
- 2-10x cost savings
- Better accuracy on in-domain tasks
- Lower latency (smaller models)
- Can run locally (data privacy)

**General Model Advantages:**
- Handles edge cases better
- Multi-domain queries
- Better reasoning on novel problems
- More up-to-date knowledge

#### Real-World Performance Data

**Finance (FinBen Benchmark):**
- BloombergGPT: Outperforms GPT-3.5 by 15-25% on financial tasks
- GPT-4: Matches or slightly exceeds BloombergGPT on most tasks
- Cost: BloombergGPT 5x cheaper

**Medical (MedQA Benchmark):**
- Med-PaLM 2: 86.5%
- GPT-4: ~67%
- GPT-3.5: ~60%
- Improvement: 20-26% better

**Code (HumanEval Benchmark):**
- GPT-4: 67%
- CodeLlama-70B: 53%
- CodeLlama-34B: 48%
- GPT-3.5: 48%
- Cost: CodeLlama 5-10x cheaper

**Legal (LegalBench):**
- No clear winner - domain models and GPT-4 trade wins
- GPT-4 better on reasoning tasks
- Domain models better on precedent search

### 5.3 When to Use Domain-Specific vs General Cascade

#### Decision Framework

**Use Domain-Specific Model When:**

1. **Clear Domain Boundaries**
   - Query clearly belongs to one domain
   - Domain-specific terminology present
   - Examples: "debug this Python code", "explain this ECG"

2. **High Volume, Cost-Sensitive**
   - Many queries per day (>1000)
   - Cost reduction critical
   - Acceptable accuracy tradeoff (2-5%)

3. **Privacy/Compliance Requirements**
   - Must run on-premises
   - Data cannot leave infrastructure
   - Regulatory requirements (HIPAA, GDPR)

4. **Low Latency Requirements**
   - Real-time applications
   - Interactive systems
   - User-facing chatbots

5. **Specialized Knowledge Depth**
   - Domain jargon and nuance critical
   - General model lacks domain expertise
   - Example: Medical diagnosis, legal precedents

**Use General Model (GPT-4) When:**

1. **Multi-Domain or Unclear Domain**
   - Query spans multiple domains
   - Domain ambiguous or hybrid
   - Example: "How do I implement HIPAA-compliant authentication in Django?"

2. **Novel or Complex Reasoning**
   - Requires creative problem-solving
   - Novel scenarios not in training data
   - Complex system design

3. **High Stakes, Zero Error Tolerance**
   - Cost of error > cost of inference
   - Mission-critical applications
   - When $0.1 error cost > model cost difference

4. **Low Volume, Diverse Queries**
   - <100 queries per day
   - Highly varied query types
   - Not worth maintaining multiple models

5. **Latest Knowledge Required**
   - Recent events or developments
   - Cutting-edge topics
   - General models updated more frequently

**Use Cascade (Domain → General) When:**

1. **Balanced Cost-Quality Tradeoff**
   - 60-85% cost savings possible
   - Maintains 95%+ quality
   - Production sweet spot

2. **Uncertainty Detection Available**
   - Can measure confidence/uncertainty
   - Cascade on low confidence
   - Example: Token entropy, semantic entropy

3. **Moderate Volume (100-10000/day)**
   - Enough to justify complexity
   - Not so high that latency critical

4. **Acceptable Latency Budget**
   - Can afford 2-step inference for some queries
   - Typically adds 500-2000ms for cascaded queries

#### Cost-Benefit Matrix

| Scenario | Queries/Day | Domain Clarity | Strategy | Cost Savings | Quality |
|----------|-------------|----------------|----------|--------------|---------|
| Chatbot (single domain) | 10K+ | High | Domain-specific | 80-90% | 95%+ |
| Enterprise assistant | 1K-10K | Medium | Cascade | 60-70% | 97%+ |
| Research tool | 100-1K | Low | General | 0% | 100% |
| Code autocomplete | 100K+ | High | Domain-specific | 85%+ | 90%+ |
| Medical diagnosis | 1K-10K | High | Domain-specific + human | 70%+ | 99%+ |
| Legal research | 100-1K | High | Hybrid (Domain + GPT-4) | 50% | 98%+ |

#### Production Implementation Example

```python
class DomainAwareRouter:
    def __init__(self):
        self.domain_models = {
            "code": "codellama-70b",
            "medical": "med-palm-2",
            "finance": "bloomberggpt-50b"
        }
        self.general_model = "gpt-4-turbo"
        self.cheap_model = "gpt-3.5-turbo"

    def route(self, query):
        # 1. Detect domain
        domain, confidence = self.detect_domain(query)

        # 2. Determine if multi-domain
        if self.is_multi_domain(query):
            return self.general_model

        # 3. Route based on confidence
        if confidence < 0.6:
            # Unclear - use general
            return self.general_model

        # 4. Check if domain model available
        if domain in self.domain_models:
            # Check complexity
            if self.is_complex(query, domain):
                # Start with domain, cascade to general if needed
                return self.cascade_route(domain, query)
            else:
                # Direct to domain model
                return self.domain_models[domain]

        # 5. Default to cheap general model
        return self.cheap_model

    def cascade_route(self, domain, query):
        # Try domain model first
        response, uncertainty = self.query_with_uncertainty(
            self.domain_models[domain],
            query
        )

        # If high uncertainty, cascade to general
        if uncertainty > 0.7:
            return self.general_model

        return response
```

---

## 6. Production Architecture Patterns

### 6.1 Lightweight Routing Stack

**Recommended Stack for Production:**

```
Layer 1: Rule-Based Filter (40-60% of queries, <1ms)
    ↓ (no match)
Layer 2: Semantic Router (30-40% of queries, 10-50ms)
    ↓ (ambiguous)
Layer 3: LLM Classifier (10-20% of queries, 200-500ms)
    ↓
Layer 4: Model Selection + Execution
    ↓
Layer 5: Uncertainty Detection + Cascade (if needed)
```

**Implementation:**

```python
class ProductionRouter:
    def __init__(self):
        # Layer 1: Rules
        self.rules = {
            r'\b(refund|cancel|return)\b': 'customer_service',
            r'\b(def|function|import|class)\b': 'code',
            r'\b(symptoms?|diagnosis|treatment)\b': 'medical'
        }

        # Layer 2: Semantic Router
        self.semantic_router = SemanticRouter(
            encoder=FastEmbedEncoder(),  # 5ms latency
            routes=predefined_routes
        )

        # Layer 3: LLM Classifier (fallback)
        self.llm_classifier = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0
        )

        # Layer 4: Model registry
        self.models = {
            'code': 'codellama-70b',
            'medical': 'med-palm-2',
            'general': 'gpt-4-turbo'
        }

    async def route(self, query):
        # Layer 1: Rule-based (fastest)
        for pattern, domain in self.rules.items():
            if re.search(pattern, query, re.I):
                return self.models.get(domain, self.models['general'])

        # Layer 2: Semantic router
        route = self.semantic_router(query)
        if route and route.confidence > 0.7:
            return self.models.get(route.name, self.models['general'])

        # Layer 3: LLM classifier (slowest, most accurate)
        domain = await self.llm_classify(query)
        return self.models.get(domain, self.models['general'])

    async def query_with_cascade(self, query):
        model = await self.route(query)

        # Execute
        response, uncertainty = await self.execute_with_uncertainty(model, query)

        # Cascade if uncertain
        if uncertainty > 0.7 and model != self.models['general']:
            response = await self.execute(self.models['general'], query)

        return response
```

### 6.2 Performance Benchmarks

**Latency by Layer:**
- Layer 1 (Rules): 0.1-1ms
- Layer 2 (Semantic): 10-50ms
- Layer 3 (LLM): 200-500ms
- Layer 4 (Execution): 500-5000ms
- Layer 5 (Cascade): +500-5000ms

**Accuracy by Layer:**
- Layer 1: 98-99% (for matched patterns)
- Layer 2: 85-95% (for clear domains)
- Layer 3: 90-98% (LLM classification)
- Overall: 95-98% (combined)

**Cost Savings:**
- No routing: $100/day (all GPT-4)
- Simple routing: $40/day (60% savings)
- Cascading: $20/day (80% savings)
- Full stack: $15/day (85% savings)

### 6.3 Monitoring and Metrics

**Key Metrics to Track:**

1. **Routing Metrics:**
   - Domain distribution
   - Confidence score distribution
   - "Unclear domain" rate (<10% target)
   - Rule match rate
   - Semantic router hit rate

2. **Performance Metrics:**
   - Latency per layer
   - End-to-end latency
   - P50, P95, P99 latencies
   - Cascade rate (target: 10-20%)

3. **Quality Metrics:**
   - Routing accuracy (manual eval)
   - User satisfaction scores
   - Error rate by domain
   - Hallucination rate

4. **Cost Metrics:**
   - Cost per query
   - Cost by domain
   - Cost savings vs baseline
   - Model utilization

**Example Monitoring:**

```python
from prometheus_client import Counter, Histogram, Gauge

# Routing metrics
routing_counter = Counter(
    'llm_routing_total',
    'Total routing decisions',
    ['layer', 'domain', 'model']
)

routing_confidence = Histogram(
    'llm_routing_confidence',
    'Confidence scores',
    ['layer', 'domain']
)

# Performance metrics
routing_latency = Histogram(
    'llm_routing_latency_seconds',
    'Routing latency',
    ['layer']
)

cascade_rate = Gauge(
    'llm_cascade_rate',
    'Percentage of queries cascaded'
)

# Cost metrics
cost_per_query = Histogram(
    'llm_cost_per_query_dollars',
    'Cost per query',
    ['domain', 'model']
)
```

### 6.4 Common Pitfalls and Solutions

**Pitfall 1: Over-Routing**
- **Problem:** Too many routing layers, adds latency
- **Solution:** Measure and optimize - remove layers with <5% impact

**Pitfall 2: Stale Domain Definitions**
- **Problem:** New query types not handled
- **Solution:** Monitor "unclear domain" rate, retrain regularly

**Pitfall 3: Ignoring Uncertainty**
- **Problem:** Wrong model confident in wrong answer
- **Solution:** Always measure and use uncertainty, cascade on high uncertainty

**Pitfall 4: Cost Without Quality**
- **Problem:** Over-optimizing for cost, sacrificing quality
- **Solution:** Set quality floor (e.g., 95% of GPT-4 performance), optimize cost above that

**Pitfall 5: No Human Feedback Loop**
- **Problem:** No way to improve routing over time
- **Solution:** Log all routing decisions, sample for manual review, retrain

---

## 7. Key Takeaways and Recommendations

### 7.1 For Domain Detection

**Lightweight & Production-Ready:**

1. **Start with Hybrid Approach:**
   - Rules (40-60% coverage, instant)
   - Semantic router (30-40% coverage, 10-50ms)
   - LLM fallback (10-20% coverage, 200-500ms)

2. **Best Models:**
   - Zero-shot: `valhalla/distilbart-mnli-12-3` (127MB, 50ms)
   - Fine-tuned: DeBERTa-v3-large or DistilBERT
   - Embeddings: `all-MiniLM-L6-v2` (384-dim, <10ms)

3. **Keyword Extraction:**
   - YAKE for balanced performance
   - RAKE for speed-critical
   - Integrate with rule-based layer

### 7.2 For Domain Routing

**Production Patterns:**

1. **Use Domain-Specific Models When:**
   - Clear domain (>80% confidence)
   - High volume (>1000 queries/day)
   - Low-medium complexity

2. **Use General Models When:**
   - Multi-domain or unclear
   - Novel reasoning required
   - High stakes (cost of error > inference cost)

3. **Use Cascading When:**
   - Moderate volume (100-10K/day)
   - 60-85% cost savings needed
   - Uncertainty detection available

### 7.3 For Code Complexity

**Thresholds:**
- CC ≤ 10: Small model (GPT-3.5, Codex)
- CC 11-20: Medium model (GPT-4-mini)
- CC > 20: Large model (GPT-4)

**Tools:**
- Python: Radon
- Multi-language: Lizard
- Enterprise: SonarQube (Cognitive Complexity)

### 7.4 For Cascading Pipelines

**Recommended Frameworks:**

1. **Semantic Router:** Fastest (10-50ms), best for clear domains
2. **LangChain LCEL:** Most flexible, good ecosystem
3. **LlamaIndex:** Best for RAG + routing
4. **DSPy:** Best for optimizing end-to-end performance

### 7.5 Cost-Quality Tradeoffs

**Sweet Spots:**
- Domain-specific: 80-90% cost savings, 95%+ quality
- Cascading: 60-85% cost savings, 95-98% quality
- Hybrid routing: 70-85% cost savings, 96-99% quality

**When NOT to Optimize Cost:**
- High-stakes applications (medical, legal, finance)
- Cost of error > $0.1
- Mission-critical decisions
- Low volume (<100/day)

---

## 8. Implementation Checklist

### Phase 1: Foundation (Week 1-2)
- [ ] Implement rule-based routing for obvious cases
- [ ] Set up domain keyword dictionaries
- [ ] Deploy lightweight embedding model (all-MiniLM-L6-v2)
- [ ] Implement basic logging and metrics

### Phase 2: Semantic Routing (Week 2-3)
- [ ] Define domains and example utterances
- [ ] Set up Semantic Router
- [ ] Calibrate confidence thresholds
- [ ] Add latency and accuracy monitoring

### Phase 3: Model Integration (Week 3-4)
- [ ] Integrate domain-specific models
- [ ] Set up model registry
- [ ] Implement fallback to general model
- [ ] Add cost tracking

### Phase 4: Cascading (Week 4-5)
- [ ] Implement uncertainty detection
- [ ] Set up cascade logic
- [ ] Calibrate cascade thresholds
- [ ] Monitor cascade rate

### Phase 5: Optimization (Week 5-6)
- [ ] Analyze routing decisions
- [ ] Identify misrouted queries
- [ ] Retrain classifiers
- [ ] Optimize thresholds

### Phase 6: Production Hardening (Week 6+)
- [ ] Load testing
- [ ] A/B testing routing strategies
- [ ] Set up alerting
- [ ] Human feedback loop
- [ ] Regular retraining schedule

---

## 9. References and Resources

### Key GitHub Repositories

1. **RouteLLM** - https://github.com/lm-sys/RouteLLM
   - Framework for LLM routing with trained routers
   - 85% cost reduction, 95% GPT-4 performance

2. **Semantic Router** - https://github.com/aurelio-labs/semantic-router
   - Fast decision-making without LLM latency
   - 10-50ms routing latency

3. **NVIDIA LLM Router** - https://github.com/NVIDIA-AI-Blueprints/llm-router
   - Production-ready Triton Inference Server
   - Minimal latency addition

4. **Anyscale LLM Router** - https://github.com/anyscale/llm-router
   - Tutorial for building routers
   - 70% cost reduction examples

5. **BentoML LLM Router** - https://github.com/bentoml/llm-router
   - Multi-LLM routing with HTTP server

### Research Papers

1. **"Doing More with Less" (2025)**
   - Comprehensive survey of routing strategies
   - https://arxiv.org/html/2502.00409v1

2. **"RouteLLM" (2024)**
   - Learning to route with preference data
   - https://arxiv.org/html/2406.18665v1

3. **"MoDEM" (2024)**
   - Mixture of Domain Expert Models
   - https://arxiv.org/html/2410.07490v1

4. **"Uncertainty-Based Routing" (2025)**
   - On-device LLM routing with uncertainty
   - https://arxiv.org/html/2502.04428v1

### Production Tools

1. **Radon** - https://radon.readthedocs.io/
   - Python code complexity metrics

2. **Lizard** - https://github.com/terryyin/lizard
   - Multi-language complexity analyzer

3. **LangChain** - https://python.langchain.com/docs/how_to/routing/
   - Routing with LCEL

4. **LlamaIndex** - https://docs.llamaindex.ai/
   - Query routing and pipelines

5. **DSPy** - https://github.com/stanfordnlp/dspy
   - Program optimization for LLMs

### Benchmarks

1. **FinBen** - Financial domain benchmark
2. **MedQA** - Medical question answering
3. **LegalBench** - Legal reasoning
4. **HumanEval** - Code generation
5. **MMLU** - Multi-domain knowledge

---

## 10. Future Directions

### Emerging Trends (2025)

1. **Mixture-of-Experts (MoE) for Routing**
   - Built-in routing in model architecture
   - LLM-based routing in MoE frameworks
   - Self-specialized experts

2. **Lookahead Routing**
   - Predicts output representations before inference
   - Better multi-domain handling
   - Response-aware routing

3. **Adaptive Thresholds**
   - Dynamic threshold adjustment based on load
   - Context-aware routing
   - Cost-aware routing

4. **Federated Domain Models**
   - Multiple specialized models working together
   - Cross-domain synthesis
   - Distributed routing

5. **Neurosymbolic Routing**
   - Combining symbolic rules with neural routing
   - Explainable routing decisions
   - Guaranteed safety properties

### Areas for Further Research

1. **Better Uncertainty Quantification**
   - Calibrated confidence scores
   - Domain-specific uncertainty metrics
   - Multi-metric uncertainty analysis

2. **Few-Shot Domain Adaptation**
   - Quick adaptation to new domains
   - Minimal training data required
   - Transfer learning for routing

3. **Cost-Aware Optimization**
   - Joint optimization of cost and quality
   - Multi-objective routing
   - Budget-constrained routing

4. **Explainable Routing**
   - Why was this model chosen?
   - Routing decision visualization
   - Debugging misrouted queries

---

**Report Compiled:** 2025-10-27
**Focus:** Practical, lightweight, production-ready approaches
**Bias:** Avoiding over-engineered academic solutions

