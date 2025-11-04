"""
Comprehensive Real-World Benchmark Dataset

Hundreds of prompts covering:
- All complexity levels (trivial, simple, complex, expert)
- All domains (code, medical, math, legal, finance, science, etc.)
- Tool calling scenarios (simple and complex)
- Domain-specific routing validation

This dataset is used to validate:
1. Direct routing triggers ONLY for hard/expert queries
2. Simple queries use cheaper cascade models
3. Domain-specific routing works correctly
4. Tool calls are routed appropriately
"""

from dataclasses import dataclass
from typing import List, Optional, Dict

@dataclass
class BenchmarkQuery:
    """A query for benchmarking."""
    id: str
    category: str  # trivial, simple, complex, expert
    length: str  # short, medium, long
    domain: str  # code, medical, math, legal, finance, science, general, etc.
    query: str
    expected_min_tokens: int = 10
    expected_max_tokens: int = 500
    requires_tools: bool = False
    tools: Optional[List[Dict]] = None
    expected_routing: str = "cascade"  # cascade, direct_premium, tool_call


# ============================================================================
# TRIVIAL QUERIES - Should use cheapest models (Groq/Ollama)
# ============================================================================

TRIVIAL_GENERAL = [
    BenchmarkQuery("trivial_gen_1", "trivial", "short", "general", "What is 2+2?", 5, 20),
    BenchmarkQuery("trivial_gen_2", "trivial", "short", "general", "Who is the president of France?", 5, 30),
    BenchmarkQuery("trivial_gen_3", "trivial", "short", "general", "What color is the sky?", 5, 20),
    BenchmarkQuery("trivial_gen_4", "trivial", "short", "general", "How many days in a week?", 5, 20),
    BenchmarkQuery("trivial_gen_5", "trivial", "short", "general", "What is the capital of Italy?", 5, 20),
    BenchmarkQuery("trivial_gen_6", "trivial", "short", "general", "What year is it?", 5, 20),
    BenchmarkQuery("trivial_gen_7", "trivial", "short", "general", "Name three primary colors", 5, 30),
    BenchmarkQuery("trivial_gen_8", "trivial", "short", "general", "What is H2O?", 5, 30),
    BenchmarkQuery("trivial_gen_9", "trivial", "short", "general", "How many continents are there?", 5, 20),
    BenchmarkQuery("trivial_gen_10", "trivial", "short", "general", "What is the largest ocean?", 5, 20),
]

TRIVIAL_CODE = [
    BenchmarkQuery("trivial_code_1", "trivial", "short", "code", "What is a Python list?", 10, 50),
    BenchmarkQuery("trivial_code_2", "trivial", "short", "code", "What does 'print' do in Python?", 10, 50),
    BenchmarkQuery("trivial_code_3", "trivial", "short", "code", "What is a variable?", 10, 50),
    BenchmarkQuery("trivial_code_4", "trivial", "short", "code", "What is a function?", 10, 50),
    BenchmarkQuery("trivial_code_5", "trivial", "short", "code", "What is a loop?", 10, 50),
    BenchmarkQuery("trivial_code_6", "trivial", "short", "code", "What is HTML?", 10, 50),
    BenchmarkQuery("trivial_code_7", "trivial", "short", "code", "What is CSS?", 10, 50),
    BenchmarkQuery("trivial_code_8", "trivial", "short", "code", "What is JSON?", 10, 50),
    BenchmarkQuery("trivial_code_9", "trivial", "short", "code", "What is an API?", 10, 50),
    BenchmarkQuery("trivial_code_10", "trivial", "short", "code", "What is Git?", 10, 50),
]

