from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
import json
from app.services.game_service import GameService, get_game_service


async def host_websocket(
    websocket: WebSocket,
    game_pin: str,
    game_service: GameService = Depends(get_game_service),
):
    await websocket.accept()
    try:
        print("YELLO")
        await game_service.connect_host(game_pin, websocket)
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            action = payload.get("action")
            print("HEY, IT PASSED HERE")
            if action == "start_quiz":
                await game_service.start_quiz(
                    game_pin, websocket
                )  # Added websocket parameter
            elif action == "next_question":
                await game_service.next_question(game_pin)
    except WebSocketDisconnect:
        game_service.disconnect_host(game_pin)
        print(f"Host disconnected from game {game_pin}")
    except Exception as e:
        print(f"Error in host websocket for game {game_pin}: {e}")
