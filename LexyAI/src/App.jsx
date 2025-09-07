import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import './App.css'
import './index.css';
import './style/demo.css'; 
import Home from './Components/Home';
// import MarkdownRenderer from './Components/MarkdownRenderer';
import MarkdownPage from './Components/MarkdownPage';
import Header from './Components/Header';
import Footer from './Components/Footer';


function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <div className="app-container">
        <div className="home-container">
          <Router>
            <Header />
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/markdown" element={<MarkdownPage />} />
            </Routes>
            <Footer />
          </Router>
        </div>
      </div>
    </>
  );
}

export default App
