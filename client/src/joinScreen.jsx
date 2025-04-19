import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";

function JoinScreen() {
  const navigate = useNavigate();
  const [gamePin, setGamePin] = useState("");
  const [nickname, setNickname] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleJoin = async () => {
    if (!gamePin || !nickname) {
      setError("Please enter both a Game PIN and a Nickname.");
      return;
    }
    
    setLoading(true);
    setError("");
    
    try {
      const response = await fetch(`http://localhost:8000/game/${gamePin}/status`);
      
      if (response.ok) {
        navigate(`/player/${gamePin}/${nickname}`);
      } else {
        setError("Invalid game PIN. Please check and try again.");
      }
    } catch (error) {
      console.error("Error joining game:", error);
      setError("Unable to connect to the game server. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleHostGame = () => {
    navigate("/host");
  };

  return (
    <motion.div 
      className="join-screen"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      <div className="logo-container">
        <div className="logo">
          Quiz<span>Blitz</span>
        </div>
      </div>
      
      <div className="card">
        <h2 className="text-center mb-4">Join a Game</h2>
        
        {error && (
          <motion.div 
            className="error-message mb-4"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            style={{ 
              backgroundColor: "rgba(255, 51, 85, 0.1)", 
              color: "var(--danger)",
              padding: "12px",
              borderRadius: "8px",
              textAlign: "center"
            }}
          >
            {error}
          </motion.div>
        )}
        
        <div className="input-group">
          <label className="input-label" htmlFor="gamePin">Game PIN</label>
          <input
            id="gamePin"
            type="text"
            className="input-field"
            placeholder="Enter 6-digit game PIN"
            value={gamePin}
            onChange={(e) => setGamePin(e.target.value.toUpperCase())}
            maxLength={6}
          />
        </div>
        
        <div className="input-group">
          <label className="input-label" htmlFor="nickname">Nickname</label>
          <input
            id="nickname"
            type="text"
            className="input-field"
            placeholder="Enter your nickname"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            maxLength={15}
          />
        </div>
        
        <motion.button
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          className="btn btn-primary btn-block mb-3"
          onClick={handleJoin}
          disabled={loading}
        >
          {loading ? (
            <span>Joining...</span>
          ) : (
            <span>Join Game</span>
          )}
        </motion.button>
        
        <div className="text-center">
          <p className="mb-2">Want to create your own quiz?</p>
          <motion.button
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            className="btn btn-secondary"
            onClick={handleHostGame}
          >
            Host a Game
          </motion.button>
        </div>
      </div>
    </motion.div>
  );
}

export default JoinScreen;