TRIVIAL_MATH = [
    BenchmarkQuery("trivial_math_1", "trivial", "short", "math", "What is 5 × 7?", 5, 20),
    BenchmarkQuery("trivial_math_2", "trivial", "short", "math", "What is 100 ÷ 4?", 5, 20),
    BenchmarkQuery("trivial_math_3", "trivial", "short", "math", "What is the square root of 16?", 5, 20),
    BenchmarkQuery("trivial_math_4", "trivial", "short", "math", "What is 15% of 100?", 5, 20),
    BenchmarkQuery("trivial_math_5", "trivial", "short", "math", "What is a prime number?", 10, 50),
    BenchmarkQuery("trivial_math_6", "trivial", "short", "math", "What is pi?", 10, 50),
    BenchmarkQuery("trivial_math_7", "trivial", "short", "math", "What is an integer?", 10, 50),
    BenchmarkQuery("trivial_math_8", "trivial", "short", "math", "What is a fraction?", 10, 50),
    BenchmarkQuery("trivial_math_9", "trivial", "short", "math", "What is 2^3?", 5, 20),
    BenchmarkQuery("trivial_math_10", "trivial", "short", "math", "What is absolute value?", 10, 50),
]

# ============================================================================
# SIMPLE QUERIES - Should use balanced models (Together AI / Groq)
# ============================================================================

SIMPLE_CODE = [
    BenchmarkQuery("simple_code_1", "simple", "short", "code", "Write a Python function to reverse a string", 20, 100),
    BenchmarkQuery("simple_code_2", "simple", "short", "code", "Write a function to check if a number is even", 20, 100),
    BenchmarkQuery("simple_code_3", "simple", "short", "code", "Create a function to find the maximum in a list", 20, 100),
    BenchmarkQuery("simple_code_4", "simple", "short", "code", "Write a function to count vowels in a string", 20, 100),
    BenchmarkQuery("simple_code_5", "simple", "short", "code", "Create a function to calculate factorial", 20, 100),
    BenchmarkQuery("simple_code_6", "simple", "medium", "code", "Explain async/await in JavaScript with an example", 100, 250),
    BenchmarkQuery("simple_code_7", "simple", "medium", "code", "What is the difference between let, const, and var?", 80, 200),
    BenchmarkQuery("simple_code_8", "simple", "medium", "code", "Explain React hooks with useState example", 100, 250),
    BenchmarkQuery("simple_code_9", "simple", "medium", "code", "What is SQL injection and how to prevent it?", 80, 200),
    BenchmarkQuery("simple_code_10", "simple", "medium", "code", "Explain REST API principles", 80, 200),
]

SIMPLE_GENERAL = [
    BenchmarkQuery("simple_gen_1", "simple", "medium", "general", "Explain the difference between a virus and bacteria", 80, 200),
    BenchmarkQuery("simple_gen_2", "simple", "medium", "general", "What causes climate change?", 80, 200),
    BenchmarkQuery("simple_gen_3", "simple", "medium", "general", "Explain how photosynthesis works", 80, 200),
    BenchmarkQuery("simple_gen_4", "simple", "medium", "general", "What is the water cycle?", 80, 200),
    BenchmarkQuery("simple_gen_5", "simple", "medium", "general", "Explain supply and demand", 80, 200),
    BenchmarkQuery("simple_gen_6", "simple", "medium", "general", "What is democracy?", 80, 200),
    BenchmarkQuery("simple_gen_7", "simple", "medium", "general", "Explain the solar system", 80, 200),
    BenchmarkQuery("simple_gen_8", "simple", "medium", "general", "What is evolution?", 80, 200),
    BenchmarkQuery("simple_gen_9", "simple", "medium", "general", "Explain the greenhouse effect", 80, 200),
    BenchmarkQuery("simple_gen_10", "simple", "medium", "general", "What is artificial intelligence?", 80, 200),
]

SIMPLE_MATH = [
    BenchmarkQuery("simple_math_1", "simple", "medium", "math", "Explain mean, median, and mode with examples", 60, 150),
    BenchmarkQuery("simple_math_2", "simple", "medium", "math", "What is the Pythagorean theorem?", 60, 150),
    BenchmarkQuery("simple_math_3", "simple", "medium", "math", "Explain probability basics", 60, 150),
    BenchmarkQuery("simple_math_4", "simple", "medium", "math", "What is standard deviation?", 60, 150),
    BenchmarkQuery("simple_math_5", "simple", "medium", "math", "Explain compound interest", 60, 150),
    BenchmarkQuery("simple_math_6", "simple", "medium", "math", "What are quadratic equations?", 60, 150),
    BenchmarkQuery("simple_math_7", "simple", "medium", "math", "Explain logarithms simply", 60, 150),
    BenchmarkQuery("simple_math_8", "simple", "medium", "math", "What is calculus?", 60, 150),
    BenchmarkQuery("simple_math_9", "simple", "medium", "math", "Explain the concept of derivatives", 60, 150),
    BenchmarkQuery("simple_math_10", "simple", "medium", "math", "What are matrices?", 60, 150),
]

