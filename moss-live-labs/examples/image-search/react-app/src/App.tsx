import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import ImageSearchPage from "./pages/ItemsPage";
import ImageDetailPage from "./pages/ItemDetailPage";
import "./App.css";
import Favicon from "./components/Favicon";

function App() {
  return (
    <Router>
      <div className="app-container">
        <Favicon />
        <main>
          <Routes>
            <Route path="/" element={<ImageSearchPage />} />
            <Route path="/image/:id" element={<ImageDetailPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
