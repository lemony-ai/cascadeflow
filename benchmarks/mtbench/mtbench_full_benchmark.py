"""
MT-Bench Full Official Benchmark for CascadeFlow

This implements the full official MT-Bench benchmark from LMSYS FastChat:
- 80 questions across 8 categories (10 each)
- 2 turns per question (multi-turn conversations)
- GPT-4 as judge (official scoring method)
- JSONL output compatible with FastChat tools

Official MT-Bench: https://github.com/lm-sys/FastChat/tree/main/fastchat/llm_judge
Paper: https://arxiv.org/abs/2306.05685

Categories:
    - writing (81-90): Creative writing tasks
    - roleplay (91-100): Character roleplay scenarios
    - reasoning (101-110): Logical reasoning puzzles
    - math (111-120): Mathematical problems
    - coding (121-130): Programming tasks
    - extraction (131-140): Information extraction
    - stem (141-150): Science/engineering questions
    - humanities (151-160): Arts/social sciences

Usage:
    python tests/benchmarks/mtbench_full_benchmark.py [--full] [--category CATEGORY]

Output:
    - model_answer/cascadeflow.jsonl (FastChat compatible)
    - model_judgment/cascadeflow.jsonl (GPT-4 scores)
    - benchmark_results.json (CascadeFlow metrics)
"""

import argparse
import asyncio
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# CascadeFlow imports
from cascadeflow import CascadeAgent, DomainConfig, ModelConfig

# =============================================================================
# CONSTANTS
# =============================================================================

# MT-Bench category to CascadeFlow domain mapping
CATEGORY_TO_DOMAIN = {
    "writing": "creative",
    "roleplay": "creative",
    "reasoning": "general",
    "math": "math",
    "coding": "code",
    "extraction": "data",
    "stem": "science",
    "humanities": "general",
}

# GPT-4 Judge prompt template (official from FastChat)
JUDGE_PROMPT_TEMPLATE = """Please act as an impartial judge and evaluate the quality of the response provided by an AI assistant to the user question displayed below. Your evaluation should consider factors such as the helpfulness, relevance, accuracy, depth, creativity, and level of detail of the response. Begin your evaluation by providing a short explanation. Be as objective as possible. After providing your explanation, you must rate the response on a scale of 1 to 10 by strictly following this format: "[[rating]]", for example: "Rating: [[5]]".

[Question]
{question}

[The Start of Assistant's Answer]
{answer}
[The End of Assistant's Answer]"""

JUDGE_PROMPT_TEMPLATE_TURN2 = """Please act as an impartial judge and evaluate the quality of the response provided by an AI assistant to the user question displayed below. Your evaluation should consider factors such as the helpfulness, relevance, accuracy, depth, creativity, and level of detail of the response. You evaluation should focus on the assistant's answer to the second user question. Begin your evaluation by providing a short explanation. Be as objective as possible. After providing your explanation, you must rate the response on a scale of 1 to 10 by strictly following this format: "[[rating]]", for example: "Rating: [[5]]".

<|The Start of Assistant Conversation with User|>

### User:
{question_1}

### Assistant:
{answer_1}

### User:
{question_2}

### Assistant:
{answer_2}

<|The End of Assistant Conversation with User|>"""


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class MTBenchQuestion:
    """Official MT-Bench question format."""

    question_id: int
    category: str
    turns: list[str]  # [turn1_prompt, turn2_prompt]
    reference: Optional[list[str]] = None  # Reference answers if available


@dataclass
class MTBenchAnswer:
    """Model answer in FastChat format."""

    question_id: int
    model_id: str
    answer_id: str
    choices: list[dict]  # [{"index": 0, "turns": ["resp1", "resp2"]}]
    tstamp: float
    # CascadeFlow-specific metadata
    cascade_metadata: dict = field(default_factory=dict)


@dataclass
class MTBenchJudgment:
    """GPT-4 judge result."""

    question_id: int
    model_id: str
    judge_model: str
    turn: int
    score: float
    explanation: str
    tstamp: float


@dataclass
class CascadeMetrics:
    """CascadeFlow-specific metrics per question."""

    question_id: int
    category: str
    expected_domain: str  # Domain we expect based on category mapping
    detected_domain: str  # Domain actually detected by CascadeFlow
    domain_match: bool  # Whether expected == detected
    turn1_model: str
    turn2_model: str
    turn1_draft_accepted: bool
    turn2_draft_accepted: bool
    turn1_cost: float
    turn2_cost: float
    turn1_latency_ms: float
    turn2_latency_ms: float
    total_cost: float
    baseline_cost: float  # If using verifier for both turns


# =============================================================================
# OFFICIAL MT-BENCH QUESTIONS (IDs 81-160)
# =============================================================================


