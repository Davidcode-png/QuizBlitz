import logo from "./logo.svg";
import "./App.css";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import JoinScreen from "./joinScreen";
import PlayerScreen from "./playerScreen";
import HostScreen from "./hostScreen";

function App() {
  return (
    <Router>
      <div className="app-container">
        <h1>QuizBlitz</h1>
        <Routes>
          <Route path="/" element={<JoinScreen />} />
          <Route path="/player/:gamePin/:nickname" element={<PlayerScreen />} />
          <Route path="/host" element={<HostScreen />} />
          <Route path="/host/:gamePin" element={<HostScreen />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
