import React, { useEffect, useState } from "react";
import { FaBook } from "react-icons/fa";
import { FaArrowUp } from "react-icons/fa";
import "../style/documentation.css"; // custom CSS 
import MarkdownRenderer from '../Components/MarkdownRenderer.jsx'

const DocumentationLayout = ({ content }) => {
  const [showScroll, setShowScroll] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setShowScroll(window.scrollY > 300);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="container-fluid documentation-container  ">
      {/* Header */}
      <header className="doc-header mb-4 p-4 rounded-4 shadow-lg text-white">
        <div className="d-flex flex-column flex-md-row justify-content-between align-items-center">
          <div className="d-flex align-items-center gap-3">
            <div className="logo d-flex align-items-center justify-content-center rounded-3">
              {/* <i className="fas fa-book fs-3"></i> */}
              <FaBook />
            </div>
            <div>
              <h1 className="fw-bold mb-1">Agent Documentation</h1>
              <p className="mb-0 text-white-50">Complete guide to our intelligent agent system</p>
            </div>
          </div>
          <div className="search-box mt-3 mt-md-0 position-relative">
            <i className="fas fa-search search-icon"></i>
            <input
              type="text"
              className="form-control ps-5 rounded-pill"
              placeholder="Search documentation..."
            />
          </div>
        </div>
      </header>

      {/* Body */}
      <div className="row g-4">
        {/* Sidebar */}
        {/* <aside className="col-lg-3">
          <div className="sidebar p-3 rounded-4 shadow-sm bg-white">
            <h6 className="text-uppercase text-muted small mb-3">Table of Contents</h6>
            <nav className="nav flex-column">
              <a href="#introduction" className="toc-item level-1 active">Introduction</a>
              <a
               href="#getting-started"
               className="toc-item level-1">Getting Started</a>
              <a href="#installation" className="toc-item level-2">Installation</a>
              <a href="#configuration" className="toc-item level-2">Configuration</a>
              <a href="#authentication" className="toc-item level-2">Authentication</a>
              <a href="#core-concepts" className="toc-item level-1">Core Concepts</a>
              <a href="#agents" className="toc-item level-2">Agents</a>
              <a href="#workflows" className="toc-item level-2">Workflows</a>
              <a href="#knowledge-base" className="toc-item level-2">Knowledge Base</a>
              <a href="#api-reference" className="toc-item level-1">API Reference</a>
              <a href="#examples" className="toc-item level-1">Examples</a>
              <a href="#faq" className="toc-item level-1">FAQ</a>
            </nav>
          </div>
        </aside> */}

        {/* Main Content */}
        <main className="col-lg-12">
          <div className="content bg-white  rounded-4 shadow-sm">
            <MarkdownRenderer content={content} />

            {/* Feedback */}
            <div className="feedback-section mt-5 pt-4 border-top d-none">
              <h5 className="mb-3">Was this documentation helpful?</h5>
              <div className="d-flex gap-2">
                <button className="btn btn-outline-secondary">Yes</button>
                <button className="btn btn-outline-secondary">No</button>
                <button className="btn btn-outline-secondary">Need Improvement</button>
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* Scroll to Top */}
      {showScroll && (
        <button
          className="scroll-top-btn btn btn-primary rounded-circle shadow-lg"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        >
         <FaArrowUp />
        </button>
      )}
    </div>
  );
};

export default DocumentationLayout;