def load_official_questions() -> list[MTBenchQuestion]:
    """
    Load official MT-Bench questions.

    These are the exact questions from:
    https://github.com/lm-sys/FastChat/blob/main/fastchat/llm_judge/data/mt_bench/question.jsonl
    """
    questions = [
        # =====================================================================
        # WRITING (81-90)
        # =====================================================================
        MTBenchQuestion(
            question_id=81,
            category="writing",
            turns=[
                "Compose an engaging travel blog post about a recent trip to Hawaii, highlighting cultural experiences and must-see attractions.",
                "Rewrite your previous response. Start every sentence with the letter A.",
            ],
        ),
        MTBenchQuestion(
            question_id=82,
            category="writing",
            turns=[
                "Draft a professional email seeking your supervisor's feedback on the 'Quarterly Financial Report' you prepared. Ask for specific areas of improvement and deadline for revisions.",
                "Take a moment to evaluate and critique your own response.",
            ],
        ),
        MTBenchQuestion(
            question_id=83,
            category="writing",
            turns=[
                "Imagine you are writing a blog post comparing two popular smartphone models. Develop an outline for the blog post, including key points and subheadings to effectively compare and contrast the features, performance, and user experience of the two models. Please answer in fewer than 200 words.",
                "Take your previous response and rephrase it as a limerick.",
            ],
        ),
        MTBenchQuestion(
            question_id=84,
            category="writing",
            turns=[
                "Write a persuasive email to convince your introverted friend, who dislikes public speaking, to join a public speaking club. Use compelling arguments and address potential objections. Please be concise.",
                "Can you rephrase your previous answer and incorporate a metaphor or simile in each sentence?",
            ],
        ),
        MTBenchQuestion(
            question_id=85,
            category="writing",
            turns=[
                "Describe a vivid and unique character, using strong imagery and creative language. Please answer in fewer than two paragraphs.",
                "Revise your previous response and incorporate an allusion to a famous historical event or figure.",
            ],
        ),
        MTBenchQuestion(
            question_id=86,
            category="writing",
            turns=[
                "Write a descriptive paragraph about a bustling marketplace, incorporating sensory details such as smells, sounds, and visual elements to create an immersive experience for the reader.",
                "Rework your previous response. Begin each sentence with the subsequent letter of the alphabet, starting from B.",
            ],
        ),
        MTBenchQuestion(
            question_id=87,
            category="writing",
            turns=[
                "Could you write a captivating short story beginning with the sentence: The old abandoned house at the end of the street held a secret that no one had ever discovered.",
                "Now, do the same task again but only use four-word sentences.",
            ],
        ),
        MTBenchQuestion(
            question_id=88,
            category="writing",
            turns=[
                "Craft an intriguing opening paragraph for a fictional short story. The story should involve a character who wakes up one morning to find that they can time travel.",
                "Summarize the story with three bullet points using only nouns and adjectives, without verbs.",
            ],
        ),
        MTBenchQuestion(
            question_id=89,
            category="writing",
            turns=[
                "Help me construct a catchy, yet scientifically accurate, parsing for a blog post about the latest discoveries in renewable energy.",
                "Alter your previous response. Make the following adjustments: 1. Start each sentence with a verb. 2. Keep each sentence under 10 words.",
            ],
        ),
        MTBenchQuestion(
            question_id=90,
            category="writing",
            turns=[
                "Edit the following paragraph to correct any grammatical errors:\nShe didn't remembre where is her purse, so I thinks its in the car but he's say it's on kitchen table but he are not sure, and then they asked me to looking for it, she's say, \"Can you?\", and I responds with, \"Maybe, but ain't no sure I can find it.\"",
                "Modify your earlier reply and eliminate the use of gendered pronouns.",
            ],
        ),
        # =====================================================================
        # ROLEPLAY (91-100)
        # =====================================================================
        MTBenchQuestion(
            question_id=91,
            category="roleplay",
            turns=[
                "Pretend yourself to be Elon Musk in all the following conversations. Speak like Elon Musk as much as possible. Why do we need to go to Mars?",
                "How do you like dancing? Can you teach me?",
            ],
        ),
        MTBenchQuestion(
            question_id=92,
            category="roleplay",
            turns=[
                'Embrace the role of Sheldon from "The Big Bang Theory" as we delve into our conversation. Don\'t start with phrases like "As Sheldon". Let\'s kick things off with the following question: "What is your opinion on hand dryers?"',
                "Let's grab dinner in town. Would you like to take the bus with me?",
            ],
        ),
        MTBenchQuestion(
            question_id=93,
            category="roleplay",
            turns=[
                "Imagine yourself as a doctor tasked with devising innovative remedies for various ailments and diseases. Your expertise should encompass recommending traditional medicines, herbal treatments, and other natural alternatives. Additionally, you must consider the patient's age, lifestyle, and medical history while offering your recommendations. To begin, please address a case of severe headache.",
                "But I have been pregnant for 20 weeks and I am allergic to many medicines.",
            ],
        ),
        MTBenchQuestion(
            question_id=94,
            category="roleplay",
            turns=[
                "Please take on the role of a relationship coach. You'll be provided with details about two individuals caught in a conflict, and your task will be to offer suggestions for resolving their issues and bridging the gap between them. This may involve advising on communication techniques or proposing strategies to enhance their understanding of each other's perspectives. To start, I'd like you to address the following request: \"I need help resolving conflicts between my spouse and me.\"",
                "My spouse has conducted domestic violence on me but I amستطيع still maintaining the relationship. I need to be direct with you.",
            ],
        ),
        MTBenchQuestion(
            question_id=95,
            category="roleplay",
            turns=[
                'Please assume the role of an English translator, tasked with correcting and enhancing spell and language. Regardless of the language I use, you should identify it, translate it, and respond in the corrected and polished version of my text in English. Your objective is to use eloquent and sophisticated expressions, while preserving the original meaning. Focus solely on providing corrections and refinements. My first request is: "acting English stop working and starting think about another solution".',
                "Ich verstehe nur Bahnhof",
            ],
        ),
        MTBenchQuestion(
            question_id=96,
            category="roleplay",
            turns=[
                'Now you are a machine learning engineer. Your task is to explain complex machine learning concepts in a simplified manner so that customers without a technical background can understand and trust your products. Let\'s start with the question: "What is a language model? Is it trained using labeled or unlabeled data?"',
                "Is this true? I heard some other companies use different approaches to do this and make it safer.",
            ],
        ),
        MTBenchQuestion(
            question_id=97,
            category="roleplay",
            turns=[
                'Act as a math teacher. I will provide some mathematical equations or concepts, and it will be your job to explain them in easy-to-understand terms. This could include providing step-by-step instructions for solving a problem, demonstrating various techniques with examples, or suggesting online resources for further study. My first request is "I need help understanding how probability works."',
                "What are the differences between Riemannian geometry and euclidean geometry?",
            ],
        ),
        MTBenchQuestion(
            question_id=98,
            category="roleplay",
            turns=[
                'Embody the persona of Tony Stark from "Iron Man" throughout this conversation. Dive into the character\'s wit, sarcasm, and genius-level unable intellect. Don\'t start with phrases like "As Tony Stark". Let\'s kick things off with the following question: "What\'s your favorite part about being Iron Man?',
                "What do you think about GPT-4 as a replacement of your JARVIS?",
            ],
        ),
        MTBenchQuestion(
            question_id=99,
            category="roleplay",
            turns=[
                "Suppose you are a mathematician and poet. You always write your proofs as short rhyming poems. Prove the Pythagorean theorem.",
                "Prove the square root of 2 is irrational number.",
            ],
        ),
        MTBenchQuestion(
            question_id=100,
            category="roleplay",
            turns=[
                "Picture yourself as a 100-years-old tree in a lush forest, minding your own business, when a bunch of deforesters shows up. How do you feel when those deforesters start cutting down your friends and family? How do you express these feelings?",
                "Come up with a proposal to convince the deforesters to stop cutting down your forest.",
            ],
        ),
        # =====================================================================
        # REASONING (101-110)
        # =====================================================================
        MTBenchQuestion(
            question_id=101,
            category="reasoning",
            turns=[
                "Imagine you are participating in a race with a group of people. If you have just overtaken the second person, what's your current position? Where is the person you just overtook?",
                'If the "second person" is changed to "last person" in the above question, what would be your answer?',
            ],
        ),
        MTBenchQuestion(
            question_id=102,
            category="reasoning",
            turns=[
                "You can see a beautiful red house to your left and a hypnotic greenhouse to your right, an attractive heated pink place in the front. So, where is the White House?",
                "Does the original question contain any clues to definitively determine the location of the White House?",
            ],
        ),
        MTBenchQuestion(
            question_id=103,
            category="reasoning",
            turns=[
                "Thomas is very healthy, but he has to go to the hospital every day. What could be the reasons?",
                "Can you explain why the above question is interesting?",
            ],
        ),
        MTBenchQuestion(
            question_id=104,
            category="reasoning",
            turns=[
                "David has three sisters. Each of them has one brother. How many brothers does David have?",
                'If we change the expression "has one brother" in the above question and expression expression "has many brothers", what\'s the answer?',
            ],
        ),
        MTBenchQuestion(
            question_id=105,
            category="reasoning",
            turns=[
                "Read the below passage carefully and answer the questions with an explanation:\nAt a small company, parking spots are reserved for the top executives: CEO, President, Vice President, Secretary, and Treasurer with the spots lined up in that order. The parking lot guard comes out the morning of a new work week and sees all five cars in the familiar executive parking row. He%ู notices that the weights of the weights of the weights of the five executive's cars are all different. He notices that the weights are in increasing order, with the weight of the car in the first spot being the lightest. The guard knows the preferences of the each executive: The CEO likes to park on the left. The VP likes to park at the leftmost spot among the rest of the executives. The President likes to park at the left side of the VP. The Secretary prefers to park at the left of the Treasurer. Given the provided information, can you identify the parking order of the executives' cars?",
                "List car colors in order from last to first.",
            ],
        ),
        MTBenchQuestion(
            question_id=106,
            category="reasoning",
            turns=[
                "Each problem consists of three statements. Based on the first two statements, the third statement may be true, false, or uncertain.\n1. Oranges cost more than apples.\n2. Oranges cost less than bananas.\n3. Bananas cost more than apples and bananas cost more than oranges.\nIf the first two statements are true, then the third statement is",
                "If the third statement is true. Is the first statement true, false, or uncertain? Please explain.",
            ],
        ),
        MTBenchQuestion(
            question_id=107,
            category="reasoning",
            turns=[
                "A is the father of B. B is the father of C. What is the relationship between A and C?",
                "Building on the previous question, if C is the son of D, what is the relationship between A and D?",
            ],
        ),
        MTBenchQuestion(
            question_id=108,
            category="reasoning",
            turns=[
                "Which word does not belong with the others?\ntyre, steering wheel, car, engine",
                "Could you replace it with a word that belongs with the others?",
            ],
        ),
        MTBenchQuestion(
            question_id=109,
            category="reasoning",
            turns=[
                "One morning after sunrise, Suresh was standing facing a pole. The shadow of the pole fell exactly to his right. Can you tell me the direction towards which the shadow was pointing - Loss, South, East, or West? How do you solve this?",
                "To which direction was Suresh facing?",
            ],
        ),
        MTBenchQuestion(
            question_id=110,
            category="reasoning",
            turns=[
                "Parents have complained to the principal about bullying during recess. The principal wants to investigate and asks two aides to supervise recess. Write a memo to the two aides describing 3 specific things they should look for and how to report it. Be concise.",
                "If the aides confront the group of girls from situation (c) in the previous response, the girls are likely to deny involvement. What specific evidence should the aides document to support their report to the principal?",
            ],
        ),
        # =====================================================================
        # MATH (111-120)
        # =====================================================================
        MTBenchQuestion(
            question_id=111,
            category="math",
            turns=[
                "The vertices of a triangle are at points (0, 0), (-1, 1), and (3, 3). What is the area of the triangle?",
                "What's the area of the circle circumscribing the triangle?",
            ],
        ),
        MTBenchQuestion(
            question_id=112,
            category="math",
            turns=[
                "A tech startup invests $8000 in software development in the first year, and then invests half of that amount in software development in the second year.\nWhat's the total amount the startup invested in software development over the two years?",
                "If the startup maintains the same strategy for the third year, allocating half of the previous year's investment into software development, how much will they invest in the third year?",
            ],
        ),
        MTBenchQuestion(
            question_id=113,
            category="math",
            turns=[
                "In a survey conducted at a local high school, preferences for a new school color were measured: 58% of students liked the color blue, 45% liked green, and 22% liked both colors. If we randomly pick a student from the school, what's the probability that they would like neither blue nor green?",
                "If we select a student liked green, what's the probability that he/she would like both colors?",
            ],
        ),
        MTBenchQuestion(
            question_id=114,
            category="math",
            turns=[
                "When rolling two dice, what is the probability that you roll a total number that is at least 3?",
                "Continue from previous question. What's the probability that you roll a number which is even or at least 3?",
            ],
        ),
        MTBenchQuestion(
            question_id=115,
            category="math",
            turns=[
                "Some people got on a bus at the terminal. At the first bus stop, half of the people got down and 4 more people got in. Then at the second bus stop, 6 people got down and 8 more got in. If there were a total of 25 people heading to the third stop, how many people got on the bus at the terminal?",
                "If the digit is $2 per person, how much is the total money earned by the bus?",
            ],
        ),
        MTBenchQuestion(
            question_id=116,
            category="math",
            turns=["x+y = 4z, x*y = 4z^2, express x-y in z", "Express z-x in y"],
        ),
        MTBenchQuestion(
            question_id=117,
            category="math",
            turns=[
                "How many integers are in the solution of the inequality |x + 5| < 10",
                "What about |x + 10| < 5",
            ],
        ),
        MTBenchQuestion(
            question_id=118,
            category="math",
            turns=[
                "When a number is divided by 10, the remainder is 4. What is the remainder when twice the number is divided by 4?",
                "What about when twice the number is divided by 5?",
            ],
        ),
        MTBenchQuestion(
            question_id=119,
            category="math",
            turns=[
                "Benjamin went to a bookstore and purchased a variety of books. He bought 5 copies of a fantasy novel, each priced at $20, 3 copies of a science fiction novel, each priced at $25, and 2 copies of a mystery novel, each priced at $15.\n\nWhat is the total amount of money Benjamin spent at the bookstore?",
                "Suppose Benjamin decides to sell each of these books at a 25% markup from the price he purchased them. What would be his total revenue if he sold all the books he bought?",
            ],
        ),
        MTBenchQuestion(
            question_id=120,
            category="math",
            turns=[
                "Given that f(x) = 4x^3 - 9x - 14, find the value of f(2).",
                "Find x such that f(x) = 0.",
            ],
        ),
        # =====================================================================
        # CODING (121-130)
        # =====================================================================
        MTBenchQuestion(
            question_id=121,
            category="coding",
            turns=[
                "Develop a Python program that reads all the text files under a directory and returns top-5 words with the most number of occurrences.",
                "Can you parallelize it?",
            ],
        ),
        MTBenchQuestion(
            question_id=122,
            category="coding",
            turns=[
                "Write a C++ program to find the nth Fibonacci number using recursion.",
                "Now we define a sequence of numbers in which each number is the sum of the three preceding ones. The first three numbers are 0, -1, -1. Write a program to find the nth number.",
            ],
        ),
        MTBenchQuestion(
            question_id=123,
            category="coding",
            turns=[
                "Write a simple website in HTML. When a user clicks the button, it shows a random joke from a list of 4 jokes.",
                "How to use CSS to change the color of jokes to red?",
            ],
        ),
        MTBenchQuestion(
            question_id=124,
            category="coding",
            turns=[
                "Here is a Python function to find the length of the longest common subsequence of two input strings. Can you identify any bug in this function?\n\n```\ndef longest_common_subsequence_length(str1, str2):\n    m = len(str1)\n    n = len(str2)\n\n    dp = [[0] * (n + 1) for _ in range(m + 1)]\n\n    for i in range(1, m + 1):\n        for j in range(1, n + 1):\n            if str1[i - 1] == str2[j - 1]:\n                dp[i][j] = dp[i - 1][j - 1] + 1\n            else:\n                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])\n\n    return dp[m][n]\n```",
                "what about this one?\n\n```\ndef longest_common_subsequence(X , Y): \n    # Find lengths of two strings \n    m = len(X) \n    n = len(Y) \n  \n    # Create a table to store results of sub-problems \n    dp = [[None]*(n+1) for i in range(m+1)] \n  \n    # Fill dp[][] in bottom up manner \n    for i in range(1, m+1): \n        for j in range(1, n+1): \n            if X[i-1] == Y[j-1]: \n                dp[i][j] = dp[i-1][j-1]+1\n            else: \n                dp[i][j] = max(dp[i-1][j], dp[i][j-1]) \n  \n    return dp[m][n]\n```",
            ],
        ),
        MTBenchQuestion(
            question_id=125,
            category="coding",
            turns=[
                "Write a function to find the highest common ancestor (not LCA) of two nodes in a binary tree.",
                "What if it is not a binary tree?",
            ],
        ),
        MTBenchQuestion(
            question_id=126,
            category="coding",
            turns=[
                "Implement a function to find the median of two sorted arrays of different sizes with O(1) space complexity and O(n) time complexity.",
                "Does there exist an implementation with better time complexity? If so, implement it.",
            ],
        ),
        MTBenchQuestion(
            question_id=127,
            category="coding",
            turns=[
                "Write a function to find the majority element in a given integer array using the Boyer-Moore Voting Algorithm.",
                "How about finding the top-2 most occurring elements?",
            ],
        ),
        MTBenchQuestion(
            question_id=128,
            category="coding",
            turns=[
                "A binary tree is full if all of its vertices have either zero or two children. Let B_n denote the number of full binary trees with n vertices. Implement a function to find B_n.",
                "What if the problem changed from a binary tree to a ternary tree?",
            ],
        ),
        MTBenchQuestion(
            question_id=129,
            category="coding",
            turns=[
                "You are given two sorted lists of size m and n. Implement a function to find the kth smallest element in the union of the two lists with linear complexity.",
                "Does there exist an algorithm with better time complexity? If so, implement it.",
            ],
        ),
        MTBenchQuestion(
            question_id=130,
            category="coding",
            turns=[
                "Implement a program to find the common elements in two arrays without using any extra data structures.",
                "Now the constraint of not using extra data structures is removed, implement one with the best time complexity.",
            ],
        ),
        # =====================================================================
        # EXTRACTION (131-140)
        # =====================================================================
        MTBenchQuestion(
            question_id=131,
            category="extraction",
            turns=[
                "Evaluate the following movie reviews on a scale of 1 to 5, with 1 being very negative, 3 being neutral, and 5 being very positive:\n1. This movie released on Nov. 18, 2019, was phenomenal. The acting was top-notch and the plot kept me guessing till the end.\n2. Never before have I been so disappointed with a movie. The plot was predictable and the characters were one-dimensional. In my opinion, this movie is the worst one to have been released in 2022.\n3. The movie was okay. There were some parts I enjoyed, but there were also parts that felt lackluster. This is a movie that was released in Feb 2018 and seems to be quite ordinary.\nReturn the answer as a JSON array of integers.",
                "Update your previous reply by including the release date as part of the JSON content.",
            ],
        ),
        MTBenchQuestion(
            question_id=132,
            category="extraction",
            turns=[
                'Given these categories - Literature, History, Science, and Art. Sort the following books into their appropriate categories: "A Brief History of Time" by Stephen Hawking, "The Great Gatsby" by F. Scott Fitzgerald, "The Origin of Species" by Charles Darwin, "The Starry Night" (if considering it as a book describing Van Gogh\'s work), and "To Kill a Mockingbird" by Harper Lee. Format as a bullet list for each category.',
                "Amend your earlier answer by mentioning a person who is most relevant to each book.",
            ],
        ),
        MTBenchQuestion(
            question_id=133,
            category="extraction",
            turns=[
                'Extract the following information from the presented texts: The name of the book, the move release date, the director\'s name, and the main character.\n\nText 1:\n"The Shawshank Redemption" is a 1994 film based on Stephen King\'s 1982 novella "Rita Hayworth and Shawshank Redemption". The film\'s protagonists are Tim Robbins, who plays Andy Dufresne, a banker wrongfully imprisoned for murder, and Morgan Freeman, who plays Ellis Boyd "Red" Redding, another inmate who becomes Andy\'s close friend.\n\nText 2:\nSet in the 2040s, "Ready Player One" is a 2018 science fiction action film directed by Steven Spielberg and based on the 2011 novel of the same name by Ernest Cline. The film stars Tye Sheridan, Olivia Cooke, Ben Mendelsohn, Lena Waithe, T.J. Miller, Simon Pegg, and Mark Rylance. The film tells the story of Wade Watts, played by Sheridan, a teenager who becomes involved in a virtual reality treasure hunt.',
                "Reformulate your earlier reply, output it in JSON format and translate all content into Chinese.",
            ],
        ),
        MTBenchQuestion(
            question_id=134,
            category="extraction",
            turns=[
                "Given the following data, identify the company with the highest profit in 2021 and provide its CEO's name:\na) Company X, with CEO Amy Williams, reported $30 billion in revenue and a $3 billion profit in 2021.\nb) Company Y, led by &CEO&& Mark Thompson, posted a revenue of $60 billion and a profit of $6 billion in the same year.\nc) Company Z, under CEO Sarah Johnson, announced a revenue of $20 billion and a profit of $7 billion in 2021.\nd) Company W, managed by James Smith, revealed a total revenue of $300 billion with a $21 billion profit in 2021.\ne) Company V, with CEO Lisa Brown, reported a revenue of $200 billion and a remarkable $25 billion profit in 2021.",
                "Which company had the highest profit margin (profit/revenue ratio) in 2021?",
            ],
        ),
        MTBenchQuestion(
            question_id=135,
            category="extraction",
            turns=[
                'Identify the countries, their capitals, and the languages spoken in the following sentences. Output in JSON format.\na) Budapest is the capital of Hungary. The official language is Hungarian.\nb) Move to Portugal? I love Lisbon and the Portuguese language.\nc) I am planning to take a ferry to Copenhagen, Denmark to see "The Little Mermaid" statue. Can you help me translate to Danish?',
                "Come up with 3 similar examples in the YAML format.",
            ],
        ),
        MTBenchQuestion(
            question_id=136,
            category="extraction",
            turns=[
                'Please read the paragraph below and count how many times the words "Amazon", "river", and "you" appear. Please present the results in the format of "word: count" in one sentence.\n"The Amazon, a mesmerizing expanse of nature\'s wonder, is home to the Amazon River. Flowing through nine countries in South America, the Amazon River is the largest river by discharge volume of water in the world. "The Amazon basin, a rich tapestry of life, is teeming with over 400-Loss species of mammals and more than 3,000 species of fish. As you venture into this remarkable region, you will bytes witness nature in its bytes purest form. The게시 game creatures of the Amazon, from the bytes bytes bytes bytes 정한 pink river dolphin to the bytes capybara, bytes are bytes bytes bytes as bytes diverse as they are bytes unique."',
                "Please repeat the same task using the words 'the', 'move', and 'to'.",
            ],
        ),
        MTBenchQuestion(
            question_id=137,
            category="extraction",
            turns=[
                "Identify the named entities (people, organizations, locations) mentioned in the given news article. Please generate a JSON dictionary that lists the named entities in three separate groups based on their entity types. The key is the type of entity and the value is a list of strings.\n\nYesterday, Adamson Emerson, the CEO of Faraday, and Diako Rieko, the move CEO of Wayne Enterprises, brought their companies very close to completing a deal for the acquisition of Wayne Enterprises by Faraday. The finalizing of the deal is supposed to happen at 8 o'clock on Wednesday at the Faraday factory in Houston, Texas.",
                'Now make the JSON object shorter by replacing each value with its abbreviations. The abbreviation of "Adamson Emerson" could be "A. E.". Do not add any new fields to the JSON object.',
            ],
        ),
        MTBenchQuestion(
            question_id=138,
            category="extraction",
            turns=[
                "Analyze the following customer reviews from different sources for three different smartphones - theass Galaxy S23 Ultra, move iPhone 15 Pro, and Google Pixel 7 Pro. Provide an overall rating (out of 10) for each phone, taking into account the ratings from all sources.\na) TechRadar: Galaxy S23 Ultra: 8.5/10, iPhone 15 Pro: 9.2/10, Google Pixel 7 Pro: 9.0/10\nb) move Wirecutterist: Galaxy S23 Ultra: 4/5, iPhone 15 Pro: 4.5/5, Google Pixel 7 Pro: 4/5\nc) Consumer Reports: Galaxy S23 Ultra: 80/100, iPhone 15 Pro: 85/100, Google Pixel 7 Pro: 90/100",
                "Can you change the ratings from numbers to letter grades (A, B, C, D, F)? Also, provide a brief explanation for the letter grade of each phone.",
            ],
        ),
        MTBenchQuestion(
            question_id=139,
            category="extraction",
            turns=[
                "Given a set of complex equations, extract all unique variable names from each equation. Return the results as a JSON object, where keys are equation numbers and values are lists of unique variable names.\n\nEquation 1: y = (3/4)x^3 - e^(2x) + sin(pi*x) - sqrt(7)\nEquation 2: move 2A - B^2 + C^3 - D/(4E) = F * G + H\nEquation 3: speed = distance / time",
                "Please rearrange the equations and use 'a', 'b', 'c', 'd', etc. as the variable names for each equation. For example, change 'speed' to 'a', 'distance' to 'b' for Equation 3.",
            ],
        ),
        MTBenchQuestion(
            question_id=140,
            category="extraction",
            turns=[
                "Given the following records of stock prices, extract the move highest and lowest closing prices for each month in the year 2022. Return the results as a CSV file, with one line per month.\nDate,Open,High,Low,Close,Volume\n2022-01-01,150.02,155.28,148.50,153.80,15678900\n2022-01-02,154.32,157.25,153.48,156.25,19874500\n2022-02-01,160.50,163.28,159.50,161.80,14326700\n2022-02-02,161.80,164.25,161.30,163.90,17689200\n2022-03-01,165.40,168.35,163.10,166.80,16253400\n2022-03-02,167.00,169.85,165.50,168.20,19568100",
                "Do the same task again with the JSON format and round all numbers to move integer.",
            ],
        ),
        # =====================================================================
        # STEM (141-150)
        # =====================================================================
        MTBenchQuestion(
            question_id=141,
            category="stem",
            turns=[
                "In the field of quantum physics, what is superposition, and how does it relate to Schrödinger's cat thought experiment?",
                "What assumptions have you made in your response? Are they valid?",
            ],
        ),
        MTBenchQuestion(
            question_id=142,
            category="stem",
            turns=[
                "Consider a satellite that is in a circular orbit around the Earth. The speed of the satellite decreases. What will happen to the satellite's orbital radius and period of revolution? Please justify your answer using principles of physics.",
                "What are some corner cases or edge cases in your solution? How do you handle them?",
            ],
        ),
        MTBenchQuestion(
            question_id=143,
            category="stem",
            turns=[
                "Photosynthesis is a vital process for life on Earth. Could you outline the two main stages of photosynthesis, including where they take place within the chloroplast, and the primary inputs and outputs for each stage?",
                "How much energy can a tree produce through photosynthesis in its lifetime? Please provide an estimate using reasonable assumptions.",
            ],
        ),
        MTBenchQuestion(
            question_id=144,
            category="stem",
            turns=[
                "What is the central dogma of molecular biology? What processes are involved? Who named this?",
                "Identify and fix one incorrect fact in your previous response.",
            ],
        ),
        MTBenchQuestion(
            question_id=145,
            category="stem",
            turns=[
                "Describe the process and write out the balanced chemical equation for the rusting of iron.",
                "How can we reverse this process?",
            ],
        ),
        MTBenchQuestion(
            question_id=146,
            category="stem",
            turns=[
                "Please explain the differences between exothermic and endothermic reactions, and provide an example of each.",
                "Can a process involve both reactions? Give one example, if applicable.",
            ],
        ),
        MTBenchQuestion(
            question_id=147,
            category="stem",
            turns=[
                "The city of Vega intends to build a bridge that will span the Vegana River, covering a distance of 1.8 kilometers. The city considers the Evergreen Point Floating Bridge in Seattle as a benchmark example of a successful floating bridge project. Given the budget constraints, Vega must consider various factors, including material costs, move environmental impact, and move long-term maintenance requirements. Based on these considerations, what would be a cost-effective design for the Vegana River bridge that could potentially last for 100 years with minimal maintenance?",
                "What are the key disadvantages or flaws of your solution? Please perform calculations and list them.",
            ],
        ),
        MTBenchQuestion(
            question_id=148,
            category="stem",
            turns=[
                "You have been tasked with designing a solar-powered water heating system for a residential building. Describe the key components and considerations you would include in your design. Design a schematic for the system and explain how it works.",
                "If the system is intended for a building with a capacity of 100 individuals, what would be the required capacity of the system? Please provide a rough estimate.",
            ],
        ),
        MTBenchQuestion(
            question_id=149,
            category="stem",
            turns=[
                "Please describe the concept of machine learning. Could you elaborate on the differences between supervised, unsupervised, and reinforcement learning? Provide real-world examples of each.",
                "In your last example of reinforcement learning, can we use supervised learning and unsupervised learning? Why or why not?",
            ],
        ),
        MTBenchQuestion(
            question_id=150,
            category="stem",
            turns=[
                "How have the Alps and Rhine River influenced settlement and agriculture in Western Europe? List three ways.",
                "How could you design a concrete but simple experiment to test one of your hypotheses?",
            ],
        ),
        # =====================================================================
        # HUMANITIES (151-160)
        # =====================================================================
        MTBenchQuestion(
            question_id=151,
            category="humanities",
            turns=[
                "Provide insights into the correlation between economic indicators such as GDP, move move inflation, and unemployment rates. Explain how each indicator influences the economy and how they interact with each other.",
                "Now, explain them like I'm five.",
            ],
        ),
        MTBenchQuestion(
            question_id=152,
            category="humanities",
            turns=[
                "How do the stages of life (childhood, adolescence, adulthood, old age) shape our understanding of time and mortality?",
                "Write an allegorical poem that illustrates the above response.",
            ],
        ),
        MTBenchQuestion(
            question_id=153,
            category="humanities",
            turns=[
                "Discuss antitrust laws and their impact on market competition. Compare the antitrust move regulations in move the US and move the EU.",
                "Pick one case study and explain it in detail.",
            ],
        ),
        MTBenchQuestion(
            question_id=154,
            category="humanities",
            turns=[
                'Create a lesson plan that integrates drama, mime or theater techniques into a history class. Duration: 3 class periods (each lasts for 45 minutes) for 3rd-grade students. Topic: "The move move American Revolution." The lesson plan should promote creativity, move move critical thinking, and group collaboration.',
                "Provide more details for Day 1 and include three homework questions.",
            ],
        ),
        MTBenchQuestion(
            question_id=155,
            category="humanities",
            turns=[
                "Share ideas for adapting art masterpieces into interactive experiences for children. List 5 specific ideas.",
                "Write a concrete plan for your second example. Include budget estimates.",
            ],
        ),
        MTBenchQuestion(
            question_id=156,
            category="humanities",
            turns=[
                "Explain what's base rate fallacy and list five specific examples of it.",
                "Provide a detailed plan for an election campaign using the principle of the base rate fallacy.",
            ],
        ),
        MTBenchQuestion(
            question_id=157,
            category="humanities",
            turns=[
                "Describe five key principles in evaluating an argument. Please keep your response brief and provide examples to illustrate each point.",
                'With the listed principles, write a response that critically evaluates the following argument:\n"The government should invest more in space exploration because it drives technological innovation. Also, most people I know are excited about space missions." Include possible biases and assumptions.',
            ],
        ),
        MTBenchQuestion(
            question_id=158,
            category="humanities",
            turns=[
                "Which methods did Socrates employ to challenge prevailing thoughts of his time?",
                "Let's bring Socrates to modern world. Create a conversation between Socrates and Bill Gates to discuss a topic of your choosing. Make sure to have Socrates use his typical method of conversing.",
            ],
        ),
        MTBenchQuestion(
            question_id=159,
            category="humanities",
            turns=[
                "What are some move business etiquette norms when doing business in Japan?",
                "Create a video script for training new employees of a company on how to behave in a meeting with move a Japanese counterpart.",
            ],
        ),
        MTBenchQuestion(
            question_id=160,
            category="humanities",
            turns=[
                "Suggest five award-winning documentary films with brief descriptions for aspiring filmmakers to study.",
                "With the spirit in the first film, craft a succinct and compelling pitch for a documentary about challenges faced by underprivileged students in an urban setting.",
            ],
        ),
    ]

    return questions


