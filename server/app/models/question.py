from pydantic import BaseModel
from typing import List


class Question(BaseModel):
    question: str
    options: List[str]
    answer: int #Index of the correct answer
