# app/dependencies.py
from fastapi import Depends, HTTPException, status
from app.services.game_service import GameService, QuizService
from app.database.database import get_game_collection

quiz_service = QuizService()

# Ensuring that the game service instance always returns a singleton
_game_service_instance = None


async def get_game_service(game_collection=Depends(get_game_collection)) -> GameService:
    global _game_service_instance
    if _game_service_instance is None:
        if game_collection is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection not available for GameService.",
            )
        _game_service_instance = GameService(
            quiz_service=quiz_service, game_collection=game_collection
        )
        _game_service_instance.game_collection = game_collection
        _game_service_instance.quiz_service = quiz_service
    return _game_service_instance


async def get_game_state_from_db(
    game_pin: str, game_service: GameService = Depends(get_game_service)
) -> dict:
    """Dependency to fetch game state directly from DB, raises 404 if not found."""
    game_data = await game_service.get_game_data_from_db(game_pin)
    if not game_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Game with pin {game_pin} not found.",
        )

    return game_data
