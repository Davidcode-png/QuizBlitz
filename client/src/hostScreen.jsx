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

  // AI Modal states
  const [showAIModal, setShowAIModal] = useState(false);
  const [aiPrompt, setAiPrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedQuestions, setGeneratedQuestions] = useState([]);
  const [editingQuestion, setEditingQuestion] = useState(null);

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

  // AI Question Generation Functions
  const generateQuestions = async () => {
    if (!aiPrompt.trim()) {
      alert("Please enter a topic or description for the questions");
      return;
    }

    setIsGenerating(true);
    try {
      const response = await fetch("http://localhost:8000/api/host/generate", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: aiPrompt,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        if (data.questions && data.questions.success && data.questions.data) {
          setGeneratedQuestions(data.questions.data);
        } else {
          alert("Failed to generate questions. Please try again.");
        }
      } else {
        console.error("Failed to generate questions");
        alert("Failed to generate questions. Please try again.");
      }
    } catch (error) {
      console.error("Error generating questions:", error);
      alert(
        "Error generating questions. Please check your connection and try again."
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const editQuestion = (index) => {
    setEditingQuestion({
      index,
      ...generatedQuestions[index],
    });
  };

  const saveEditedQuestion = () => {
    if (editingQuestion) {
      const updatedQuestions = [...generatedQuestions];
      updatedQuestions[editingQuestion.index] = {
        question: editingQuestion.question,
        options: editingQuestion.options,
        answer: editingQuestion.answer,
        time_limit: editingQuestion.time_limit,
        correct_answer: editingQuestion.correct_answer,
      };
      setGeneratedQuestions(updatedQuestions);
      setEditingQuestion(null);
    }
  };

  const deleteQuestion = (index) => {
    const updatedQuestions = generatedQuestions.filter((_, i) => i !== index);
    setGeneratedQuestions(updatedQuestions);
  };

  const useGeneratedQuestions = async () => {
    if (generatedQuestions.length === 0) {
      alert("No questions to use");
      return;
    }

    try {
      const response = await fetch("http://localhost:8000/api/host/new-game", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(generatedQuestions),
      });

      if (response.ok) {
        const data = await response.json();
        closeAIModal();
        navigate(`/host/${data.game_pin}`);
      } else {
        console.error("Failed to create game with questions");
        alert("Failed to create game with questions. Please try again.");
      }
    } catch (error) {
      console.error("Error creating game with questions:", error);
      alert("Error creating game. Please check your connection and try again.");
    }
  };

  const closeAIModal = () => {
    setShowAIModal(false);
    setAiPrompt("");
    setGeneratedQuestions([]);
    setEditingQuestion(null);
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
        <div className="header-controls">
          <button
            className="ai-button"
            onClick={() => setShowAIModal(true)}
            title="Generate AI Questions"
          >
            🤖
          </button>
          <div
            className="connection-indicator"
            style={{ backgroundColor: getConnectionStatusColor() }}
          >
            {connectionStatus}
          </div>
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

      {/* AI Modal */}
      {showAIModal && (
        <div
          className="modal-overlay"
          onClick={(e) =>
            e.target.className === "modal-overlay" && closeAIModal()
          }
        >
          <div className="modal-content">
            <div className="modal-header">
              <h2>🤖 AI Question Generator</h2>
              <button className="close-button" onClick={closeAIModal}>
                ×
              </button>
            </div>

            <div className="modal-body">
              {generatedQuestions.length === 0 ? (
                <div className="prompt-section">
                  <label htmlFor="ai-prompt">
                    Describe the topic or type of questions you want:
                  </label>
                  <textarea
                    id="ai-prompt"
                    className="ai-prompt-input"
                    value={aiPrompt}
                    onChange={(e) => setAiPrompt(e.target.value)}
                    placeholder="e.g., questions trivia on Messi and Ronaldo"
                    rows={4}
                    disabled={isGenerating}
                  />
                  <button
                    className="generate-button"
                    onClick={generateQuestions}
                    disabled={isGenerating || !aiPrompt.trim()}
                  >
                    {isGenerating ? "Generating..." : "Generate Questions"}
                  </button>
                </div>
              ) : (
                <div className="questions-section">
                  <div className="questions-header">
                    <h3>Generated Questions ({generatedQuestions.length})</h3>
                    <button
                      className="new-generation-button"
                      onClick={() => {
                        setGeneratedQuestions([]);
                        setAiPrompt("");
                      }}
                    >
                      Generate New Set
                    </button>
                  </div>

                  <div className="questions-list">
                    {generatedQuestions.map((q, index) => (
                      <div key={index} className="question-card">
                        <div className="question-card-header">
                          <span className="question-number">Q{index + 1}</span>
                          <div className="question-actions">
                            <button
                              className="edit-button"
                              onClick={() => editQuestion(index)}
                            >
                              Edit
                            </button>
                            <button
                              className="delete-button"
                              onClick={() => deleteQuestion(index)}
                            >
                              Delete
                            </button>
                          </div>
                        </div>

                        <div className="question-content">
                          <p className="question-text">{q.question}</p>
                          <div className="question-meta">
                            <span>Time: {q.time_limit}s</span>
                            <span>Correct: Option {q.correct_answer + 1}</span>
                          </div>
                          <div className="options-list">
                            {q.options.map((option, optIndex) => (
                              <div
                                key={optIndex}
                                className={`option ${
                                  optIndex === q.correct_answer ? "correct" : ""
                                }`}
                              >
                                {optIndex + 1}. {option}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="modal-footer">
              {generatedQuestions.length > 0 && (
                <button className="use-questions-button" onClick={useGeneratedQuestions}>
                  Use These Questions
                </button>
              )}
              <button className="cancel-button" onClick={closeAIModal}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Question Modal */}
      {editingQuestion && (
        <div className="modal-overlay">
          <div className="modal-content edit-modal">
            <div className="modal-header">
              <h2>Edit Question</h2>
              <button
                className="close-button"
                onClick={() => setEditingQuestion(null)}
              >
                ×
              </button>
            </div>

            <div className="modal-body">
              <div className="edit-form">
                <div className="form-group">
                  <label>Question:</label>
                  <textarea
                    value={editingQuestion.question}
                    onChange={(e) =>
                      setEditingQuestion({
                        ...editingQuestion,
                        question: e.target.value,
                      })
                    }
                    rows={3}
                  />
                </div>

                <div className="form-group">
                  <label>Time Limit (seconds):</label>
                  <input
                    type="number"
                    value={editingQuestion.time_limit}
                    onChange={(e) =>
                      setEditingQuestion({
                        ...editingQuestion,
                        time_limit: parseInt(e.target.value),
                      })
                    }
                    min={10}
                    max={120}
                  />
                </div>

                <div className="form-group">
                  <label>Options:</label>
                  {editingQuestion.options.map((option, index) => (
                    <div key={index} className="option-input-group">
                      <input
                        type="text"
                        value={option}
                        onChange={(e) => {
                          const newOptions = [...editingQuestion.options];
                          newOptions[index] = e.target.value;
                          setEditingQuestion({
                            ...editingQuestion,
                            options: newOptions,
                          });
                        }}
                        placeholder={`Option ${index + 1}`}
                      />
                      <input
                        type="radio"
                        name="correct_answer"
                        checked={editingQuestion.correct_answer === index}
                        onChange={() =>
                          setEditingQuestion({
                            ...editingQuestion,
                            correct_answer: index,
                          })
                        }
                        title="Mark as correct answer"
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button className="save-button" onClick={saveEditedQuestion}>
                Save Changes
              </button>
              <button
                className="cancel-button"
                onClick={() => setEditingQuestion(null)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default HostScreen;