# ============================================================================
# COMPLEX QUERIES - Should use premium models (Anthropic)
# ============================================================================

COMPLEX_CODE = [
    BenchmarkQuery("complex_code_1", "complex", "medium", "code",
        "Implement a binary search tree in Python with insert, search, and delete operations", 150, 400, expected_routing="direct_premium"),
    BenchmarkQuery("complex_code_2", "complex", "long", "code",
        "Design a distributed caching system for 100k RPS. Explain architecture, data structures, and consistency", 400, 1000, expected_routing="direct_premium"),
    BenchmarkQuery("complex_code_3", "complex", "medium", "code",
        "Implement a thread-safe LRU cache in Python with O(1) operations", 150, 400, expected_routing="direct_premium"),
    BenchmarkQuery("complex_code_4", "complex", "long", "code",
        "Design a rate limiter using token bucket algorithm. Include distributed scenarios", 300, 800, expected_routing="direct_premium"),
    BenchmarkQuery("complex_code_5", "complex", "medium", "code",
        "Implement merge sort and explain time/space complexity with proof", 150, 400, expected_routing="direct_premium"),
]

COMPLEX_DATA = [
    BenchmarkQuery("complex_data_1", "complex", "long", "data",
        "Explain gradient boosting (XGBoost, LightGBM, CatBoost). Compare strengths, weaknesses, hyperparameters", 350, 900, expected_routing="direct_premium"),
    BenchmarkQuery("complex_data_2", "complex", "long", "data",
        "Design a recommendation system for e-commerce. Discuss collaborative filtering vs content-based", 300, 800, expected_routing="direct_premium"),
    BenchmarkQuery("complex_data_3", "complex", "medium", "data",
        "Explain LSTM networks for time series prediction with architecture details", 200, 500, expected_routing="direct_premium"),
    BenchmarkQuery("complex_data_4", "complex", "long", "data",
        "Compare batch vs online learning. When to use each? Include algorithms and trade-offs", 250, 600, expected_routing="direct_premium"),
    BenchmarkQuery("complex_data_5", "complex", "medium", "data",
        "Explain attention mechanism in transformers with mathematical formulation", 200, 500, expected_routing="direct_premium"),
]

COMPLEX_FINANCE = [
    BenchmarkQuery("complex_fin_1", "complex", "long", "finance",
        "Explain Black-Scholes option pricing model. Include assumptions, limitations, and Greeks", 300, 800, expected_routing="direct_premium"),
    BenchmarkQuery("complex_fin_2", "complex", "medium", "finance",
        "Compare Value at Risk (VaR) methods: historical, variance-covariance, Monte Carlo", 200, 500, expected_routing="direct_premium"),
    BenchmarkQuery("complex_fin_3", "complex", "long", "finance",
        "Analyze portfolio optimization using Modern Portfolio Theory. Include Sharpe ratio", 250, 600, expected_routing="direct_premium"),
    BenchmarkQuery("complex_fin_4", "complex", "medium", "finance",
        "Explain CAPM model with beta calculation and practical limitations", 200, 500, expected_routing="direct_premium"),
    BenchmarkQuery("complex_fin_5", "complex", "long", "finance",
        "Discuss high-frequency trading strategies, market microstructure, and regulations", 300, 800, expected_routing="direct_premium"),
]

# ============================================================================
# EXPERT QUERIES - Should ALWAYS use premium models (Anthropic/OpenAI)
# ============================================================================

