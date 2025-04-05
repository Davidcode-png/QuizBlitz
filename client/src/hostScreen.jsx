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

  useEffect(() => {
    if (!gamePin) return;
    const ws = new WebSocket(`ws://localhost:8000/ws/host/${gamePin}`);

    ws.onopen = () => {
      console.log("Host connected to WebSocket");
      setWebsocket(ws);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("Host received message:", data);
      if (data.type === "player_joined") {
        setPlayers((prevPlayers) => [...prevPlayers, data.nickname]);
      } else if (data.type === "player_left") {
        setPlayers((prevPlayers) =>
          prevPlayers.filter((nick) => nick !== data.nickname)
        );
      } else if (data.type === "current_question_host") {
        setCurrentQuestion(data.question);
        setQuestionNumber(data.question_number);
        setTotalQuestions(data.total_questions);
      }
    };

    ws.onclose = () => {
      console.log("Host disconnected from WebSocket");
      setWebsocket(null);
    };

    return () => {
      if (ws) {
        ws.close();
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
      }
    } catch (error) {
      console.error("Error creating new game:", error);
    }
  };

  const startGame = () => {
    if (websocket) {
      websocket.send(JSON.stringify({ action: "start_quiz" }));
    }
  };

  const nextQuestion = () => {
    if (websocket) {
      websocket.send(JSON.stringify({ action: "next_question" }));
    }
  };

  return (
    <div>
      <h2>Host Screen</h2>
      {!gamePin ? (
        <button onClick={createNewGame}>Create New Game</button>
      ) : (
        <div>
          <p>Game Pin: {gamePin}</p>
          <h3>Players Joined:</h3>
          <ul>
            {players.map((player, index) => (
              <li key={index}>{player}</li>
            ))}
          </ul>
          <button onClick={startGame} disabled={!players.length}>
            Start Quiz
          </button>
          {currentQuestion && (
            <div>
              <h3>
                Question {questionNumber}/{totalQuestions}
              </h3>
              <p>{currentQuestion}</p>
              <button onClick={nextQuestion}>Next Question</button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default HostScreen;
