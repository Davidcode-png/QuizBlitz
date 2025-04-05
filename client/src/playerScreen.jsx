import React, { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";



function PlayerScreen() {
  const { gamePin, nickname } = useParams();
  const [websocket, setWebsocket] = useState(null);
  const [question, setQuestion] = useState(null);
  const [options, setOptions] = useState([]);
  const [feedback, setFeedback] = useState("");
  const [score, setScore] = useState(0);
  const submitAnswer = (answerIndex) => {
    if (websocket && !feedback){
      websocket.send(JSON.stringify({ action: 'submit_answer', answer: answerIndex }))
    }
  }
  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/join/${gamePin}`);
    ws.onopen = () => {
      console.log("Connected to the websocket");
      ws.send(nickname);
      setWebsocket(ws);
    };
    ws.onclose = () => {
      console.log("Disconnected from WebSocket");
      setWebsocket(null);
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("Received message:", data);
      // Handle different message types from the backend
      if (data.type === "question") {
        setQuestion(data.question);
        setOptions(data.options);
        setFeedback("");
      } else if (data.type === "answer_reveal") {
        setFeedback(data.is_correct ? "Correct!" : "Incorrect.");
        setScore(data.new_score);
      } else if (data.type === "player_joined") {
        console.log(`${data.nickname} joined the game.`);
      } else if (data.type === "error") {
        alert(data.message);
      }
    };
  });

  return (
    <div>
      <h2>Player Screen</h2>
      <p>Game Pin: {gamePin}</p>
      <p>Nickname: {nickname}</p>
      {question && (
        <div>
          <h3>{question}</h3>
          <ul>
            {options.map((option, index) => (
              <li key={index}>
                <button
                  onClick={() => submitAnswer(index)}
                  disabled={feedback !== ""}
                >
                  {option}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {feedback && (
        <p>
          {" "}
          {feedback} Your answer is: {feedback} Score: {score}
        </p>
      )}
      {!question && <p> Waiting for the game to start</p>}
    </div>
  );
}

export default PlayerScreen;
