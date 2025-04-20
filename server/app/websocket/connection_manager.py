import json
import asyncio
from typing import Dict, List, Optional, Set
import logging
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import redis.asyncio as redis
from redis.asyncio import Redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RedisConnectionManager:
    """
    Connection manager that uses Redis to track WebSocket connections
    This allows for distributed connection management across multiple server instances
    """

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialize the connection manager with Redis connection"""
        self.redis_url = redis_url
        self.redis: Optional[Redis] = None
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
        self.host_connections: Dict[str, WebSocket] = {}
        self.heartbeat_tasks: Dict[str, Dict[str, asyncio.Task]] = (
            {}
        )  # Track heartbeat tasks

    async def connect_to_redis(self):
        """Connect to Redis if not already connected with retry logic"""
        if self.redis is None:
            retry_count = 0
            max_retries = 3

            while retry_count < max_retries:
                try:
                    self.redis = await redis.from_url(
                        self.redis_url, encoding="utf-8", decode_responses=True
                    )
                    # Test connection with ping
                    await self.redis.ping()
                    logger.info(f"Connected to Redis at {self.redis_url}")
                    return
                except Exception as e:
                    retry_count += 1
                    logger.warning(
                        f"Redis connection attempt {retry_count} failed: {e}"
                    )
                    if retry_count >= max_retries:
                        logger.error(
                            f"Failed to connect to Redis after {max_retries} attempts"
                        )
                        raise
                    await asyncio.sleep(1)  # Wait before retrying

    async def start_heartbeat(self, game_pin: str, is_host: bool, nickname: str = None):
        """Start heartbeat for a connection to keep it alive"""
        key = f"host:{game_pin}" if is_host else f"player:{game_pin}:{nickname}"

        # Initialize heartbeat tracking for this game if not exists
        if game_pin not in self.heartbeat_tasks:
            self.heartbeat_tasks[game_pin] = {}

        # Create and track the heartbeat task
        task = asyncio.create_task(self._heartbeat_loop(game_pin, is_host, nickname))
        self.heartbeat_tasks[game_pin][key] = task

    async def _heartbeat_loop(self, game_pin: str, is_host: bool, nickname: str = None):
        """Send periodic pings to keep the connection alive"""
        try:
            while True:
                await asyncio.sleep(25)  # Send ping every 25 seconds

                try:
                    if is_host:
                        host_ws = self.get_host_connection(game_pin)
                        if host_ws:
                            await host_ws.send_text(json.dumps({"type": "ping"}))
                    else:
                        player_ws = self.get_player_connection(game_pin, nickname)
                        if player_ws:
                            await player_ws.send_text(json.dumps({"type": "ping"}))
                except Exception as e:
                    logger.debug(
                        f"Heartbeat failed for {'host' if is_host else f'player {nickname}'} in game {game_pin}: {e}"
                    )
                    # Allow the loop to continue and try again until the task is cancelled
        except asyncio.CancelledError:
            logger.debug(
                f"Heartbeat canceled for {'host' if is_host else f'player {nickname}'} in game {game_pin}"
            )
        except Exception as e:
            logger.error(
                f"Error in heartbeat for {'host' if is_host else f'player {nickname}'} in game {game_pin}: {e}"
            )

    def stop_heartbeat(self, game_pin: str, is_host: bool, nickname: str = None):
        """Stop heartbeat for a connection"""
        if game_pin in self.heartbeat_tasks:
            key = f"host:{game_pin}" if is_host else f"player:{game_pin}:{nickname}"
            if key in self.heartbeat_tasks[game_pin]:
                self.heartbeat_tasks[game_pin][key].cancel()
                del self.heartbeat_tasks[game_pin][key]

                # Clean up if no more heartbeats for this game
                if not self.heartbeat_tasks[game_pin]:
                    del self.heartbeat_tasks[game_pin]

    async def register_host(self, game_pin: str, websocket: WebSocket) -> bool:
        """Register a host connection for a game"""
        await self.connect_to_redis()

        # Check if host already exists in Redis
        host_exists = await self.redis.exists(f"host:{game_pin}")
        if host_exists:
            # Check if the host is still active in our local tracking
            if (
                game_pin in self.host_connections
                and self.host_connections[game_pin].client_state == 1
            ):
                logger.warning(f"Host already connected for game {game_pin}")
                return False
            else:
                # Host exists in Redis but not active locally, clean up
                await self.redis.delete(f"host:{game_pin}")

        # Store host connection locally
        self.host_connections[game_pin] = websocket

        # Store in Redis with expiration (e.g., 2 hours)
        await self.redis.set(f"host:{game_pin}", "connected", ex=7200)

        # Start heartbeat for host
        await self.start_heartbeat(game_pin, is_host=True)

        logger.info(f"Host registered for game {game_pin}")
        return True

    def remove_host(self, game_pin: str):
        """Remove a host connection"""
        # Stop heartbeat first
        self.stop_heartbeat(game_pin, is_host=True)

        if game_pin in self.host_connections:
            del self.host_connections[game_pin]

        # Schedule Redis cleanup to run asynchronously
        asyncio.create_task(self._remove_host_from_redis(game_pin))

    async def _remove_host_from_redis(self, game_pin: str):
        """Remove host from Redis storage"""
        try:
            await self.connect_to_redis()
            await self.redis.delete(f"host:{game_pin}")
            logger.info(f"Host removed for game {game_pin}")
        except Exception as e:
            logger.error(f"Error removing host from Redis for game {game_pin}: {e}")

    def get_host_connection(self, game_pin: str) -> Optional[WebSocket]:
        """Get the host connection for a game if it exists and is active"""
        print("HOST CONNECTIONS", self.host_connections)
        if game_pin in self.host_connections:
            host = self.host_connections[game_pin]
            print("HOST", host)
            print("CONNECTION", host.client_state)
            try:
                if host.client_state == WebSocketState.CONNECTED:  # Check if connection is still active
                    return host
            except Exception:
                # If access to client_state raises an exception, connection is likely broken
                pass

            # Clean up stale connection
            # logger.debug(f"Removing stale host connection for game {game_pin}")
            # self.remove_host(game_pin)

        return None

    async def register_player(
        self, game_pin: str, nickname: str, websocket: WebSocket
    ) -> bool:
        """Register a player connection"""
        await self.connect_to_redis()

        # Initialize the game's player dictionary if it doesn't exist
        if game_pin not in self.active_connections:
            self.active_connections[game_pin] = {}

        # Store the connection
        self.active_connections[game_pin][nickname] = websocket

        # Store in Redis with expiration (e.g., 2 hours)
        await self.redis.hset(f"players:{game_pin}", nickname, "connected")
        await self.redis.expire(f"players:{game_pin}", 7200)

        # Start heartbeat for player
        await self.start_heartbeat(game_pin, is_host=False, nickname=nickname)

        logger.info(f"Player {nickname} registered for game {game_pin}")
        return True

    def remove_player(self, game_pin: str, nickname: str):
        """Remove a player connection"""
        # Stop heartbeat first
        self.stop_heartbeat(game_pin, is_host=False, nickname=nickname)

        if (
            game_pin in self.active_connections
            and nickname in self.active_connections[game_pin]
        ):
            del self.active_connections[game_pin][nickname]

            # If no more players in this game, clean up
            if not self.active_connections[game_pin]:
                del self.active_connections[game_pin]

        # Schedule Redis cleanup to run asynchronously
        asyncio.create_task(self._remove_player_from_redis(game_pin, nickname))

    async def _remove_player_from_redis(self, game_pin: str, nickname: str):
        """Remove player from Redis storage"""
        try:
            await self.connect_to_redis()
            await self.redis.hdel(f"players:{game_pin}", nickname)
            logger.info(f"Player {nickname} removed from game {game_pin}")
        except Exception as e:
            logger.error(f"Error removing player from Redis for game {game_pin}: {e}")

    def get_player_connection(
        self, game_pin: str, nickname: str
    ) -> Optional[WebSocket]:
        """Get a specific player's WebSocket connection"""
        if (
            game_pin in self.active_connections
            and nickname in self.active_connections[game_pin]
        ):
            player_ws = self.active_connections[game_pin][nickname]
            try:
                if player_ws.client_state == 1:  # Check if connection is still active
                    return player_ws
            except Exception:
                # If access to client_state raises an exception, connection is likely broken
                pass

            # Clean up stale connection
            self.remove_player(game_pin, nickname)

        return None

    def get_player_connections(self, game_pin: str) -> Dict[str, WebSocket]:
        """Get all active player connections for a game"""
        if game_pin in self.active_connections:
            # Filter out any closed connections
            active_players = {}
            to_remove = []

            for nickname, ws in self.active_connections[game_pin].items():
                try:
                    if ws.client_state == 1:  # Check if connection is still active
                        active_players[nickname] = ws
                    else:
                        to_remove.append(nickname)
                except Exception:
                    # If accessing client_state raises an exception, connection is broken
                    to_remove.append(nickname)

            # Clean up stale connections
            for nickname in to_remove:
                self.remove_player(game_pin, nickname)

            return active_players
        return {}

    async def get_player_list(self, game_pin: str) -> List[str]:
        """Get list of all players in a game from Redis"""
        try:
            await self.connect_to_redis()
            players = await self.redis.hkeys(f"players:{game_pin}")
            return players
        except Exception as e:
            logger.error(
                f"Error getting player list from Redis for game {game_pin}: {e}"
            )
            return []

    async def broadcast_to_host(self, game_pin: str, message: dict):
        """Send a message to the host of a game"""
        host_ws = self.get_host_connection(game_pin)
        print("HOST WS", host_ws)
        if host_ws:
            try:
                await host_ws.send_text(json.dumps(message))
                logger.debug(
                    f"Message sent to host of game {game_pin}: {message['type']}"
                )
            except WebSocketDisconnect:
                logger.info(
                    f"Host disconnected while sending message for game {game_pin}"
                )
                self.remove_host(game_pin)
            except Exception as e:
                logger.error(f"Error sending message to host: {e}")
                # self.remove_host(game_pin)
        else:
            logger.warning(f"No active host connection for game {game_pin}")

    async def broadcast_to_players(
        self,
        game_pin: str,
        message: dict,
        exclude_nickname: str = None,
        exclude_websocket: WebSocket = None,
    ):
        """Send a message to all players in a game, with optional exclusions"""
        players = self.get_player_connections(game_pin)
        to_remove = []

        for nickname, websocket in players.items():
            if (exclude_nickname and nickname == exclude_nickname) or (
                exclude_websocket and websocket == exclude_websocket
            ):
                continue

            try:
                await websocket.send_text(json.dumps(message))
            except WebSocketDisconnect:
                logger.info(f"Player {nickname} disconnected while sending message")
                to_remove.append(nickname)
            except Exception as e:
                logger.error(f"Error sending message to player {nickname}: {e}")
                to_remove.append(nickname)

        # Clean up disconnected players
        for nickname in to_remove:
            self.remove_player(game_pin, nickname)

    async def broadcast_to_all(self, game_pin: str, message: dict):
        """Send a message to all participants (host and players) in a game"""
        # Send to host
        await self.broadcast_to_host(game_pin, message)

        # Send to all players
        await self.broadcast_to_players(game_pin, message)

    def cleanup_game(self, game_pin: str):
        """Remove all connections for a game"""
        # Clean up heartbeats
        if game_pin in self.heartbeat_tasks:
            for task in self.heartbeat_tasks[game_pin].values():
                task.cancel()
            del self.heartbeat_tasks[game_pin]

        # Clean up host
        if game_pin in self.host_connections:
            del self.host_connections[game_pin]

        # Clean up players
        if game_pin in self.active_connections:
            del self.active_connections[game_pin]

        # Schedule Redis cleanup to run asynchronously
        asyncio.create_task(self._cleanup_game_from_redis(game_pin))

    async def _cleanup_game_from_redis(self, game_pin: str):
        """Remove all game data from Redis"""
        try:
            await self.connect_to_redis()
            await self.redis.delete(f"host:{game_pin}")
            await self.redis.delete(f"players:{game_pin}")
            logger.info(f"Cleaned up game {game_pin} from Redis")
        except Exception as e:
            logger.error(f"Error cleaning up game from Redis: {e}")

    async def test_redis_connection(self) -> bool:
        """Test if Redis is reachable"""
        try:
            await self.connect_to_redis()
            await self.redis.ping()
            logger.info("Redis connection test successful!")
            return True
        except Exception as e:
            logger.error(f"Redis connection test failed: {e}")
            return False


# Singleton instance
_redis_connection_manager = None


def get_connection_manager() -> RedisConnectionManager:
    """Get the global Redis connection manager instance"""
    global _redis_connection_manager
    if _redis_connection_manager is None:
        _redis_connection_manager = RedisConnectionManager(
            redis_url="redis://127.0.0.1:6379"
        )
    return _redis_connection_manager
