import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import InputPage from './pages/InputPage';
import LoadingPage from './pages/LoadingPage';
import ResultsPage from './pages/ResultsPage';
import BatchProgressPage from './pages/BatchProgressPage';
import './styles/main.css';

function App() {
  return (
    <Router>
      <nav className="main-nav">
        <div className="nav-container">
          <Link to="/" className="nav-logo">Regulatory Classifier</Link>
          <div className="nav-links">
            <Link to="/">Classify</Link>
          </div>
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<InputPage />} />
        <Route path="/input" element={<InputPage />} />
        <Route path="/loading" element={<LoadingPage />} />
        <Route path="/results/:documentId" element={<ResultsPage />} />
        <Route path="/batch/:batchId" element={<BatchProgressPage />} />
      </Routes>
    </Router>
  );
}

export default App;