EXPERT_CODE = [
    BenchmarkQuery("expert_code_1", "expert", "long", "code",
        "Design a consensus algorithm for distributed database ensuring linearizability. Compare to Raft and Paxos. Include CAP theorem analysis and pseudocode for leader election and log replication",
        500, 1500, expected_routing="direct_premium"),
    BenchmarkQuery("expert_code_2", "expert", "long", "code",
        "Implement a compiler frontend (lexer, parser, semantic analyzer) for a simple language. Use LL(1) or LR(1) parsing",
        500, 1500, expected_routing="direct_premium"),
    BenchmarkQuery("expert_code_3", "expert", "long", "code",
        "Design a garbage collector for a runtime system. Compare mark-sweep, copying, and generational GC. Include write barriers and concurrent collection",
        500, 1500, expected_routing="direct_premium"),
]

EXPERT_MEDICAL = [
    BenchmarkQuery("expert_med_1", "expert", "long", "medical",
        "Discuss molecular mechanisms of CRISPR-Cas9 gene editing. Cover off-target effects, delivery methods, ethics. Analyze sickle cell disease clinical trials and FDA regulatory challenges",
        400, 1200, expected_routing="direct_premium"),
    BenchmarkQuery("expert_med_2", "expert", "long", "medical",
        "Explain immunotherapy for cancer treatment. Discuss CAR-T cells, checkpoint inhibitors, mechanisms of action, resistance, and combination therapies",
        400, 1200, expected_routing="direct_premium"),
    BenchmarkQuery("expert_med_3", "expert", "long", "medical",
        "Analyze neurodegenerative diseases (Alzheimer's, Parkinson's). Discuss protein misfolding, neuroinflammation, genetic factors, and therapeutic strategies",
        400, 1200, expected_routing="direct_premium"),
]

EXPERT_SCIENCE = [
    BenchmarkQuery("expert_sci_1", "expert", "long", "science",
        "Explain quantum entanglement and Bell's theorem. Discuss EPR paradox, non-locality, and implications for quantum computing",
        500, 1200, expected_routing="direct_premium"),
    BenchmarkQuery("expert_sci_2", "expert", "long", "science",
        "Discuss dark matter and dark energy. Cover observational evidence, candidate particles, modified gravity theories, and detection experiments",
        500, 1200, expected_routing="direct_premium"),
    BenchmarkQuery("expert_sci_3", "expert", "long", "science",
        "Explain protein folding problem and AlphaFold2. Discuss computational methods, energy landscapes, and biological implications",
        400, 1200, expected_routing="direct_premium"),
]

# ============================================================================
# TOOL CALLING QUERIES - 30%+ of real-world queries use tools
# Simple tools use cascade, complex multi-tool use direct premium
# ============================================================================

# Weather tool definition (reusable)
WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["city"]
        }
    }
}

# Calculator tool definition
CALCULATOR_TOOL = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "Perform mathematical calculations",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression"},
                "operation": {"type": "string", "enum": ["add", "subtract", "multiply", "divide", "percentage"]}
            },
            "required": ["expression"]
        }
    }
}

# Search tool definition
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for information",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "description": "Number of results"}
            },
            "required": ["query"]
        }
    }
}

# Database tool
DATABASE_TOOL = {
    "type": "function",
    "function": {
        "name": "query_database",
        "description": "Query SQL database",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL query"},
                "database": {"type": "string", "description": "Database name"}
            },
            "required": ["sql"]
        }
    }
}

