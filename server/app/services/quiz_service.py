import json
from typing import Any, List, Optional, Dict
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
        print("QUIZ DATA", quiz_data)
        return [Question(**q) for q in quiz_data]

    def get_quiz_from_external(
        self, external: Optional[Dict[str, Any]] = None
    ) -> List[Question]:
        if external is None:
            return self._get_default_quiz()
        if isinstance(external, str):
            try:
                external = json.loads(external)
            except Exception as e:
                print(f"Error loading external quiz JSON: {e}")
                return []
        return external