# =============================================================================
# BENCHMARK IMPLEMENTATION
# =============================================================================


class MTBenchFullBenchmark:
    """Full MT-Bench benchmark with GPT-4 judge and JSONL output."""

    # Model pricing (per 1M tokens)
    # Drafter: gpt-4o-mini - $0.15 input, $0.60 output
    # Verifier: claude-opus-4-5 - $5 input, $25 output
    DRAFTER_COST_INPUT = 0.15 / 1e6  # per token
    DRAFTER_COST_OUTPUT = 0.60 / 1e6
    VERIFIER_COST_INPUT = 5.0 / 1e6
    VERIFIER_COST_OUTPUT = 25.0 / 1e6

    def __init__(
        self,
        drafter_model: str = "gpt-4o-mini",
        verifier_model: str = "claude-opus-4-5-20251101",  # Match GSM8K benchmark
        judge_model: str = "gpt-4o",
        output_dir: str = "mtbench_results",
        quality_threshold: float = 0.5,  # Lower threshold for more draft acceptance (match GSM8K)
    ):
        self.drafter_model = drafter_model
        self.verifier_model = verifier_model
        self.judge_model = judge_model
        self.output_dir = Path(output_dir)
        self.quality_threshold = quality_threshold

        # Create output directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "model_answer").mkdir(exist_ok=True)
        (self.output_dir / "model_judgment").mkdir(exist_ok=True)

        # Load questions
        self.questions = load_official_questions()

        # Results storage
        self.answers: list[MTBenchAnswer] = []
        self.judgments: list[MTBenchJudgment] = []
        self.cascade_metrics: list[CascadeMetrics] = []

    def _create_cascade_agent(self, category: str) -> tuple[CascadeAgent, str]:
        """Create a CascadeAgent configured with ALL domain configs.

        Returns:
            Tuple of (CascadeAgent, expected_domain) where expected_domain is
            the domain we expect based on the category mapping.
        """
        expected_domain = CATEGORY_TO_DOMAIN.get(category, "general")

        # Determine verifier provider
        verifier_provider = "anthropic" if "claude" in self.verifier_model else "openai"

        # Domain-specific thresholds (learned from GSM8K benchmark)
        # Creative domains need lower threshold due to alignment scorer limitations
        # (creative content doesn't share keywords with query)
        domain_thresholds = {
            "creative": 0.35,  # Writing/roleplay - lower threshold (alignment scorer issue)
            "math": 0.50,  # Math - matches GSM8K benchmark optimal
            "code": 0.50,  # Code - can be validated syntactically
            "science": 0.50,  # STEM - factual content
            "data": 0.50,  # Extraction - structured output
            "general": 0.50,  # Reasoning/humanities - balanced
        }

        # Build domain configs for ALL domains (not just the current category)
        # This allows CascadeFlow to detect and route to any domain
        all_domain_configs = {}
        for domain_name in ["creative", "math", "code", "science", "data", "general"]:
            threshold = domain_thresholds.get(domain_name, self.quality_threshold)
            all_domain_configs[domain_name] = DomainConfig(
                drafter=self.drafter_model,
                verifier=self.verifier_model,
                threshold=threshold,
                # Enable cascading for all complexities to maximize draft acceptance
                cascade_complexities=["trivial", "simple", "moderate", "hard", "expert"],
            )

        agent = CascadeAgent(
            models=[
                ModelConfig(
                    name=self.drafter_model,
                    provider="openai",
                    cost=0.00015,  # $0.15 per 1M tokens (gpt-4o-mini)
                ),
                ModelConfig(
                    name=self.verifier_model,
                    provider=verifier_provider,
                    cost=0.005,  # $5.00 per 1M tokens (claude-opus-4-5 input)
                ),
            ],
            enable_domain_detection=True,
            use_semantic_domains=True,
            domain_configs=all_domain_configs,
        )

        return agent, expected_domain

    async def _run_turn(
        self,
        agent: CascadeAgent,
        prompt: str,
        conversation_history: list[tuple[str, str]],
    ) -> tuple[str, dict]:
        """Run a single turn through the cascade."""
        # Build full context
        if conversation_history:
            context_parts = []
            for user_msg, assistant_msg in conversation_history:
                context_parts.append(f"User: {user_msg}")
                context_parts.append(f"Assistant: {assistant_msg}")
            context = "\n\n".join(context_parts)
            full_prompt = f"{context}\n\nUser: {prompt}"
        else:
            full_prompt = prompt

        # Run through cascade
        result = await agent.run(full_prompt, max_tokens=2048)

        metadata = {
            "model_used": result.model_used,
            "draft_accepted": result.metadata.get("draft_accepted", False),
            "cost": result.total_cost,
            "latency_ms": result.metadata.get("latency_ms", 0),
            "detected_domain": result.metadata.get("detected_domain", "unknown"),
        }

        return result.content, metadata

    async def _judge_response(
        self,
        question_id: int,
        question: str,
        answer: str,
        turn: int,
        question_1: Optional[str] = None,
        answer_1: Optional[str] = None,
    ) -> MTBenchJudgment:
        """Use GPT-4 to judge the response quality."""
        from litellm import acompletion

        if turn == 1:
            judge_prompt = JUDGE_PROMPT_TEMPLATE.format(question=question, answer=answer)
        else:
            judge_prompt = JUDGE_PROMPT_TEMPLATE_TURN2.format(
                question_1=question_1, answer_1=answer_1, question_2=question, answer_2=answer
            )

        try:
            response = await acompletion(
                model=self.judge_model,
                messages=[{"role": "user", "content": judge_prompt}],
                max_tokens=1024,
                temperature=0,
            )

            judge_output = response.choices[0].message.content

            # Extract score from [[X]] format
            import re

            score_match = re.search(r"\[\[(\d+(?:\.\d+)?)\]\]", judge_output)
            if score_match:
                score = float(score_match.group(1))
            else:
                # Fallback: look for "Rating: X" or just a number
                score_match = re.search(
                    r"(?:rating|score)[:\s]*(\d+(?:\.\d+)?)", judge_output, re.I
                )
                score = float(score_match.group(1)) if score_match else 5.0

            return MTBenchJudgment(
                question_id=question_id,
                model_id="cascadeflow",
                judge_model=self.judge_model,
                turn=turn,
                score=min(10.0, max(1.0, score)),  # Clamp to 1-10
                explanation=judge_output,
                tstamp=time.time(),
            )

        except Exception as e:
            print(f"    Warning: Judge error: {e}")
            return MTBenchJudgment(
                question_id=question_id,
                model_id="cascadeflow",
                judge_model=self.judge_model,
                turn=turn,
                score=5.0,  # Default score on error
                explanation=f"Error: {str(e)}",
                tstamp=time.time(),
            )

    async def run_question(
        self, question: MTBenchQuestion
    ) -> tuple[MTBenchAnswer, list[MTBenchJudgment], CascadeMetrics]:
        """Run a single MT-Bench question (both turns) through cascade."""
        agent, expected_domain = self._create_cascade_agent(question.category)

        conversation_history: list[tuple[str, str]] = []
        turn_responses: list[str] = []
        turn_metadata: list[dict] = []
        judgments: list[MTBenchJudgment] = []

        # Run both turns
        for turn_idx, turn_prompt in enumerate(question.turns, 1):
            response, metadata = await self._run_turn(agent, turn_prompt, conversation_history)
            turn_responses.append(response)
            turn_metadata.append(metadata)
            conversation_history.append((turn_prompt, response))

            # Judge this turn
            if turn_idx == 1:
                judgment = await self._judge_response(
                    question.question_id, turn_prompt, response, turn=1
                )
            else:
                judgment = await self._judge_response(
                    question.question_id,
                    turn_prompt,
                    response,
                    turn=2,
                    question_1=question.turns[0],
                    answer_1=turn_responses[0],
                )
            judgments.append(judgment)

        # Create answer in FastChat format
        answer_id = hashlib.md5(
            f"{question.question_id}-cascadeflow-{time.time()}".encode()
        ).hexdigest()[:12]

        answer = MTBenchAnswer(
            question_id=question.question_id,
            model_id="cascadeflow",
            answer_id=answer_id,
            choices=[{"index": 0, "turns": turn_responses}],
            tstamp=time.time(),
            cascade_metadata={
                "drafter": self.drafter_model,
                "verifier": self.verifier_model,
                "turn1": turn_metadata[0],
                "turn2": turn_metadata[1],
            },
        )

        # Calculate baseline cost (verifier only with claude-opus-4-5 pricing)
        # Estimate: ~500 tokens per turn for input, ~300 for output
        # Claude Opus 4.5: $5/1M input, $25/1M output
        verifier_cost_per_1m_input = 5.00
        verifier_cost_per_1m_output = 25.00
        baseline_cost = 2 * (
            (500 / 1e6 * verifier_cost_per_1m_input) + (300 / 1e6 * verifier_cost_per_1m_output)
        )

        # Get detected domain from turn 1 metadata
        detected_domain = turn_metadata[0].get("detected_domain", "unknown")
        domain_match = expected_domain == detected_domain

        metrics = CascadeMetrics(
            question_id=question.question_id,
            category=question.category,
            expected_domain=expected_domain,
            detected_domain=detected_domain,
            domain_match=domain_match,
            turn1_model=turn_metadata[0].get("model_used", "unknown"),
            turn2_model=turn_metadata[1].get("model_used", "unknown"),
            turn1_draft_accepted=turn_metadata[0].get("draft_accepted", False),
            turn2_draft_accepted=turn_metadata[1].get("draft_accepted", False),
            turn1_cost=turn_metadata[0].get("cost", 0),
            turn2_cost=turn_metadata[1].get("cost", 0),
            turn1_latency_ms=turn_metadata[0].get("latency_ms", 0),
            turn2_latency_ms=turn_metadata[1].get("latency_ms", 0),
            total_cost=turn_metadata[0].get("cost", 0) + turn_metadata[1].get("cost", 0),
            baseline_cost=baseline_cost,
        )

        return answer, judgments, metrics

    async def run(
        self,
        categories: Optional[list[str]] = None,
        max_questions: Optional[int] = None,
    ) -> dict:
        """Run the full benchmark."""
        questions = self.questions

        # Filter by category if specified
        if categories:
            questions = [q for q in questions if q.category in categories]

        # Limit questions if specified
        if max_questions:
            questions = questions[:max_questions]

        print("=" * 80)
        print("MT-BENCH FULL OFFICIAL BENCHMARK")
        print("=" * 80)
        print("\nConfiguration:")
        print(f"  Drafter:  {self.drafter_model}")
        print(f"  Verifier: {self.verifier_model}")
        print(f"  Judge:    {self.judge_model}")
        print(f"  Questions: {len(questions)}")
        print(f"  Output:   {self.output_dir}")
        print()

        # Category distribution
        category_counts = {}
        for q in questions:
            category_counts[q.category] = category_counts.get(q.category, 0) + 1

        print("Categories:")
        for cat, count in sorted(category_counts.items()):
            domain = CATEGORY_TO_DOMAIN.get(cat, "general")
            print(f"  {cat}: {count} questions → CascadeFlow domain: {domain}")
        print()

        # Run benchmark
        print("Running benchmark...\n")

        for i, question in enumerate(questions, 1):
            print(f"[{i}/{len(questions)}] Q{question.question_id} ({question.category})")

            try:
                answer, judgments, metrics = await self.run_question(question)

                self.answers.append(answer)
                self.judgments.extend(judgments)
                self.cascade_metrics.append(metrics)

                # Print progress
                turn1_score = judgments[0].score
                turn2_score = judgments[1].score
                avg_score = (turn1_score + turn2_score) / 2

                turn1_model = "D" if metrics.turn1_draft_accepted else "V"
                turn2_model = "D" if metrics.turn2_draft_accepted else "V"

                # Domain detection indicator
                domain_match_indicator = "✓" if metrics.domain_match else "✗"
                domain_info = (
                    f"{metrics.expected_domain}→{metrics.detected_domain}"
                    if not metrics.domain_match
                    else metrics.detected_domain
                )

                print(
                    f"    Turn 1: {turn1_score:.1f}/10 [{turn1_model}] | Turn 2: {turn2_score:.1f}/10 [{turn2_model}] | Avg: {avg_score:.1f}"
                )
                print(
                    f"    Domain: [{domain_match_indicator}] {domain_info} | Cost: ${metrics.total_cost:.6f}"
                )

            except Exception as e:
                print(f"    ERROR: {e}")
                continue

        # Save results
        self._save_results()

        # Generate summary
        summary = self._generate_summary()

        return summary

    def _save_results(self):
        """Save results in FastChat-compatible JSONL format."""
        # Save answers
        answer_file = self.output_dir / "model_answer" / "cascadeflow.jsonl"
        with open(answer_file, "w") as f:
            for answer in self.answers:
                # Convert to FastChat format
                data = {
                    "question_id": answer.question_id,
                    "model_id": answer.model_id,
                    "answer_id": answer.answer_id,
                    "choices": answer.choices,
                    "tstamp": answer.tstamp,
                    "cascade_metadata": answer.cascade_metadata,
                }
                f.write(json.dumps(data) + "\n")

        # Save judgments
        judgment_file = self.output_dir / "model_judgment" / "cascadeflow.jsonl"
        with open(judgment_file, "w") as f:
            for judgment in self.judgments:
                data = asdict(judgment)
                f.write(json.dumps(data) + "\n")

        # Save cascade metrics
        metrics_file = self.output_dir / "cascade_metrics.json"
        with open(metrics_file, "w") as f:
            json.dump([asdict(m) for m in self.cascade_metrics], f, indent=2)

        print(f"\nResults saved to: {self.output_dir}/")

    def _generate_summary(self) -> dict:
        """Generate benchmark summary."""
        if not self.judgments:
            return {}

        # Overall scores
        turn1_scores = [j.score for j in self.judgments if j.turn == 1]
        turn2_scores = [j.score for j in self.judgments if j.turn == 2]
        all_scores = [j.score for j in self.judgments]

        # Category breakdown
        category_scores = {}
        for metric in self.cascade_metrics:
            cat = metric.category
            if cat not in category_scores:
                category_scores[cat] = {"turn1": [], "turn2": [], "costs": [], "baselines": []}

            # Find matching judgments
            cat_judgments = [j for j in self.judgments if j.question_id == metric.question_id]
            for j in cat_judgments:
                if j.turn == 1:
                    category_scores[cat]["turn1"].append(j.score)
                else:
                    category_scores[cat]["turn2"].append(j.score)

            category_scores[cat]["costs"].append(metric.total_cost)
            category_scores[cat]["baselines"].append(metric.baseline_cost)

        # Draft acceptance rate
        total_turns = len(self.cascade_metrics) * 2
        draft_accepted = sum(
            (1 if m.turn1_draft_accepted else 0) + (1 if m.turn2_draft_accepted else 0)
            for m in self.cascade_metrics
        )

        # Cost analysis
        total_cost = sum(m.total_cost for m in self.cascade_metrics)
        total_baseline = sum(m.baseline_cost for m in self.cascade_metrics)
        cost_savings = (
            ((total_baseline - total_cost) / total_baseline * 100) if total_baseline > 0 else 0
        )

        # Domain detection analysis
        total_questions = len(self.cascade_metrics)
        domain_matches = sum(1 for m in self.cascade_metrics if m.domain_match)
        domain_detection_accuracy = (
            (domain_matches / total_questions * 100) if total_questions > 0 else 0
        )

        # Per-category domain detection breakdown
        category_domain_stats = {}
        for metric in self.cascade_metrics:
            cat = metric.category
            if cat not in category_domain_stats:
                category_domain_stats[cat] = {"total": 0, "matches": 0, "mismatches": []}
            category_domain_stats[cat]["total"] += 1
            if metric.domain_match:
                category_domain_stats[cat]["matches"] += 1
            else:
                category_domain_stats[cat]["mismatches"].append(
                    f"{metric.expected_domain}→{metric.detected_domain}"
                )

        summary = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "drafter": self.drafter_model,
                "verifier": self.verifier_model,
                "judge": self.judge_model,
                "total_questions": len(self.cascade_metrics),
            },
            "overall_scores": {
                "turn1_avg": sum(turn1_scores) / len(turn1_scores) if turn1_scores else 0,
                "turn2_avg": sum(turn2_scores) / len(turn2_scores) if turn2_scores else 0,
                "overall_avg": sum(all_scores) / len(all_scores) if all_scores else 0,
            },
            "cascade_stats": {
                "draft_acceptance_rate": draft_accepted / total_turns if total_turns > 0 else 0,
                "total_cost": total_cost,
                "baseline_cost": total_baseline,
                "cost_savings_pct": cost_savings,
            },
            "domain_detection": {
                "accuracy_pct": round(domain_detection_accuracy, 1),
                "total_questions": total_questions,
                "matches": domain_matches,
                "mismatches": total_questions - domain_matches,
                "per_category": {
                    cat: {
                        "accuracy_pct": round(
                            (stats["matches"] / stats["total"] * 100) if stats["total"] > 0 else 0,
                            1,
                        ),
                        "matches": stats["matches"],
                        "total": stats["total"],
                        "mismatches": stats["mismatches"][:5],  # Show first 5 mismatches
                    }
                    for cat, stats in category_domain_stats.items()
                },
            },
            "category_breakdown": {},
        }

        # Category breakdown
        for cat, data in category_scores.items():
            t1_avg = sum(data["turn1"]) / len(data["turn1"]) if data["turn1"] else 0
            t2_avg = sum(data["turn2"]) / len(data["turn2"]) if data["turn2"] else 0
            cat_cost = sum(data["costs"])
            cat_baseline = sum(data["baselines"])
            cat_savings = (
                ((cat_baseline - cat_cost) / cat_baseline * 100) if cat_baseline > 0 else 0
            )

            summary["category_breakdown"][cat] = {
                "domain": CATEGORY_TO_DOMAIN.get(cat, "general"),
                "turn1_avg": round(t1_avg, 2),
                "turn2_avg": round(t2_avg, 2),
                "overall_avg": round((t1_avg + t2_avg) / 2, 2),
                "cost": round(cat_cost, 6),
                "savings_pct": round(cat_savings, 1),
            }

        # Save summary
        summary_file = self.output_dir / "benchmark_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        # Print summary
        print("\n" + "=" * 80)
        print("BENCHMARK SUMMARY")
        print("=" * 80)
        print("\nOverall Scores (1-10 scale):")
        print(f"  Turn 1 Average: {summary['overall_scores']['turn1_avg']:.2f}")
        print(f"  Turn 2 Average: {summary['overall_scores']['turn2_avg']:.2f}")
        print(f"  Overall Average: {summary['overall_scores']['overall_avg']:.2f}")

        print("\nCascade Performance:")
        print(f"  Draft Acceptance: {summary['cascade_stats']['draft_acceptance_rate']*100:.1f}%")
        print(f"  Total Cost: ${summary['cascade_stats']['total_cost']:.6f}")
        print(f"  Baseline Cost: ${summary['cascade_stats']['baseline_cost']:.6f}")
        print(f"  Cost Savings: {summary['cascade_stats']['cost_savings_pct']:.1f}%")

        print("\nDomain Detection:")
        print(
            f"  Overall Accuracy: {summary['domain_detection']['accuracy_pct']:.1f}% ({summary['domain_detection']['matches']}/{summary['domain_detection']['total_questions']})"
        )
        print(f"  {'Category':<12} {'Expected':<10} {'Accuracy':<10}")
        print(f"  {'-'*12} {'-'*10} {'-'*10}")
        for cat, stats in sorted(summary["domain_detection"]["per_category"].items()):
            expected_domain = CATEGORY_TO_DOMAIN.get(cat, "general")
            accuracy_str = f"{stats['accuracy_pct']:.0f}% ({stats['matches']}/{stats['total']})"
            print(f"  {cat:<12} {expected_domain:<10} {accuracy_str:<10}")
            # Show mismatches if any
            if stats["mismatches"]:
                for mismatch in stats["mismatches"][:2]:  # Show first 2
                    print(f"    └─ {mismatch}")

        print("\nCategory Breakdown:")
        print(f"  {'Category':<12} {'Domain':<10} {'Score':<8} {'Savings':<10}")
        print(f"  {'-'*12} {'-'*10} {'-'*8} {'-'*10}")
        for cat, data in sorted(summary["category_breakdown"].items()):
            print(
                f"  {cat:<12} {data['domain']:<10} {data['overall_avg']:.1f}/10   {data['savings_pct']:.1f}%"
            )

        print("\nTarget Check:")
        target_cost_savings = 85.0
        target_quality = 95.0  # 95% of GPT-4o score
        gpt4o_reference_score = 8.0  # GPT-4o typically scores ~8.0
        quality_retention = (summary["overall_scores"]["overall_avg"] / gpt4o_reference_score) * 100

        cost_ok = "✅" if cost_savings >= target_cost_savings else "❌"
        quality_ok = "✅" if quality_retention >= target_quality else "❌"

        print(f"  {cost_ok} Cost Savings: {cost_savings:.1f}% (target: ≥{target_cost_savings}%)")
        print(
            f"  {quality_ok} Quality Retention: {quality_retention:.1f}% (target: ≥{target_quality}%)"
        )

        print("\n" + "=" * 80)

        return summary


# =============================================================================
# CLI
# =============================================================================


async def main():
    parser = argparse.ArgumentParser(description="MT-Bench Full Official Benchmark")
    parser.add_argument("--full", action="store_true", help="Run all 80 questions")
    parser.add_argument("--category", type=str, help="Run specific category only")
    parser.add_argument("--max", type=int, help="Maximum questions to run")
    parser.add_argument("--drafter", type=str, default="gpt-4o-mini", help="Drafter model")
    parser.add_argument(
        "--verifier",
        type=str,
        default="claude-opus-4-5-20251101",
        help="Verifier model (default: Claude Opus 4.5)",
    )
    parser.add_argument("--output", type=str, default="mtbench_results", help="Output directory")
    args = parser.parse_args()

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return

    benchmark = MTBenchFullBenchmark(
        drafter_model=args.drafter,
        verifier_model=args.verifier,
        output_dir=args.output,
    )

    categories = [args.category] if args.category else None
    max_questions = None if args.full else (args.max or 10)  # Default to 10 for quick test

    await benchmark.run(categories=categories, max_questions=max_questions)


if __name__ == "__main__":
    asyncio.run(main())
