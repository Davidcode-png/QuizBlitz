from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from fastapi import WebSocket

from app.models.question import Question
from app.models.player import Player


class GameState(BaseModel):
    host: Optional[WebSocket]
    players: List[Player]
    questions: List[Question]
    current_question_index: int = 0
    game_status: str = "waiting"
    player_answers: dict = {}
    current_question_start_time: Optional[float] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )
