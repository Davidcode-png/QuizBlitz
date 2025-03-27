from pydantic import BaseModel, ConfigDict
from typing import Optional
from fastapi import WebSocket

# from starlette.websockets import WebSocket


class Player(BaseModel):
    websocket: Optional[WebSocket]
    nickname: str
    score: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)