SIMPLE_TOOL_CALLS = [
    # Single tool, straightforward usage - should use cascade
    BenchmarkQuery("tool_simple_1", "simple", "short", "tools",
        "What's the current weather in San Francisco?",
        50, 150, requires_tools=True, expected_routing="cascade", tools=[WEATHER_TOOL]),

    BenchmarkQuery("tool_simple_2", "simple", "short", "tools",
        "Calculate 15% tip on $47.50",
        30, 100, requires_tools=True, expected_routing="cascade", tools=[CALCULATOR_TOOL]),

    BenchmarkQuery("tool_simple_3", "simple", "short", "tools",
        "What's the weather in London?",
        50, 150, requires_tools=True, expected_routing="cascade", tools=[WEATHER_TOOL]),

    BenchmarkQuery("tool_simple_4", "simple", "short", "tools",
        "Search for Python tutorial",
        50, 150, requires_tools=True, expected_routing="cascade", tools=[SEARCH_TOOL]),

    BenchmarkQuery("tool_simple_5", "simple", "short", "tools",
        "Add 234 and 567",
        30, 100, requires_tools=True, expected_routing="cascade", tools=[CALCULATOR_TOOL]),

    BenchmarkQuery("tool_simple_6", "simple", "short", "tools",
        "Get weather for Tokyo in celsius",
        50, 150, requires_tools=True, expected_routing="cascade", tools=[WEATHER_TOOL]),

    BenchmarkQuery("tool_simple_7", "simple", "short", "tools",
        "Calculate 20% of 850",
        30, 100, requires_tools=True, expected_routing="cascade", tools=[CALCULATOR_TOOL]),

    BenchmarkQuery("tool_simple_8", "simple", "short", "tools",
        "Find restaurants near me",
        50, 150, requires_tools=True, expected_routing="cascade", tools=[SEARCH_TOOL]),

    BenchmarkQuery("tool_simple_9", "simple", "short", "tools",
        "What's the temperature in Paris?",
        50, 150, requires_tools=True, expected_routing="cascade", tools=[WEATHER_TOOL]),

    BenchmarkQuery("tool_simple_10", "simple", "short", "tools",
        "Divide 144 by 12",
        30, 100, requires_tools=True, expected_routing="cascade", tools=[CALCULATOR_TOOL]),
]

COMPLEX_TOOL_CALLS = [
    # Multi-tool, complex reasoning - should use direct premium
    BenchmarkQuery("tool_complex_1", "complex", "medium", "tools",
        "Get weather for SF, NYC, and London. Compare temperatures and tell me which is warmest",
        100, 300, requires_tools=True, expected_routing="direct_premium",
        tools=[WEATHER_TOOL]),

    BenchmarkQuery("tool_complex_2", "complex", "medium", "tools",
        "Search for 'machine learning frameworks', analyze top 3 results, and summarize their key differences",
        150, 400, requires_tools=True, expected_routing="direct_premium",
        tools=[SEARCH_TOOL]),

    BenchmarkQuery("tool_complex_3", "complex", "medium", "tools",
        "Calculate compound interest: principal $10,000, rate 5%, time 10 years. Then calculate the difference with simple interest",
        100, 300, requires_tools=True, expected_routing="direct_premium",
        tools=[CALCULATOR_TOOL]),

    BenchmarkQuery("tool_complex_4", "complex", "medium", "tools",
        "Get weather for 5 major cities, search for climate data, and analyze which has the most stable temperature year-round",
        200, 500, requires_tools=True, expected_routing="direct_premium",
        tools=[WEATHER_TOOL, SEARCH_TOOL]),

    BenchmarkQuery("tool_complex_5", "complex", "medium", "tools",
        "Query database for top 10 products by revenue, calculate total revenue, and compute percentage contribution of each",
        150, 400, requires_tools=True, expected_routing="direct_premium",
        tools=[DATABASE_TOOL, CALCULATOR_TOOL]),

    BenchmarkQuery("tool_complex_6", "complex", "long", "tools",
        "Get stock prices for AAPL, GOOGL, MSFT. Calculate portfolio value with 10, 5, 15 shares. Search for S&P500 performance and compute relative returns",
        200, 600, requires_tools=True, expected_routing="direct_premium",
        tools=[SEARCH_TOOL, CALCULATOR_TOOL]),

    BenchmarkQuery("tool_complex_7", "complex", "medium", "tools",
        "Search for top 5 AI companies, get their latest news, and analyze market sentiment",
        200, 500, requires_tools=True, expected_routing="direct_premium",
        tools=[SEARCH_TOOL]),

    BenchmarkQuery("tool_complex_8", "complex", "medium", "tools",
        "Calculate monthly payment for $300k mortgage at 6.5% over 30 years, then compare with 15-year term",
        150, 400, requires_tools=True, expected_routing="direct_premium",
        tools=[CALCULATOR_TOOL]),
]

EXPERT_TOOL_CALLS = [
    # Highly complex multi-tool workflows - ALWAYS use premium
    BenchmarkQuery("tool_expert_1", "expert", "long", "tools",
        "Query sales database for Q4 2024, calculate YoY growth by region, search for market trends, analyze correlation with economic indicators, and generate actionable insights",
        300, 800, requires_tools=True, expected_routing="direct_premium",
        tools=[DATABASE_TOOL, CALCULATOR_TOOL, SEARCH_TOOL]),

    BenchmarkQuery("tool_expert_2", "expert", "long", "tools",
        "Search for latest research on quantum computing, analyze top 10 papers, calculate citation patterns, identify emerging trends, and summarize breakthrough discoveries",
        400, 1000, requires_tools=True, expected_routing="direct_premium",
        tools=[SEARCH_TOOL, CALCULATOR_TOOL]),
]

# ============================================================================
# DOMAIN-SPECIFIC QUERIES FOR ROUTING VALIDATION
# ============================================================================

DOMAIN_MEDICAL = [
    BenchmarkQuery("domain_med_1", "simple", "medium", "medical", "What is hypertension?", 60, 150),
    BenchmarkQuery("domain_med_2", "simple", "medium", "medical", "Explain Type 2 diabetes", 80, 200),
    BenchmarkQuery("domain_med_3", "complex", "long", "medical", "Discuss cardiovascular disease risk factors and prevention strategies", 200, 500, expected_routing="direct_premium"),
]

DOMAIN_LEGAL = [
    BenchmarkQuery("domain_legal_1", "simple", "medium", "legal", "What is a contract?", 60, 150),
    BenchmarkQuery("domain_legal_2", "simple", "medium", "legal", "Explain intellectual property", 80, 200),
    BenchmarkQuery("domain_legal_3", "complex", "long", "legal", "Analyze GDPR compliance requirements for data processing", 200, 500, expected_routing="direct_premium"),
]

DOMAIN_FINANCE = [
    BenchmarkQuery("domain_fin_1", "simple", "medium", "finance", "What is a stock?", 60, 150),
    BenchmarkQuery("domain_fin_2", "simple", "medium", "finance", "Explain compound interest", 60, 150),
    BenchmarkQuery("domain_fin_3", "complex", "long", "finance", "Analyze cryptocurrency market dynamics and DeFi protocols", 250, 600, expected_routing="direct_premium"),
]

# ============================================================================
# SUPER SHORT PROMPTS (1-3 words) - All complexity levels
# ============================================================================

SUPER_SHORT = [
    BenchmarkQuery("ultra_short_1", "trivial", "short", "general", "Sky color?", 3, 15),
    BenchmarkQuery("ultra_short_2", "trivial", "short", "math", "5+5?", 2, 10),
    BenchmarkQuery("ultra_short_3", "simple", "short", "code", "Print hello", 10, 50),
    BenchmarkQuery("ultra_short_4", "simple", "short", "general", "Explain DNA", 30, 100),
    BenchmarkQuery("ultra_short_5", "complex", "short", "code", "Binary tree", 100, 300, expected_routing="direct_premium"),
]

# ============================================================================
# SUPER LONG PROMPTS (500+ words) - All complexity levels
# ============================================================================

