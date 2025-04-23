import json
from typing import Dict, List, Optional
import uuid
from fastapi import WebSocket, status
import asyncio
import time

from app.models.game import GameState
from app.database.database import get_game_collection
from app.models.player import Player
from app.models.question import Question
from app.services.quiz_service import QuizService
from app.websocket.connection_manager import (
    get_connection_manager,
)
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_game_service():
    game_collection = get_game_collection()
    return GameService(game_collection=game_collection)


class GameService:
    def __init__(
        self,
        quiz_service: Optional[QuizService] = None,
        game_collection: AsyncIOMotorCollection = None,
    ):
        self.connection_manager = get_connection_manager()
        self.active_games: Dict[str, GameState] = {}
        self.quiz_service = quiz_service or QuizService()
        self.game_collection = get_game_collection()

    def _get_db_projection(self):
        return {"_id": 0}

    async def create_game(self) -> str:
        if not self.quiz_service:
            logger.error("Cannot create game, QuizService is not available.")
            raise ValueError("QuizService not initialized")
        if self.game_collection is None:
            logger.error("Cannot create game, game_collection is not available.")
            raise ValueError("Database collection not initialized")

        game_pin = str(uuid.uuid4())[:6].upper()
        # Simple uniqueness check (consider retrying if collisions are likely)
        while await self.get_game_data_from_db(game_pin):
            game_pin = str(uuid.uuid4())[:6].upper()

        questions = self.quiz_service._get_default_quiz()

        if not questions:
            logger.error(f"No questions found for game {game_pin}")
            raise ValueError("No questions available")

        game_data_for_db = {
            "game_pin": game_pin,
            "players": [],  # Start with no players in DB
            "questions": [q.dict() for q in questions],  # Store question data
            "current_question_index": 0,
            "game_status": "waiting",
            "player_answers": {},
            "current_question_start_time": None,
            "host_connected": False,  # Track host connection status
        }

        result = await self.game_collection.insert_one(game_data_for_db)
        logger.info(
            f"Game created in DB with pin {game_pin}, Inserted ID: {result.inserted_id}"
        )
        return game_pin

    async def get_all_active_game_pins(self) -> List[str]:
        """Retrieves a list of all game pins from the database."""
        if self.game_collection is None:
            logger.error("get_all_active_game_pins: game_collection is not set!")
            return []
        cursor = self.game_collection.find({}, {"game_pin": 1, "_id": 0})
        pins = [doc["game_pin"] async for doc in cursor]
        logger.debug(f"Fetched active game pins from DB: {pins}")
        return pins

    async def get_game_data_from_db(self, game_pin: str) -> Optional[dict]:
        if self.game_collection is None:
            logger.error("get_game_data_from_db: game collection is not set!")
            return None
        logger.debug(f"Fetching game from the game pin {game_pin}")
        return await self.game_collection.find_one(
            {"game_pin": game_pin}, projection=self._get_db_projection()
        )

    async def _update_game_state_in_db(
        self, game_pin: str, update_data: dict, array_filters=None
    ):
        """
        Update game state in the database with optional array filters
        """
        if self.game_collection is None:
            logger.error("_update_game_state_in_db: game collection is not set!")
            return None

        logger.debug(f"Updating DB for game {game_pin}: {update_data}")

        update_operation = {"$set": update_data}

        try:
            if array_filters:
                result = await self.game_collection.update_one(
                    {"game_pin": game_pin},
                    update_operation,
                    array_filters=array_filters,
                )
            else:
                result = await self.game_collection.update_one(
                    {"game_pin": game_pin}, update_operation
                )

            logger.debug(
                f"DB update result for {game_pin}: Matched={result.matched_count}, Modified={result.modified_count}"
            )
            return result
        except Exception as e:
            logger.error(f"Error updating game state in DB: {e}")
            return None

    async def _push_player_to_db(self, game_pin: str, player_data: dict):
        if self.game_collection is None:
            logger.error("_push_player_to_db: game_collection is not set!")
            return None
        logger.debug(
            f"Adding player {player_data.get('nickname')} to DB for game {game_pin}"
        )
        result = await self.game_collection.update_one(
            {"game_pin": game_pin}, {"$push": {"players": player_data}}
        )
        logger.debug(
            f"DB push player result for {game_pin}: Matched={result.matched_count}, Modified={result.modified_count}"
        )
        return result

    async def _pull_player_from_db(self, game_pin: str, nickname: str):
        if self.game_collection is None:
            logger.error("_pull_player_from_db: game_collection is not set!")
            return None
        logger.debug(f"Removing player {nickname} from DB for game {game_pin}")
        result = await self.game_collection.update_one(
            {"game_pin": game_pin}, {"$pull": {"players": {"nickname": nickname}}}
        )
        logger.debug(
            f"DB pull player result for {game_pin}: Matched={result.matched_count}, Modified={result.modified_count}"
        )
        return result

    async def _update_player_score_in_db(
        self, game_pin: str, nickname: str, new_score: int
    ):
        if self.game_collection is None:
            logger.error("_update_player_score_in_db: game_collection is not set!")
            return None
        logger.debug(
            f"Updating score for player {nickname} to {new_score} in DB for game {game_pin}"
        )
        result = await self.game_collection.update_one(
            {"game_pin": game_pin, "players.nickname": nickname},
            {"$set": {"players.$.score": new_score}},
        )
        logger.debug(
            f"DB update score result for {game_pin}: Matched={result.matched_count}, Modified={result.modified_count}"
        )
        return result

    async def _get_or_create_active_game_state(
        self, game_pin: str
    ) -> Optional[GameState]:
        """
        Gets the GameState from active_games or loads from DB if needed.
        Returns None if game doesn't exist in DB.
        Now incorporates the connection manager for websockets.
        """
        if game_pin in self.active_games:
            game_state = self.active_games[game_pin]

            # Update the host connection from the connection manager
            host_websocket = self.connection_manager.get_host_connection(game_pin)
            game_state.host = host_websocket

            # Update player websockets from the connection manager
            for player in game_state.players:
                player.websocket = self.connection_manager.get_player_connection(
                    game_pin, player.nickname
                )

            return game_state

        game_data = await self.get_game_data_from_db(game_pin)
        if not game_data:
            logger.warning(
                f"_get_or_create_active_game_state: Game {game_pin} not found in DB"
            )
            return None

        # Deserialize data from DB into GameState
        players_from_db = []
        for player_data in game_data.get("players", []):
            nickname = player_data.get("nickname")
            # Get websocket from connection manager if available
            websocket = self.connection_manager.get_player_connection(
                game_pin, nickname
            )
            players_from_db.append(Player(**player_data, websocket=websocket))
        print("HEYY")
        questions_from_db = [
            Question(**q_data) for q_data in game_data.get("questions", [])
        ]

        # Get host websocket from connection manager
        host_websocket = self.connection_manager.get_host_connection(game_pin)

        game_state = GameState(
            host=host_websocket,  # Use host from connection manager
            players=players_from_db,
            questions=questions_from_db,
            current_question_index=game_data.get("current_question_index", 0),
            game_status=game_data.get("game_status", "waiting"),
            player_answers=game_data.get("player_answers", {}),
            current_question_start_time=game_data.get("current_question_start_time"),
        )

        self.active_games[game_pin] = game_state
        logger.info(f"Loaded game {game_pin} from DB into active games.")
        return game_state

    def _cleanup_active_game(self, game_pin: str):
        """Removes a game from active_games if no host or players are connected."""
        if game_pin in self.active_games:
            if not self.connection_manager.get_host_connection(
                game_pin
            ) and not self.connection_manager.get_player_connections(game_pin):
                del self.active_games[game_pin]
                logger.info(
                    f"Removed game {game_pin} from active games (no active host/players)."
                )

    async def connect_host(self, game_pin: str, websocket: WebSocket):
        """Connect a host to a game"""
        # Accept the WebSocket connection
        # await websocket.accept()

        game_state = await self._get_or_create_active_game_state(game_pin)

        if not game_state:
            logger.error(f"Game with pin {game_pin} not found.")
            await websocket.send_text(
                json.dumps(
                    {"type": "error", "message": f"Game with pin {game_pin} not found."}
                )
            )
            raise ValueError(f"Game with pin {game_pin} not found.")

        # Register the host connection in the connection manager
        registration_success = await self.connection_manager.register_host(
            game_pin, websocket
        )

        if not registration_success:
            await websocket.send_text(
                json.dumps({"type": "error", "message": "Host already connected."})
            )
            return False

        # Update the game state with the new host
        game_state.host = websocket

        logger.info(f"Host connected to game {game_pin}")

        # Send connection confirmation
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connection_status",
                    "status": "connected",
                    "message": f"Connected as host for game {game_pin}",
                }
            )
        )

        # Get player list from Redis
        player_list = await self.connection_manager.get_player_list(game_pin)
        logger.info(f"Players in game {game_pin} from Redis: {player_list}")

        # Send existing players to host
        for player in game_state.players:
            try:
                logger.info(f"Sending player {player.nickname} to host")
                await websocket.send_text(
                    json.dumps({"type": "player_joined", "nickname": player.nickname})
                )
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.error(f"Error sending player {player.nickname} to host: {e}")

        # Update DB to indicate host is connected
        await self._update_game_state_in_db(game_pin, {"host_connected": True})

        # Keep connection active and handle messages
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                logger.info(f"Host message received for game {game_pin}: {message}")

                # Process host messages (start game, next question, etc.)
                if message.get("action") == "start_quiz":
                    await self.start_quiz(game_pin, websocket)
                elif message.get("action") == "next_question":
                    await self.next_question(game_pin)

        except Exception as e:
            logger.error(f"Error in host connection: {e}")
            await self.disconnect_host(game_pin)

        return True

    async def connect_player(self, game_pin: str, websocket: WebSocket, nickname: str):
        """Connect a player to a game"""
        # Accept the WebSocket connection
        # await websocket.accept()

        game_state = await self._get_or_create_active_game_state(game_pin)

        if not game_state:
            logger.error(f"Game with pin {game_pin} not found")
            await websocket.send_text(
                json.dumps({"type": "error", "message": "Invalid game pin."})
            )
            return False

        logger.debug(
            f"Existing players in game {game_pin}: {[p.nickname for p in game_state.players]}"
        )

        # Check if nickname is already taken
        existing_player = next(
            (p for p in game_state.players if p.nickname == nickname), None
        )

        if existing_player:
            # If player exists but has no websocket, update the websocket
            existing_player_connection = self.connection_manager.get_player_connection(
                game_pin, nickname
            )
            print("EXISTING PLAYER", existing_player_connection)
            if not existing_player_connection:
                # Register the connection in the connection manager
                await self.connection_manager.register_player(
                    game_pin, nickname, websocket
                )
                existing_player.websocket = websocket
                logger.info(f"Reconnected player {nickname} to game {game_pin}")

                # Important: Notify the host about the reconnected player
                await self.connection_manager.broadcast_to_host(
                    game_pin, {"type": "player_joined", "nickname": nickname}
                )

                # Notify the player
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "joined_game",
                            "message": f"Successfully rejoined game {game_pin}",
                            "nickname": nickname,
                        }
                    )
                )
                return True
            # else:
            #     # Player exists and is connected
            #     await websocket.send_text(
            #         json.dumps({"type": "error", "message": "Nickname already taken"})
            #     )
            #     return False

        # Add new player
        player = Player(websocket=websocket, nickname=nickname, score=0)
        game_state.players.append(player)

        # Register the player connection in the connection manager
        await self.connection_manager.register_player(game_pin, nickname, websocket)

        # Store player in DB (without websocket)
        player_data = player.dict(exclude={"websocket"})
        await self._push_player_to_db(game_pin, player_data)

        logger.info(f"Player {nickname} joined game {game_pin}, notifying host")

        # Notify the host about the new player - CRITICAL PART
        await self.connection_manager.broadcast_to_host(
            game_pin, {"type": "player_joined", "nickname": nickname}
        )

        # Send confirmation to the player
        await websocket.send_text(
            json.dumps(
                {
                    "type": "joined_game",
                    "message": f"Successfully joined game {game_pin}",
                    "nickname": nickname,
                }
            )
        )

        # Handle player messages
        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                logger.info(f"Player {nickname} message for game {game_pin}: {message}")

                # Process player messages (answer submission, etc.)
                if (
                    message.get("action") == "submit_answer"
                    and "answer_index" in message
                ):
                    time_taken = message.get("time_taken", 0)
                    await self.submit_answer(
                        game_pin, websocket, message["answer_index"], time_taken
                    )
                elif message.get("action") == "time_up":
                    # Handle when player time runs out
                    await self.handle_player_timeout(game_pin, websocket)

        except Exception as e:
            logger.error(f"Error in player connection: {e}")
            await self.disconnect_player(game_pin, websocket)

        return True

    async def disconnect_host(self, game_pin: str):
        """Disconnect a host from a game"""
        self.connection_manager.remove_host(game_pin)

        if game_pin in self.active_games:
            game_state = self.active_games[game_pin]
            game_state.host = None
            logger.info(f"Host disconnected from game {game_pin}")

            # Update DB to reflect host disconnection
            await self._update_game_state_in_db(game_pin, {"host_connected": False})

            self._cleanup_active_game(game_pin)
        else:
            logger.warning(
                f"disconnect_host: Game {game_pin} not found in active games."
            )

    async def disconnect_player(self, game_pin: str, websocket: WebSocket):
        """Handle player disconnection by removing them from active connections and notifying others"""
        game_state = self.active_games.get(game_pin)

        if not game_state:
            logger.warning(
                f"disconnect_player: Game {game_pin} not found in active games"
            )
            return

        # Find the player by their websocket
        player_to_remove = None
        for player in game_state.players:
            if player.websocket == websocket:
                player_to_remove = player
                break

        if player_to_remove:
            nickname = player_to_remove.nickname
            logger.info(f"Player {nickname} disconnected from game {game_pin}")

            # Remove from connection manager
            self.connection_manager.remove_player(game_pin, nickname)

            # Remove player websocket from game state
            player_to_remove.websocket = None

            # Update player in DB to mark as disconnected instead of completely removing
            await self._update_game_state_in_db(
                game_pin,
                {f"players.$[elem].connected": False},
                array_filters=[{"elem.nickname": nickname}],
            )

            # Notify host that player has left
            await self.connection_manager.broadcast_to_host(
                game_pin, {"type": "player_left", "nickname": nickname}
            )

            # Notify other players
            await self.connection_manager.broadcast_to_players(
                game_pin,
                {"type": "player_left", "nickname": nickname},
                exclude_websocket=websocket,
            )

            # Clean up active game if no players or host remain
            self._cleanup_active_game(game_pin)
        else:
            logger.warning(
                f"Could not find player with the given websocket in game {game_pin}"
            )

    async def end_game(self, game_pin: str):
        """End a game and notify all participants"""
        game_state = self.active_games.get(game_pin)
        if game_state:
            game_state.game_status = "finished"
            await self._update_game_state_in_db(game_pin, {"game_status": "finished"})

            players_data = [
                {"nickname": p.nickname, "score": p.score} for p in game_state.players
            ]
            final_results = sorted(players_data, key=lambda x: x["score"], reverse=True)

            # Use connection manager to notify everyone
            await self.connection_manager.broadcast_to_all(
                game_pin, {"type": "game_over", "results": final_results}
            )

            # Clean up all connections for this game
            self.connection_manager.cleanup_game(game_pin)

            # Remove from active games
            if game_pin in self.active_games:
                del self.active_games[game_pin]
        else:
            raise ValueError(f"Game with pin {game_pin} not found.")

    async def _send_current_question(self, game_pin: str):
        """Send the current question to host and players"""
        game_state = self.active_games.get(game_pin)
        if game_state and game_state.current_question_index < len(game_state.questions):
            current_question: Question = game_state.questions[
                game_state.current_question_index
            ]

            # Record the time this question was sent
            question_start_time = time.time()
            game_state.current_question_start_time = question_start_time

            # Update in DB
            await self._update_game_state_in_db(
                game_pin, {"current_question_start_time": question_start_time}
            )

            # Send question to players - include time_limit for client-side timer
            question_data = {
                "type": "question",
                "question": current_question.question,
                "options": current_question.options,
                "time_limit": current_question.time_limit
                or 20,  # Default to 20 seconds if not specified
            }
            await self.connection_manager.broadcast_to_players(game_pin, question_data)

            # Send more detailed question to host
            host_question_data = {
                "type": "current_question_host",
                "question": current_question.question,
                "options": current_question.options,
                "question_number": game_state.current_question_index + 1,
                "total_questions": len(game_state.questions),
                "time_limit": current_question.time_limit or 20,
                "correct_answer": current_question.correct_answer,  # Send correct answer to host
            }
            await self.connection_manager.broadcast_to_host(
                game_pin, host_question_data
            )

            # Reset player answers for this question
            game_state.player_answers = {}
            await self._update_game_state_in_db(game_pin, {"player_answers": {}})

        elif game_state:
            await self.end_game(game_pin)
        else:
            raise ValueError(f"Game with pin {game_pin} not found.")

    async def start_quiz(self, game_pin: str, websocket: WebSocket):
        """Start a quiz"""
        game_state = await self._get_or_create_active_game_state(game_pin)

        if not game_state:
            logger.error(f"Game with pin {game_pin} not found.")
            await websocket.send_text(
                json.dumps(
                    {"type": "error", "message": f"Game with pin {game_pin} not found."}
                )
            )
            raise ValueError(f"Game with pin {game_pin} not found.")

        # Check if host is connected
        if not self.connection_manager.get_host_connection(game_pin):
            await websocket.send_text(
                json.dumps({"type": "error", "message": "No host connected."})
            )
            return False

        # Update game state
        game_state.game_status = "in_progress"
        game_state.current_question_index = 0

        # Update in DB
        await self._update_game_state_in_db(
            game_pin, {"game_status": "in_progress", "current_question_index": 0}
        )

        # Send first question
        await self._send_current_question(game_pin)

        # Notify all players that the game has started
        await self.connection_manager.broadcast_to_players(
            game_pin,
            {"type": "game_started"},
        )
        return True

    async def handle_player_timeout(self, game_pin: str, player_websocket: WebSocket):
        """Handle when a player's timer expires without submitting an answer"""
        game_state = self.active_games.get(game_pin)
        if not game_state:
            return False

        # Find player by websocket
        player = None
        for p in game_state.players:
            if p.websocket == player_websocket:
                player = p
                break

        if not player:
            return False

        # Player didn't answer in time
        logger.info(f"Player {player.nickname} timed out for game {game_pin}")

        # Notify host that this player timed out
        await self.connection_manager.broadcast_to_host(
            game_pin,
            {
                "type": "player_timeout",
                "nickname": player.nickname,
                "question_index": game_state.current_question_index,
            },
        )

        # Send feedback to player that they didn't answer in time
        await player_websocket.send_text(
            json.dumps(
                {
                    "type": "answer_reveal",
                    "is_correct": False,
                    "new_score": player.score,
                    "message": "Time's up!",
                }
            )
        )

        return True

    async def submit_answer(
        self,
        game_pin: str,
        player_websocket: WebSocket,
        answer_index: int,
        time_taken: float = 0,
    ):
        """Submit a player's answer"""
        game_state = await self._get_or_create_active_game_state(game_pin)
        if not game_state:
            await player_websocket.send_text(
                json.dumps({"type": "error", "message": "Invalid game pin."})
            )
            return False

        if game_state.game_status != "in_progress":
            await player_websocket.send_text(
                json.dumps({"type": "error", "message": "Game is not in progress."})
            )
            return False

        # Find player by websocket
        player = None
        for p in game_state.players:
            if p.websocket == player_websocket:
                player = p
                break

        if not player:
            await player_websocket.send_text(
                json.dumps({"type": "error", "message": "Player not found in game."})
            )
            return False

        question_index = game_state.current_question_index
        if question_index >= len(game_state.questions):
            await player_websocket.send_text(
                json.dumps({"type": "error", "message": "Invalid question index."})
            )
            return False

        current_question = game_state.questions[question_index]

        # Store the answer
        if str(question_index) not in game_state.player_answers:
            game_state.player_answers[str(question_index)] = {}

        game_state.player_answers[str(question_index)][player.nickname] = answer_index

        # Update in DB
        await self._update_game_state_in_db(
            game_pin,
            {f"player_answers.{question_index}.{player.nickname}": answer_index},
        )

        # Check if the answer is correct
        is_correct = answer_index == current_question.correct_answer

        # Calculate score based on correctness and time taken
        score_to_add = 0
        if is_correct:
            # Base score for correct answer
            base_score = 1000

            # Time factor (faster answers get more points)
            # Assuming a 20-second timer by default
            time_limit = current_question.time_limit or 20
            time_factor = max(0, (time_limit - time_taken) / time_limit)

            # Calculate score
            score_to_add = int(base_score * time_factor)

            # Update player's score
            player.score += score_to_add
            await self._update_player_score_in_db(
                game_pin, player.nickname, player.score
            )

        # Notify player about their answer result
        await player_websocket.send_text(
            json.dumps(
                {
                    "type": "answer_reveal",
                    "is_correct": is_correct,
                    "new_score": player.score,
                    "time_taken": time_taken,
                }
            )
        )

        # Get top players for leaderboard
        top_players = sorted(
            [{"nickname": p.nickname, "score": p.score} for p in game_state.players],
            key=lambda x: x["score"],
            reverse=True,
        )[
            :10
        ]  # Get top 10

        # Send leaderboard update to all players
        await self.connection_manager.broadcast_to_players(
            game_pin, {"type": "leaderboard_update", "top_players": top_players}
        )

        # Notify host about the answer
        await self.connection_manager.broadcast_to_host(
            game_pin,
            {
                "type": "player_answered",
                "nickname": player.nickname,
                "question_index": question_index,
                "answer_index": answer_index,
                "is_correct": is_correct,
                "score_added": score_to_add,
                "new_score": player.score,
            },
        )

        return True

    async def next_question(self, game_pin: str):
        """Move to the next question in the quiz"""
        game_state = await self._get_or_create_active_game_state(game_pin)

        if not game_state:
            logger.error(f"Game with pin {game_pin} not found.")
            raise ValueError(f"Game with pin {game_pin} not found.")

        if game_state.game_status != "in_progress":
            await self.connection_manager.broadcast_to_host(
                game_pin, {"type": "error", "message": "Game is not in progress."}
            )
            return False

        # Move to next question index
        game_state.current_question_index += 1

        # Update in DB
        await self._update_game_state_in_db(
            game_pin, {"current_question_index": game_state.current_question_index}
        )

        # Check if there are more questions
        if game_state.current_question_index < len(game_state.questions):
            # Send new question to all players
            await self._send_current_question(game_pin)
        else:
            # End the game if no more questions
            await self.end_game(game_pin)

        return True
