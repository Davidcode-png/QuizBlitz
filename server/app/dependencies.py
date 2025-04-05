# app/dependencies.py
from fastapi import Depends
from app.services.game_service import GameService, QuizService
from app.database.database import get_game_collection

quiz_service = QuizService()


async def get_game_service(game_collection=Depends(get_game_collection)):
    return GameService(quiz_service=quiz_service, game_collection=game_collection)
