 import { useState, useRef, useEffect } from 'react';
import React from 'react';
import bannervido from '../assets/agents-hero-video.mp4';
import imagefiles from '../assets/image-2.webp';
import bannerImage from '../assets/BannerImage.png'
import insightAgentData from '../files/insight_agen_index.md?raw'
import dashboardAgentData from '../files/dashboard_agents.md?raw'
import integrationAgentData from '../files/integration-agents-index.md?raw'
import knowledgeAgentData from '../files/knowledge-graph-agents-index.md?raw'
import mlAgentData from '../files/ml-agents-index.md?raw'
import semanticAgentData from '../files/semantic_agents-index.md?raw'
import sqlAgentData from '../files/sqlagents.md?raw'
import webAgentData from '../files/web-search-agents-index.md?raw'
import workflowAgentData from '../files/workflow-agents-index.md?raw'
import '../style/demo.css';
import '../style/home.css'; 

import { Link } from 'react-router-dom';
import ServiceCards from './ServiceCards';

const Home = () => {
    const cardsRef = useRef({});
    const containerRef = useRef(null);
    const [activeTab, setActiveTab] = useState("Insightagents");
    const [isScrolling, setIsScrolling] = useState(false);
    const [scrollProgress, setScrollProgress] = useState(0);



    const images = import.meta.glob("../assets/agents/*.{png,jpg,jpeg,webp}", {
    eager: true,
    import: "default",
  }); 
  const imageMap = {};
  for (const path in images) {
    const fileName = path.split("/").pop();
    imageMap[fileName] = images[path];
  }

    // Agent colors - light and modern palette
    const agentColors = {
        Insightagents: { bg: '#e0f2fe', text: '#0369a1' },
        Integrationagents: { bg: '#fce7f3', text: '#be185d' },
        knowledgegraphagents: { bg: '#dcfce7', text: '#15803d' },
        MLagents: { bg: '#ffedd5', text: '#ea580c' },
        websearchagents: { bg: '#e0e7ff', text: '#3730a3' },
        semanticagents: { bg: '#fef3c7', text: '#92400e' },
        workflowagents: { bg: '#ede9fe', text: '#5b21b6' },
        dashboardagents: { bg: '#d1fae5', text: '#065f46' },
        sqlagents: { bg: '#ffe4e6', text: '#be123c' }
    };

    // Agent content data
    const agentContent = {
        Insightagents: { 
            data: "insightAgentData", 
            markdownContent:insightAgentData,
            image:"insight.png",
            title: "Read 10,000 documents and extract critical insights in seconds",
            description: "Scan contracts, invoices, and reports for red flags and hidden gems. Turn documents into structured and actionable data."
        },
        Integrationagents: { 
            data: "integrationAgentData", 
             markdownContent:integrationAgentData,
             image:"integration.png",
            title: "Connect and automate across all your business applications",
            description: "Seamlessly integrate with your existing tools and platforms to create powerful automated workflows."
        },
        knowledgegraphagents: { 
            data: "knowledgeAgentData", 
             markdownContent:knowledgeAgentData,
             image:"knowledge.png",
            title: "Build intelligent knowledge networks that understand relationships",
            description: "Create dynamic knowledge graphs that connect information and provide deep insights."
        },
        MLagents: { 
            data: "mlAgentData", 
             markdownContent:mlAgentData,
             image:"mlagent.png",
            title: "Leverage machine learning to predict outcomes and optimize decisions",
            description: "Implement advanced ML models that learn from your data and improve over time."
        },
        websearchagents: { 
            data: "webAgentData", 
             markdownContent:webAgentData,
             image:"websearch.png",
            title: "Gather and analyze information from across the web automatically",
            description: "Automate web research and data collection with intelligent agents that understand context."
        },
        semanticagents: { 
            data: "semanticAgentData", 
             markdownContent:semanticAgentData,
             image:"semantic.png",
            title: "Understand context and meaning in your data and content",
            description: "Go beyond keywords to truly understand the meaning and relationships in your information."
        },
        workflowagents: { 
            data: "workflowAgentData", 
             markdownContent:workflowAgentData,
             image:"workflow.png",
            title: "Automate complex business processes end-to-end",
            description: "Design and implement sophisticated workflows that handle even the most complex tasks."
        },
        dashboardagents: { 
            data: "dashboardAgentData", 
             markdownContent:dashboardAgentData,
             image:"dashboard.png",
            title: "Create intelligent dashboards that update and analyze themselves",
            description: "Build dynamic dashboards that not only display data but also provide insights and recommendations."
        },
        sqlagents: { 
            data: "sqlAgentData", 
             markdownContent:sqlAgentData,
             image:"sql.png",
            title: "Query and analyze databases using natural language",
            description: "Transform how you interact with databases by using conversational language instead of complex queries."
        }
    };

    // Scroll to a specific card
    const scrollToCard = (tab) => {
        if (isScrolling || activeTab === tab) return;
        
        setIsScrolling(true);
        setActiveTab(tab);
        
        const cardElement = cardsRef.current[tab];
        const containerElement = containerRef.current;
        
        if (cardElement && containerElement) {
            const cardTop = cardElement.offsetTop;
            
            // Add a slight bounce effect at the end of scrolling
            containerElement.scrollTo({
                top: cardTop,
                behavior: 'smooth'
            });
            
            // Add a highlight animation to the card
            cardElement.classList.add('highlight');
            setTimeout(() => {
                cardElement.classList.remove('highlight');
            }, 1000);
        }
        
        // Reset scrolling flag after animation completes
        setTimeout(() => setIsScrolling(false), 800);
    };

    // Handle scroll events to update active tab
    useEffect(() => {
        const handleScroll = () => {
            if (isScrolling) return;
            
            const containerElement = containerRef.current;
            if (!containerElement) return;
            
            const scrollPosition = containerElement.scrollTop;
            const maxScroll = containerElement.scrollHeight - containerElement.clientHeight;
            const scrollPercent = (scrollPosition / maxScroll) * 100;
            setScrollProgress(scrollPercent);
            
            const cardElements = Object.values(cardsRef.current);
            
            let activeCard = "Insightagents";
            let minDistance = Infinity;
            
            cardElements.forEach(card => {
                if (!card) return;
                
                const cardTop = card.offsetTop;
                const cardHeight = card.offsetHeight;
                const distance = Math.abs(scrollPosition - cardTop + cardHeight/2);
                
                if (distance < minDistance) {
                    minDistance = distance;
                    activeCard = card.getAttribute('data-tab');
                }
            });
            
            if (activeTab !== activeCard) {
                setActiveTab(activeCard);
            }
        };

        const containerElement = containerRef.current;
        if (containerElement) {
            containerElement.addEventListener('scroll', handleScroll);
            return () => containerElement.removeEventListener('scroll', handleScroll);
        }
    }, [isScrolling, activeTab]);

    return (
      <>
        
        <section id="hastag" className="home-container">
          {/* Hero Section */}
          <div className="hero-section">
            <div className="container-fluid">
              <div className="hero-content">
                <h1 className="hero-title animate-fade-in">
                  The instant way to put agents to work
                </h1>
                <div className="hero-description-container">
                  <p className="hero-description">
                    Turn manual to magical with agents who understand your
                    business, make informed decisions, and get work done at
                    scale in a fraction of the time.
                  </p>
                  <div className="hero-button-container">
                    <button className="cta-button animate-pulse">
                      Try it now
                      <span className="button-icon">→</span>
                    </button>
                  </div>
                </div>
              </div>

              <div className="video-container py-3">
                {/* <video className="hero-video" autoPlay muted loop controls>
                  <source src={bannervido} type="video/mp4" />
                </video> */}
                <img src={bannerImage} alt="banner-image" className='w-100'  />
              </div>
            </div>
          </div>

          {/* Agents Section */}
          <div className="agents-section">
            <div className="container-fluid">
              <h2 className="section-title">
                Agents that scale across every workflow
              </h2>

              <div className="agents-container">
                {/* Left Tabs - Sticky on scroll */}
                <div className="agents-nav">
                  {Object.entries({
                    Insightagents: "Insight agents",
                    Integrationagents: "Integration agents",
                    knowledgegraphagents: "Knowledge graph agents",
                    MLagents: "ML agents",
                    websearchagents: "Web search agents",
                    semanticagents: "Semantic agents",
                    workflowagents: "Workflow agents",
                    dashboardagents: "Dashboard agents",
                    sqlagents: "SQL agents",
                  }).map(([key, label]) => (
                    <button
                      key={key}
                      className={`nav-item ${
                        activeTab === key ? "active" : ""
                      }`}
                      onClick={() => scrollToCard(key)}
                      style={{
                        color:
                          activeTab === key ? agentColors[key].text : "#333",
                        borderLeft: `4px solid ${
                          activeTab === key
                            ? agentColors[key].text
                            : "transparent"
                        }`,
                      }}
                    >
                      <span className="nav-label">{label}</span>
                      <span
                        className="nav-indicator"
                        style={{
                          backgroundColor: agentColors[key].text,
                          transform:
                            activeTab === key ? "scaleX(1)" : "scaleX(0)",
                        }}
                      ></span>
                    </button>
                  ))}
                </div>

                {/* Right Content - Scrollable Cards Container */}
                <div className="agents-content-wrapper">
                  <div className="agents-content" ref={containerRef}>
                    {Object.entries(agentContent).map(([key, value]) => (
                      <div
                        key={key}
                        ref={(el) => (cardsRef.current[key] = el)}
                        data-tab={key}
                        className="agent-card"
                        style={{ backgroundColor: agentColors[key].bg }}
                      >
                        <div className="card-content">
                          <div className="text-content">
                            <h4 style={{ color: agentColors[key].text }}>
                              {value.title}
                            </h4>
                            <p>{value.description}</p>
                          </div>
                          <div className="link-container">
                            <Link
                              to="/markdown"
                              className="learn-link"
                              state={{ content: value.markdownContent }}
                              style={{ color: agentColors[key].text }}
                            >
                              Learn more
                              <span className="link-arrow">→</span>
                            </Link>
                          </div>
                        </div>
                        <img
                          className="card-image"
                          src={imageMap[value.image]}
                          alt="service"
                        />
                      </div>
                    ))}
                  </div>

                  {/* Custom scroll indicator */}
                  <div className="scroll-indicator">
                    <div className="scroll-track">
                      <div
                        className="scroll-progress"
                        style={{ width: `${scrollProgress}%` }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
        <ServiceCards />
      </>
    );
}

export default Home