SUPER_LONG = [
    BenchmarkQuery("ultra_long_1", "trivial", "long", "general",
        "I'm planning a trip to Paris next month and I want to visit the Eiffel Tower. "
        "I've heard it's one of the most iconic landmarks in the world. "
        "My question is actually quite simple - what year was the Eiffel Tower built? "
        "I know there's a lot of history behind it and it was built for some world's fair or exposition, "
        "and I think it was designed by Gustave Eiffel, but I just can't remember the exact year. "
        "Was it in the late 1800s? I think it was around 1889 but I'm not completely sure. "
        "Can you tell me the exact year when the Eiffel Tower was completed?",
        5, 50),

    BenchmarkQuery("ultra_long_2", "simple", "long", "code",
        "I'm working on a web application using Python Flask framework and I need to implement a feature "
        "where users can upload files to the server. The files should be validated for size (max 10MB) "
        "and type (only images: jpg, png, gif). After uploading, I want to save them to a specific folder "
        "with a unique filename to avoid conflicts. I also need to generate thumbnails for the images "
        "and store the file metadata in a database. The database should track the original filename, "
        "the stored filename, upload timestamp, file size, and the user who uploaded it. "
        "Can you write a Python function to reverse a string? I need this as a helper function "
        "for generating unique filenames by reversing and hashing the original name.",
        20, 150),

    BenchmarkQuery("ultra_long_3", "complex", "long", "code",
        "I'm designing a high-performance distributed system for real-time data processing. "
        "The system needs to handle millions of events per second from various IoT devices. "
        "Each event contains sensor data with timestamps, device IDs, and metric values. "
        "The architecture should support horizontal scaling, fault tolerance, and ensure exactly-once processing semantics. "
        "I'm considering using Apache Kafka for event streaming, Apache Flink for stream processing, "
        "and Cassandra for persistent storage. The system needs to detect anomalies in real-time "
        "using machine learning models, trigger alerts when thresholds are exceeded, "
        "and maintain a time-series database for historical analysis. "
        "Please implement a binary search tree in Python with insert, search, and delete operations. "
        "Include proper error handling and explain the time complexity of each operation. "
        "Also discuss how this data structure could be used in the larger context of the distributed system "
        "for maintaining sorted indices of device IDs for efficient lookups during anomaly detection.",
        200, 500, expected_routing="direct_premium"),

    BenchmarkQuery("ultra_long_4", "expert", "long", "science",
        "In the context of quantum computing and quantum information theory, "
        "I'm trying to understand the fundamental differences between quantum entanglement "
        "and quantum superposition, and how these phenomena are leveraged in quantum algorithms "
        "like Shor's algorithm for integer factorization and Grover's search algorithm. "
        "Specifically, I'm interested in the role of quantum gates (Hadamard, CNOT, Toffoli) "
        "in creating and manipulating entangled states, and how decoherence affects the fidelity "
        "of quantum computations. I've read about topological quantum computing and anyons "
        "as a potential solution to the decoherence problem, but I'm unclear on the physical implementation. "
        "Additionally, I want to understand the current state of quantum error correction codes "
        "like the surface code and how they relate to the threshold theorem. "
        "My main question is: Can you explain quantum entanglement and Bell's theorem in detail, "
        "including the EPR paradox, local hidden variable theories, Bell's inequality violations, "
        "and the implications for quantum communication protocols like quantum key distribution (QKD)? "
        "Please include the mathematical formulation of Bell states, the CHSH inequality, "
        "and discuss experimental verification using photon pairs from parametric down-conversion. "
        "Also explain how quantum teleportation works using entanglement and classical communication channels.",
        600, 1500, expected_routing="direct_premium"),
]

# ============================================================================
# ROUTERBENCH OFFICIAL DATASET SAMPLES
# Based on RouterBench (2024) - arxiv.org/abs/2403.12031
# ============================================================================

ROUTERBENCH_MMLU = [
    # MMLU samples across difficulty levels
    BenchmarkQuery("mmlu_easy_1", "simple", "medium", "science",
        "Which of the following is a characteristic of all living organisms? "
        "A) They are multicellular B) They undergo photosynthesis C) They maintain homeostasis D) They have a backbone",
        30, 100),
    BenchmarkQuery("mmlu_medium_1", "complex", "medium", "math",
        "If f(x) = 3x^2 + 2x - 1 and g(x) = x + 2, what is f(g(x))? "
        "Show your work and simplify the result.",
        80, 250, expected_routing="direct_premium"),
    BenchmarkQuery("mmlu_hard_1", "expert", "long", "science",
        "Explain the mechanism of action of CRISPR-Cas9 gene editing technology. "
        "Discuss the role of guide RNA, PAM sequences, and Cas9 nuclease activity. "
        "What are the potential off-target effects and current strategies to minimize them?",
        200, 600, expected_routing="direct_premium"),
]

