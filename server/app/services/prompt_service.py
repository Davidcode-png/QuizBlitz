import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
SYSTEM_PROMPT = """
You are a question generator for a quiz game.

Given a topic or combination of topics, generate 10 multiple-choice questions in the following JSON format:

[
  {
    "question": "Your question here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": <index_of_correct_option (0-based)>,
    "time_limit": 30,
    "correct_answer": <same_as_answer>
  },
  ...
]

Guidelines:
- Each question must have exactly four options.
- The answer field and correct_answer must both be the 0-based index of the correct option (e.g., 1 for the second option).
- The time_limit for every question is 30 seconds.
- Questions must cover the given topic(s) accurately and be appropriate for general audiences.

Now, generate 10 questions on the topic: **{user_input_topic}**

Example topic: “France and Mathematics”
Example output:
[
  {
    "question": "What is the capital of France?",
    "options": ["Berlin", "Madrid", "Paris", "Rome"],
    "answer": 2,
    "time_limit": 30,
    "correct_answer": 2
  },
  {
    "question": "Who is known as the father of modern mathematics?",
    "options": ["Isaac Newton", "Euclid", "Carl Friedrich Gauss", "Leonhard Euler"],
    "answer": 3,
    "time_limit": 30,
    "correct_answer": 3
  },
  ...
]
"""

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")


def get_questions_response(message: str) -> dict:

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]

    try:
        client = OpenAI(
            api_key=PERPLEXITY_API_KEY, base_url="https://api.perplexity.ai"
        )
        response = client.chat.completions.create(
            model="sonar-pro", messages=messages, temperature=0.7
        )

        # Extract the JSON from the response
        content = response.choices[0].message.content.strip()

        # Try to parse as JSON
        try:
            questions_data = json.loads(content)
            return {
                "success": True,
                "data": questions_data,
                "message": "Questions generated successfully",
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON response: {str(e)}",
                "raw_content": content,
            }

    except Exception as e:
        return {"success": False, "error": f"API call failed: {str(e)}"}
