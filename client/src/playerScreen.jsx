import React, { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";

function PlayerScreen() {
  const { gamePin, nickname } = useParams();
  const navigate = useNavigate();
  const [websocket, setWebsocket] = useState(null);
  const [question, setQuestion] = useState(null);
  const [options, setOptions] = useState([]);
  const [feedback, setFeedback] = useState("");
  const [score, setScore] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState(null);
  const [timer, setTimer] = useState(null);
  const [initialTimerDuration, setInitialTimerDuration] = useState(0);
  const [countdown, setCountdown] = useState(null);
  const [waitingForNext, setWaitingForNext] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState("connecting");
  const [gameStarted, setGameStarted] = useState(false);
  const [scoreAnimation, setScoreAnimation] = useState(false);
  const [prevScore, setPrevScore] = useState(0);
  const [timerFinished, setTimerFinished] = useState(false);
  const [topPlayers, setTopPlayers] = useState([]);
  const [gameOver, setGameOver] = useState(false);
  const [finalResults, setFinalResults] = useState([]);
  const [questionStartTime, setQuestionStartTime] = useState(null);
  const timerRef = useRef(null);
  const colors = ["#ff5252", "#4caf50", "#2196f3", "#ff9800"];
  const iconNames = ["🔴", "🟢", "🔵", "🟠"];
  const wsRef = useRef(null);

  useEffect(() => {
    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [gamePin]);

  const connectWebSocket = () => {
    const ws = new WebSocket(`ws://localhost:8000/ws/join/${gamePin}`);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("Connected to the websocket");
      ws.send(nickname);
      setWebsocket(ws);
      setConnectionStatus("connected");
    };

    ws.onclose = () => {
      console.log("Disconnected from WebSocket");
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

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("Received message:", data);

      if (data.type === "question") {
        setQuestion(data.question);
        setOptions(data.options);
        setFeedback("");
        setSelectedAnswer(null);
        setWaitingForNext(false);
        setGameStarted(true);
        setTimerFinished(false);
        setQuestionStartTime(Date.now());

        // Start the countdown timer (assuming 20 seconds per question)
        if (data.time_limit) {
          startCountdown(data.time_limit);
        } else {
          startCountdown(20); // Default 20 seconds
        }
      } else if (data.type === "answer_reveal") {
        setFeedback(data.is_correct ? "Correct!" : "Incorrect");
        setPrevScore(score);
        setScore(data.new_score);
        setWaitingForNext(true);

        if (score !== data.new_score) {
          setScoreAnimation(true);
          setTimeout(() => setScoreAnimation(false), 1500);
        }
      } else if (data.type === "leaderboard_update") {
        // Update top players list
        setTopPlayers(data.top_players);
      } else if (data.type === "game_over") {
        // Handle game over state
        setQuestion(null);
        setOptions([]);
        setFeedback("");
        setWaitingForNext(false);
        setGameOver(true);
        setFinalResults(data.results);
      } else if (data.type === "error") {
        alert(data.message);
      }
    };
  };

  const submitAnswer = (answerIndex) => {
    if (websocket && !feedback && !selectedAnswer && !timerFinished) {
      // Calculate time taken to answer (in seconds)
      const timeTaken = (Date.now() - questionStartTime) / 1000;

      websocket.send(
        JSON.stringify({
          action: "submit_answer",
          answer_index: answerIndex,
          time_taken: timeTaken,
        })
      );
      setSelectedAnswer(answerIndex);
    }
  };

  const startCountdown = (seconds) => {
  if (timerRef.current) {
    clearInterval(timerRef.current);
  }

  setCountdown(seconds);
  setInitialTimerDuration(seconds);
  timerRef.current = setInterval(() => {
    setCountdown((prev) => {
      if (prev <= 1) {
        clearInterval(timerRef.current);
        setTimerFinished(true);
        console.log("TIMER FINISHED");
        if (wsRef.current) {
          wsRef.current.send(JSON.stringify({ action: "time_up" }));
        }
        return 0;
      }
      return prev - 1;
    });
  }, 1000);
};

  // useEffect(() => {
  //   return () => {
  //     if (timer) clearInterval(timer);
  //   };
  // }, [timer]);

  const AnimatedScore = () => (
    <motion.div
      key={score}
      initial={{ scale: 1.5, y: -20 }}
      animate={{ scale: 1, y: 0 }}
      className="score-display"
    >
      {score}
    </motion.div>
  );

  // Calculate the progress percentage for timer
  const timerProgress = countdown ? (countdown / initialTimerDuration) * 100 : 0;

  // Render top players leaderboard
  const renderTopPlayers = () => (
    <div className="top-players">
      <h3>Top Players</h3>
      <div className="leaderboard">
        {topPlayers.slice(0, 3).map((player, index) => (
          <div
            key={player.nickname}
            className={`leaderboard-item ${
              player.nickname === nickname ? "current-player" : ""
            }`}
          >
            <div className="rank">{index + 1}</div>
            <div className="player-name">{player.nickname}</div>
            <div className="player-score">{player.score}</div>
          </div>
        ))}
      </div>
    </div>
  );

  // Render game over screen with final results
  const renderGameOver = () => (
  <motion.div
    className="game-over-screen"
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.6, ease: "easeOut" }}
  >
    {/* Clean title */}
    <motion.div
      className="game-over-title"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.1, duration: 0.5 }}
    >
      <h1>Game Over</h1>
    </motion.div>

    <motion.div
      className="final-results"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 0.3, duration: 0.5 }}
    >
      <h2 className="results-title">Final Results</h2>

      {/* Clean podium */}
      <div className="podium-container">
        {finalResults.slice(0, 3).map((player, index) => (
          <motion.div
            key={player.nickname}
            className={`podium-item rank-${index + 1} ${
              player.nickname === nickname ? "current-player" : ""
            }`}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ 
              delay: 0.5 + (index * 0.1), 
              duration: 0.4
            }}
            whileHover={{ 
              y: -2,
              transition: { duration: 0.2 }
            }}
          >
            <div className="rank-number">{index + 1}</div>
            <div className="trophy">
              {index === 0 ? "🏆" : index === 1 ? "🥈" : "🥉"}
            </div>
            <div className="player-info">
              <div className="player-name">{player.nickname}</div>
              <div className="player-score">
                {player.score.toLocaleString()} points
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Clean current player position
      {!finalResults.slice(0, 3).some((p) => p.nickname === nickname) && (
        <motion.div
          className="your-position"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8, duration: 0.4 }}
        >
          <p className="position-label">Your Position</p>
          
          {finalResults.findIndex((p) => p.nickname === nickname) > -1 && (
            <div className="current-player-result">
              <span className="rank">
                #{finalResults.findIndex((p) => p.nickname === nickname) + 1}
              </span>
              <span className="player-name">{nickname}</span>
              <span className="player-score">
                {finalResults.find((p) => p.nickname === nickname)?.score?.toLocaleString()} points
              </span>
            </div>
          )}
        </motion.div>
      )} */}

      {/* Simple button */}
      <motion.button
        className="play-again-btn"
        onClick={() => navigate("/")}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1, duration: 0.4 }}
        whileHover={{ y: -2 }}
        whileTap={{ scale: 0.98  }}
      >
        Play Again
      </motion.button>
    </motion.div>
  </motion.div>
);

  return (
    <motion.div
      className="player-screen"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      <div className="player-header">
        <div
          className="connection-status"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            color:
              connectionStatus === "connected"
                ? "var(--success)"
                : connectionStatus === "connecting"
                ? "var(--warning)"
                : "var(--danger)",
          }}
        >
          <div
            style={{
              width: "10px",
              height: "10px",
              borderRadius: "50%",
              backgroundColor:
                connectionStatus === "connected"
                  ? "var(--success)"
                  : connectionStatus === "connecting"
                  ? "var(--warning)"
                  : "var(--danger)",
            }}
          ></div>
          {connectionStatus === "connected"
            ? "Connected"
            : connectionStatus === "connecting"
            ? "Connecting..."
            : "Disconnected"}
        </div>

        <div className="player-info" style={{ textAlign: "right" }}>
          <div className="nickname" style={{ fontWeight: "600" }}>
            {nickname}
          </div>
          <div className="score-container">
            <span className="score-label">Score:</span>
            <AnimatedScore />
          </div>
          <div className="game-pin-small">Game: {gamePin}</div>
        </div>
      </div>

      {scoreAnimation && (
        <motion.div
          initial={{ opacity: 0, y: -50 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 50 }}
          style={{
            position: "absolute",
            top: "20%",
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: "2rem",
            color: "var(--success)",
            fontWeight: "bold",
          }}
        >
          +{score - prevScore} points!
        </motion.div>
      )}

      {gameOver ? (
        renderGameOver()
      ) : (
        <>
          <AnimatePresence>
            {!gameStarted && (
              <motion.div
                className="waiting-screen"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <h2>Waiting for the game to start</h2>
                <p>
                  Game PIN: <strong>{gamePin}</strong>
                </p>
                <p>
                  You're in as: <strong>{nickname}</strong>
                </p>
                <div className="spinner"></div>
                <p>Wait for the host to start the game...</p>
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {question && (
              <motion.div
                className="question-container"
                key={question}
                initial={{ opacity: 0, y: 50 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -50 }}
                transition={{ duration: 0.5 }}
              >
                {countdown !== null && (
                  <div className="timer-container">
                    <div
                      className="timer-circle"
                      style={{
                        background: `conic-gradient(var(--primary) ${timerProgress}%, #e0e0e0 0)`,
                      }}
                    ></div>
                    <div className="timer-text">{countdown}</div>
                  </div>
                )}

                <h2 className="question-text">{question}</h2>

                <div className="options-grid">
                  {options.map((option, index) => (
                    <motion.button
                      key={index}
                      className={`option-btn option-${index} ${
                        selectedAnswer === index ? "selected" : ""
                      }`}
                      style={{
                        backgroundColor: colors[index],
                        opacity:
                          selectedAnswer !== null && selectedAnswer !== index
                            ? 0.7
                            : 1,
                        transform:
                          selectedAnswer === index ? "scale(1.05)" : "scale(1)",
                      }}
                      whileHover={{
                        scale:
                          selectedAnswer === null && !timerFinished ? 1.05 : 1,
                      }}
                      whileTap={{
                        scale:
                          selectedAnswer === null && !timerFinished ? 0.95 : 1,
                      }}
                      onClick={() => submitAnswer(index)}
                      disabled={
                        selectedAnswer !== null ||
                        feedback !== "" ||
                        timerFinished
                      }
                    >
                      <span style={{ fontSize: "1.5rem", marginRight: "8px" }}>
                        {iconNames[index]}
                      </span>
                      {option}
                    </motion.button>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {(feedback || timerFinished) && (
              <motion.div
                className={`feedback-container ${
                  feedback === "Correct!"
                    ? "correct"
                    : feedback === "Incorrect"
                    ? "incorrect"
                    : "time-up"
                }`}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
              >
                {feedback ? (
                  <div className="feedback-text">{feedback}</div>
                ) : (
                  <div className="feedback-text">Time's Up!</div>
                )}

                <div className="score-info">
                  <div className="current-score">
                    Your Score: <AnimatedScore />
                  </div>
                </div>

                {/* Show top 3 players when waiting for next */}
                {(waitingForNext || timerFinished) &&
                  topPlayers.length > 0 &&
                  renderTopPlayers()}

                {waitingForNext && <p>Waiting for the next question...</p>}
              </motion.div>
            )}
          </AnimatePresence>
        </>
      )}
    </motion.div>
  );
}

export default PlayerScreen;