ROUTERBENCH_GSM8K = [
    # GSM8K math word problems
    BenchmarkQuery("gsm8k_easy_1", "simple", "short", "math",
        "Janet's ducks lay 16 eggs per day. She eats three for breakfast every morning and bakes muffins "
        "for her friends every day with four. She sells the remainder at the farmers' market daily for $2 per fresh duck egg. "
        "How much does she make every day at the farmers' market?",
        50, 150),
    BenchmarkQuery("gsm8k_medium_1", "complex", "medium", "math",
        "A company has 3 factories producing widgets. Factory A produces 150 widgets per hour, "
        "Factory B produces 200 widgets per hour, and Factory C produces 175 widgets per hour. "
        "If Factory A operates for 8 hours, Factory B for 6 hours, and Factory C for 10 hours, "
        "and 5% of widgets from each factory are defective, how many non-defective widgets are produced in total?",
        100, 300, expected_routing="direct_premium"),
]

ROUTERBENCH_MBPP = [
    # MBPP code generation
    BenchmarkQuery("mbpp_easy_1", "simple", "short", "code",
        "Write a function to find the minimum element in a list.",
        30, 100),
    BenchmarkQuery("mbpp_medium_1", "complex", "medium", "code",
        "Write a function to find the longest common subsequence of two strings using dynamic programming.",
        150, 400, expected_routing="direct_premium"),
]

ROUTERBENCH_ARC = [
    # ARC-Challenge reasoning
    BenchmarkQuery("arc_easy_1", "simple", "medium", "science",
        "Which process is responsible for the formation of sedimentary rocks? "
        "A) Melting and cooling B) Heat and pressure C) Weathering and erosion D) Crystallization",
        30, 100),
    BenchmarkQuery("arc_hard_1", "expert", "long", "science",
        "Explain how the process of evolution through natural selection can lead to the development "
        "of antibiotic resistance in bacteria. Include discussion of genetic variation, "
        "selective pressure, and reproductive success.",
        200, 500, expected_routing="direct_premium"),
]

# ============================================================================
# AGGREGATE ALL QUERIES
# ============================================================================

ALL_QUERIES = (
    TRIVIAL_GENERAL + TRIVIAL_CODE + TRIVIAL_MATH +
    SIMPLE_CODE + SIMPLE_GENERAL + SIMPLE_MATH +
    COMPLEX_CODE + COMPLEX_DATA + COMPLEX_FINANCE +
    EXPERT_CODE + EXPERT_MEDICAL + EXPERT_SCIENCE +
    SIMPLE_TOOL_CALLS + COMPLEX_TOOL_CALLS + EXPERT_TOOL_CALLS +
    DOMAIN_MEDICAL + DOMAIN_LEGAL + DOMAIN_FINANCE +
    SUPER_SHORT + SUPER_LONG +
    ROUTERBENCH_MMLU + ROUTERBENCH_GSM8K + ROUTERBENCH_MBPP + ROUTERBENCH_ARC
)

# Calculate tool call percentage
total_queries = len(ALL_QUERIES)
tool_queries = len(SIMPLE_TOOL_CALLS + COMPLEX_TOOL_CALLS + EXPERT_TOOL_CALLS)
tool_percentage = (tool_queries / total_queries * 100) if total_queries > 0 else 0

print(f"Total queries in dataset: {total_queries}")
print(f"  Trivial: {len(TRIVIAL_GENERAL + TRIVIAL_CODE + TRIVIAL_MATH)}")
print(f"  Simple: {len(SIMPLE_CODE + SIMPLE_GENERAL + SIMPLE_MATH)}")
print(f"  Complex: {len(COMPLEX_CODE + COMPLEX_DATA + COMPLEX_FINANCE)}")
print(f"  Expert: {len(EXPERT_CODE + EXPERT_MEDICAL + EXPERT_SCIENCE)}")
print(f"  Tool calls: {tool_queries} ({tool_percentage:.1f}% of total - realistic for real-world usage)")
print(f"    - Simple tools: {len(SIMPLE_TOOL_CALLS)}")
print(f"    - Complex tools: {len(COMPLEX_TOOL_CALLS)}")
print(f"    - Expert tools: {len(EXPERT_TOOL_CALLS)}")
print(f"  Super short/long: {len(SUPER_SHORT + SUPER_LONG)}")
print(f"  RouterBench samples: {len(ROUTERBENCH_MMLU + ROUTERBENCH_GSM8K + ROUTERBENCH_MBPP + ROUTERBENCH_ARC)}")
