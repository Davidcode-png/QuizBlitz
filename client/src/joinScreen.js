import React from "react";
import { useNavigate } from "react-router-dom";

function JoinScreen() {
  const navigate = useNavigate();
  const [gamePin, setGamePin] = React.useState("");
  const [nickname, setNickname] = React.useState("");

  const handleJoin = () => {
    if (gamePin && nickname) {
      navigate(`/player/${gamePin}/${nickname}`);
    } else {
      alert("Enter Nickname and Game Pin.");
    }
  };
  return (
    <div>
      <h2>Join a Game</h2>
      <input
        type="text"
        placeholder="Game Pin"
        value={gamePin}
        onChange={(e) => setGamePin(e.targetValue)}
      />
      <input
        type="text"
        placeholder="Nickname"
        value={nickname}
        onChange={(e) => setNickname(e.targetValue)}
      />
      <button onClick={handleJoin}>Join</button>
    </div>
  );
}

export default JoinScreen;
