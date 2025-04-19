import React, { useState, useEffect, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";

function HostScreen() {
  const { gamePin } = useParams();
  const navigate = useNavigate();
  const [websocket, setWebsocket] = useState(null);
  const [players, setPlayers] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [questionNumber, setQuestionNumber] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [connectionStatus, setConnectionStatus] = useState("disconnected");
  const [gameStatus, setGameStatus] = useState("waiting");
  const wsRef = useRef(null);

  useEffect(() => {
    if (!gamePin) return;

    const connectWebSocket = () => {
      setConnectionStatus("connecting");
      const ws = new WebSocket(`ws://localhost:8000/ws/host/${gamePin}`);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("Host connected to WebSocket");
        setWebsocket(ws);
        setConnectionStatus("connected");
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log("Host received message:", data);

        // Handle different message types
        switch (data.type) {
          case "player_joined":
            console.log("Player joined:", data.nickname);
            setPlayers((prevPlayers) => {
              if (!prevPlayers.includes(data.nickname)) {
                return [...prevPlayers, data.nickname];
              }
              return prevPlayers;
            });
            break;

          case "player_left":
            console.log(`Player left: ${data.nickname}`);
            setPlayers((prevPlayers) =>
              prevPlayers.filter((nick) => nick !== data.nickname)
            );
            break;

          case "current_question_host":
            setCurrentQuestion(data.question);
            setQuestionNumber(data.question_number);
            setTotalQuestions(data.total_questions);
            setGameStatus("in_progress");
            break;

          case "game_over":
            setGameStatus("finished");
            // Handle game over state
            break;

          case "connection_status":
            console.log(`Connection status: ${data.status}`);
            setConnectionStatus(data.status);
            break;

          case "error":
            console.error(`Error from server: ${data.message}`);
            alert(`Error: ${data.message}`);
            break;

          default:
            console.log("Unknown message type:", data);
        }
      };

      ws.onclose = (event) => {
        console.log("Host disconnected from WebSocket", event);
        setWebsocket(null);
        setConnectionStatus("disconnected");

        // Attempt to reconnect after a delay
        setTimeout(() => {
          if (document.visibilityState === "visible") {
            connectWebSocket();
          }
        }, 3000);
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setConnectionStatus("error");
      };
    };

    connectWebSocket();

    // Cleanup function
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [gamePin]);

  const createNewGame = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/host/new", {
        method: "POST",
      });
      if (response.ok) {
        const data = await response.json();
        navigate(`/host/${data.game_pin}`);
      } else {
        console.error("Failed to create a new game");
        alert("Failed to create a new game. Please try again.");
      }
    } catch (error) {
      console.error("Error creating new game:", error);
      alert(
        "Error creating new game. Please check your connection and try again."
      );
    }
  };

  const startGame = () => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.send(JSON.stringify({ action: "start_quiz" }));
      setGameStatus("starting");
    } else {
      alert("Not connected to the server. Please wait or refresh the page.");
    }
  };

  const nextQuestion = () => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.send(JSON.stringify({ action: "next_question" }));
    } else {
      alert("Not connected to the server. Please wait or refresh the page.");
    }
  };

  // Helper for connection status visual indicator
  const getConnectionStatusColor = () => {
    switch (connectionStatus) {
      case "connected":
        return "#4caf50"; // green
      case "connecting":
        return "#ff9800"; // orange
      case "disconnected":
      case "error":
        return "#f44336"; // red
      default:
        return "#9e9e9e"; // grey
    }
  };

  return (
    <div className="host-screen-container">
      <header className="host-header">
        <h1>Quiz Host Dashboard</h1>
        <div
          className="connection-indicator"
          style={{ backgroundColor: getConnectionStatusColor() }}
        >
          {connectionStatus}
        </div>
      </header>

      {!gamePin ? (
        <div className="create-game-container">
          <h2>Welcome to the Quiz Host Dashboard</h2>
          <p>Create a new game to get started!</p>
          <button className="primary-button" onClick={createNewGame}>
            Create New Game
          </button>
        </div>
      ) : (
        <div className="game-dashboard">
          <div className="game-info-panel">
            <h2>
              Game Pin: <span className="highlight">{gamePin}</span>
            </h2>
            <p>Share this PIN with your players so they can join</p>

            <div className="player-list-container">
              <h3>Players Joined: {players.length}</h3>
              {players.length === 0 ? (
                <p className="no-players-message">No players have joined yet</p>
              ) : (
                <ul className="player-list">
                  {players.map((player, index) => (
                    <li key={index} className="player-item">
                      {player}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {gameStatus === "waiting" && (
              <button
                className="primary-button start-button"
                onClick={startGame}
                disabled={!players.length || connectionStatus !== "connected"}
              >
                {players.length ? "Start Quiz" : "Waiting for Players"}
              </button>
            )}
          </div>

          {gameStatus !== "waiting" && currentQuestion && (
            <div className="question-control-panel">
              <div className="question-header">
                <h3>
                  Question {questionNumber}/{totalQuestions}
                </h3>
              </div>

              <div className="question-content">
                <p className="question-text">{currentQuestion}</p>
              </div>

              <div className="question-controls">
                <button
                  className="primary-button next-button"
                  onClick={nextQuestion}
                  disabled={connectionStatus !== "connected"}
                >
                  Next Question
                </button>
              </div>
            </div>
          )}

          {gameStatus === "finished" && (
            <div className="game-over-panel">
              <h2>Game Over!</h2>
              <button className="primary-button" onClick={createNewGame}>
                Start a New Game
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default HostScreen;
