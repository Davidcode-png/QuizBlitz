import json
from typing import List
from app.models.question import Question


class QuizService:
    def __init__(self, quiz_file: str = r"app/services/default_quiz.json"):
        self.quiz_file = quiz_file
        self.quizzes = self._load_quizzes()

    def _load_quizzes(self) -> dict:
        try:
            with open(self.quiz_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warinng! Quiz {self.quiz_file} was not found.")
            return {"default": []}

    def _get_default_quiz(self) -> List[Question]:
        quiz_data = self.quizzes.get("default", [])
        return [Question(**q) for q in quiz_data]
