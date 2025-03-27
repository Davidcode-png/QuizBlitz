import React, { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";

function PlayerScreen() {
  const { gamePin, nickname } = useParams();
  const [websocket, setWebsocket] = useState(null);
  const [question, setQuestion] = useState(null);
  const [options, setOptions] = useState([]);
  const [feedback, setFeedback] = useState("");
  const [score, setScore] = useState(0);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/join/${gamePin}`);
    ws.onopen = () => {
      console.log("Connected to the websocket");
      ws.send(nickname);
      setWebsocket(ws);
    }
    ws.onclose = () => {
      console.log('Disconnected from WebSocket');
      setWebsocket(null);
    };
  })

  return (
    <div>
      <h2>Player Screen</h2>
      <p>Game Pin: {gamePin}</p>
      <p>Nickname: {nickname}</p>
    </div>
  );
}

export default PlayerScreen;
