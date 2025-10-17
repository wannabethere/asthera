//  import { useState, useRef, useEffect } from 'react';
// import React from 'react';
// import bannervido from '../assets/agents-hero-video.mp4';
// import imagefiles from '../assets/image-2.webp';
// import bannerImage from '../assets/BannerImage.png'
// import insightAgentData from '../files/insight_agen_index.md?raw'
// import dashboardAgentData from '../files/dashboard_agents.md?raw'
// import integrationAgentData from '../files/integration-agents-index.md?raw'
// import knowledgeAgentData from '../files/knowledge-graph-agents-index.md?raw'
// import mlAgentData from '../files/ml-agents-index.md?raw'
// import semanticAgentData from '../files/semantic_agents-index.md?raw'
// import sqlAgentData from '../files/sqlagents.md?raw'
// import webAgentData from '../files/web-search-agents-index.md?raw'
// import workflowAgentData from '../files/workflow-agents-index.md?raw'
// import '../style/demo.css';
// import '../style/home.css'; 

// import { Link } from 'react-router-dom';
// import ServiceCards from './ServiceCards';

// const Platform = () => {
//     const cardsRef = useRef({});
//     const containerRef = useRef(null);
//     const [activeTab, setActiveTab] = useState("Insightagents");
//     const [isScrolling, setIsScrolling] = useState(false);
//     const [scrollProgress, setScrollProgress] = useState(0);



//     const images = import.meta.glob("../assets/agents/*.{png,jpg,jpeg,webp}", {
//     eager: true,
//     import: "default",
//   }); 
//   const imageMap = {};
//   for (const path in images) {
//     const fileName = path.split("/").pop();
//     imageMap[fileName] = images[path];
//   }

//     // Agent colors - light and modern palette
//     const agentColors = {
//         Insightagents: { bg: '#e0f2fe', text: '#0369a1' },
//         Integrationagents: { bg: '#fce7f3', text: '#be185d' },
//         knowledgegraphagents: { bg: '#dcfce7', text: '#15803d' },
//         MLagents: { bg: '#ffedd5', text: '#ea580c' },
//         websearchagents: { bg: '#e0e7ff', text: '#3730a3' },
//         semanticagents: { bg: '#fef3c7', text: '#92400e' },
//         workflowagents: { bg: '#ede9fe', text: '#5b21b6' },
//         dashboardagents: { bg: '#d1fae5', text: '#065f46' },
//         sqlagents: { bg: '#ffe4e6', text: '#be123c' }
//     };

//     // Agent content data
//     const agentContent = {
//         Insightagents: { 
//             data: "insightAgentData", 
//             markdownContent:insightAgentData,
//             image:"insight.png",
//             title: "Read 10,000 documents and extract critical insights in seconds",
//             description: "Scan contracts, invoices, and reports for red flags and hidden gems. Turn documents into structured and actionable data."
//         },
//         Integrationagents: { 
//             data: "integrationAgentData", 
//              markdownContent:integrationAgentData,
//              image:"integration.png",
//             title: "Connect and automate across all your business applications",
//             description: "Seamlessly integrate with your existing tools and platforms to create powerful automated workflows."
//         },
//         knowledgegraphagents: { 
//             data: "knowledgeAgentData", 
//              markdownContent:knowledgeAgentData,
//              image:"knowledge.png",
//             title: "Build intelligent knowledge networks that understand relationships",
//             description: "Create dynamic knowledge graphs that connect information and provide deep insights."
//         },
//         MLagents: { 
//             data: "mlAgentData", 
//              markdownContent:mlAgentData,
//              image:"mlagent.png",
//             title: "Leverage machine learning to predict outcomes and optimize decisions",
//             description: "Implement advanced ML models that learn from your data and improve over time."
//         },
//         websearchagents: { 
//             data: "webAgentData", 
//              markdownContent:webAgentData,
//              image:"websearch.png",
//             title: "Gather and analyze information from across the web automatically",
//             description: "Automate web research and data collection with intelligent agents that understand context."
//         },
//         semanticagents: { 
//             data: "semanticAgentData", 
//              markdownContent:semanticAgentData,
//              image:"semantic.png",
//             title: "Understand context and meaning in your data and content",
//             description: "Go beyond keywords to truly understand the meaning and relationships in your information."
//         },
//         workflowagents: { 
//             data: "workflowAgentData", 
//              markdownContent:workflowAgentData,
//              image:"workflow.png",
//             title: "Automate complex business processes end-to-end",
//             description: "Design and implement sophisticated workflows that handle even the most complex tasks."
//         },
//         dashboardagents: { 
//             data: "dashboardAgentData", 
//              markdownContent:dashboardAgentData,
//              image:"dashboard.png",
//             title: "Create intelligent dashboards that update and analyze themselves",
//             description: "Build dynamic dashboards that not only display data but also provide insights and recommendations."
//         },
//         sqlagents: { 
//             data: "sqlAgentData", 
//              markdownContent:sqlAgentData,
//              image:"sql.png",
//             title: "Query and analyze databases using natural language",
//             description: "Transform how you interact with databases by using conversational language instead of complex queries."
//         }
//     };

//     // Scroll to a specific card
//     const scrollToCard = (tab) => {
//         if (isScrolling || activeTab === tab) return;
        
//         setIsScrolling(true);
//         setActiveTab(tab);
        
//         const cardElement = cardsRef.current[tab];
//         const containerElement = containerRef.current;
        
//         if (cardElement && containerElement) {
//             const cardTop = cardElement.offsetTop;
            
//             // Add a slight bounce effect at the end of scrolling
//             containerElement.scrollTo({
//                 top: cardTop,
//                 behavior: 'smooth'
//             });
            
//             // Add a highlight animation to the card
//             cardElement.classList.add('highlight');
//             setTimeout(() => {
//                 cardElement.classList.remove('highlight');
//             }, 1000);
//         }
        
//         // Reset scrolling flag after animation completes
//         setTimeout(() => setIsScrolling(false), 800);
//     };

//     // Handle scroll events to update active tab
//     useEffect(() => {
//         const handleScroll = () => {
//             if (isScrolling) return;
            
//             const containerElement = containerRef.current;
//             if (!containerElement) return;
            
//             const scrollPosition = containerElement.scrollTop;
//             const maxScroll = containerElement.scrollHeight - containerElement.clientHeight;
//             const scrollPercent = (scrollPosition / maxScroll) * 100;
//             setScrollProgress(scrollPercent);
            
//             const cardElements = Object.values(cardsRef.current);
            
//             let activeCard = "Insightagents";
//             let minDistance = Infinity;
            
//             cardElements.forEach(card => {
//                 if (!card) return;
                
//                 const cardTop = card.offsetTop;
//                 const cardHeight = card.offsetHeight;
//                 const distance = Math.abs(scrollPosition - cardTop + cardHeight/2);
                
//                 if (distance < minDistance) {
//                     minDistance = distance;
//                     activeCard = card.getAttribute('data-tab');
//                 }
//             });
            
//             if (activeTab !== activeCard) {
//                 setActiveTab(activeCard);
//             }
//         };

//         const containerElement = containerRef.current;
//         if (containerElement) {
//             containerElement.addEventListener('scroll', handleScroll);
//             return () => containerElement.removeEventListener('scroll', handleScroll);
//         }
//     }, [isScrolling, activeTab]);

//     return (
//       <>
        
//         <section id="hastag" className="home-container">
//           {/* Hero Section */}
//           <div className="hero-section">
//             <div className="container-fluid">
//               <div className="hero-content">
//                 <h1 className="hero-title animate-fade-in">
//                   The instant way to put agents to work
//                 </h1>
//                 <div className="hero-description-container">
//                   <p className="hero-description">
//                     Turn manual to magical with agents who understand your
//                     business, make informed decisions, and get work done at
//                     scale in a fraction of the time.
//                   </p>
//                   <div className="hero-button-container">
//                     <button className="cta-button animate-pulse">
//                       Try it now
//                       <span className="button-icon">→</span>
//                     </button>
//                   </div>
//                 </div>
//               </div>

//               <div className="video-container py-3">
//                 {/* <video className="hero-video" autoPlay muted loop controls>
//                   <source src={bannervido} type="video/mp4" />
//                 </video> */}
//                 <img src={bannerImage} alt="banner-image" className='w-100'  />
//               </div>
//             </div>
//           </div>

//           {/* Agents Section */}
//           <div className="agents-section">
//             <div className="container-fluid">
//               <h2 className="section-title">
//                 Agents that scale across every workflow
//               </h2>

//               <div className="agents-container">
//                 {/* Left Tabs - Sticky on scroll */}
//                 <div className="agents-nav">
//                   {Object.entries({
//                     Insightagents: "Insight agents",
//                     Integrationagents: "Integration agents",
//                     knowledgegraphagents: "Knowledge graph agents",
//                     MLagents: "ML agents",
//                     websearchagents: "Web search agents",
//                     semanticagents: "Semantic agents",
//                     workflowagents: "Workflow agents",
//                     dashboardagents: "Dashboard agents",
//                     sqlagents: "SQL agents",
//                   }).map(([key, label]) => (
//                     <button
//                       key={key}
//                       className={`nav-item ${
//                         activeTab === key ? "active" : ""
//                       }`}
//                       onClick={() => scrollToCard(key)}
//                       style={{
//                         color:
//                           activeTab === key ? agentColors[key].text : "#333",
//                         borderLeft: `4px solid ${
//                           activeTab === key
//                             ? agentColors[key].text
//                             : "transparent"
//                         }`,
//                       }}
//                     >
//                       <span className="nav-label">{label}</span>
//                       <span
//                         className="nav-indicator"
//                         style={{
//                           backgroundColor: agentColors[key].text,
//                           transform:
//                             activeTab === key ? "scaleX(1)" : "scaleX(0)",
//                         }}
//                       ></span>
//                     </button>
//                   ))}
//                 </div>

//                 {/* Right Content - Scrollable Cards Container */}
//                 <div className="agents-content-wrapper">
//                   <div className="agents-content" ref={containerRef}>
//                     {Object.entries(agentContent).map(([key, value]) => (
//                       <div
//                         key={key}
//                         ref={(el) => (cardsRef.current[key] = el)}
//                         data-tab={key}
//                         className="agent-card"
//                         style={{ backgroundColor: agentColors[key].bg }}
//                       >
//                         <div className="card-content">
//                           <div className="text-content">
//                             <h4 style={{ color: agentColors[key].text }}>
//                               {value.title}
//                             </h4>
//                             <p>{value.description}</p>
//                           </div>
//                           <div className="link-container">
//                             <Link
//                               to="/markdown"
//                               className="learn-link"
//                               state={{ content: value.markdownContent }}
//                               style={{ color: agentColors[key].text }}
//                             >
//                               Learn more
//                               <span className="link-arrow">→</span>
//                             </Link>
//                           </div>
//                         </div>
//                         <img
//                           className="card-image"
//                           src={imageMap[value.image]}
//                           alt="service"
//                         />
//                       </div>
//                     ))}
//                   </div>

//                   {/* Custom scroll indicator */}
//                   <div className="scroll-indicator">
//                     <div className="scroll-track">
//                       <div
//                         className="scroll-progress"
//                         style={{ width: `${scrollProgress}%` }}
//                       ></div>
//                     </div>
//                   </div>
//                 </div>
//               </div>
//             </div>
//           </div>
//         </section>
//         {/* <ServiceCards /> */}
//       </>
//     );
// }

// export default Platform


import { useState, useRef, useEffect } from "react";
import React from "react";
import bannervido from "../assets/agents-hero-video.mp4";
import imagefiles from "../assets/image-2.webp";
import bannerImage from "../assets/BannerImage.png";

import insightAgentData from "../files/insight_agen_index.md?raw";
import dashboardAgentData from "../files/dashboard_agents.md?raw";
import integrationAgentData from "../files/integration-agents-index.md?raw";
import knowledgeAgentData from "../files/knowledge-graph-agents-index.md?raw";
import mlAgentData from "../files/ml-agents-index.md?raw";
import semanticAgentData from "../files/semantic_agents-index.md?raw";
import sqlAgentData from "../files/sqlagents.md?raw";
import webAgentData from "../files/web-search-agents-index.md?raw";
import workflowAgentData from "../files/workflow-agents-index.md?raw";

import "../style/demo.css";
import "../style/home.css";

import { Link } from "react-router-dom";
// import ServiceCards from './ServiceCards'; // keep commented if unused

const Platform = () => {
  const cardsRef = useRef({});
  const containerRef = useRef(null);
  const [activeTab, setActiveTab] = useState("semanticagents");
  const [isScrolling, setIsScrolling] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [expandedGroups, setExpandedGroups] = useState({});

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
    Insightagents: { bg: "#e0f2fe", text: "#0369a1" },
    Integrationagents: { bg: "#fce7f3", text: "#be185d" },
    knowledgegraphagents: { bg: "#dcfce7", text: "#15803d" },
    MLagents: { bg: "#ffedd5", text: "#ea580c" },
    websearchagents: { bg: "#e0e7ff", text: "#3730a3" },
    semanticagents: { bg: "#fef3c7", text: "#92400e" },
    workflowagents: { bg: "#ede9fe", text: "#5b21b6" },
    dashboardagents: { bg: "#d1fae5", text: "#065f46" },
    sqlagents: { bg: "#ffe4e6", text: "#be123c" },
  };

  // Agent content data (unchanged)
  const agentContent = {
    Insightagents: {
      data: "insightAgentData",
      markdownContent: insightAgentData,
      image: "insight.png",
      title: "Read 10,000 documents and extract critical insights in seconds",
      description:
        "Scan contracts, invoices, and reports for red flags and hidden gems. Turn documents into structured and actionable data.",
    },
    Integrationagents: {
      data: "integrationAgentData",
      markdownContent: integrationAgentData,
      image: "integration.png",
      title: "Connect and automate across all your business applications",
      description:
        "Seamlessly integrate with your existing tools and platforms to create powerful automated workflows.",
    },
    knowledgegraphagents: {
      data: "knowledgeAgentData",
      markdownContent: knowledgeAgentData,
      image: "knowledge.png",
      title: "Build intelligent knowledge networks that understand relationships",
      description:
        "Create dynamic knowledge graphs that connect information and provide deep insights.",
    },
    MLagents: {
      data: "mlAgentData",
      markdownContent: mlAgentData,
      image: "mlagent.png",
      title: "Leverage machine learning to predict outcomes and optimize decisions",
      description:
        "Implement advanced ML models that learn from your data and improve over time.",
    },
    websearchagents: {
      data: "webAgentData",
      markdownContent: webAgentData,
      image: "websearch.png",
      title: "Gather and analyze information from across the web automatically",
      description:
        "Automate web research and data collection with intelligent agents that understand context.",
    },
    semanticagents: {
      data: "semanticAgentData",
      markdownContent: semanticAgentData,
      image: "semantic.png",
      title: "Understand context and meaning in your data and content",
      description:
        "Go beyond keywords to truly understand the meaning and relationships in your information.",
    },
    workflowagents: {
      data: "workflowAgentData",
      markdownContent: workflowAgentData,
      image: "workflow.png",
      title: "Automate complex business processes end-to-end",
      description:
        "Design and implement sophisticated workflows that handle even the most complex tasks.",
    },
    dashboardagents: {
      data: "dashboardAgentData",
      markdownContent: dashboardAgentData,
      image: "dashboard.png",
      title: "Create intelligent dashboards that update and analyze themselves",
      description:
        "Build dynamic dashboards that not only display data but also provide insights and recommendations.",
    },
    sqlagents: {
      data: "sqlAgentData",
      markdownContent: sqlAgentData,
      image: "sql.png",
      title: "Query and analyze databases using natural language",
      description:
        "Transform how you interact with databases by using conversational language instead of complex queries.",
    },
  };

  // Helper: create a safe slug from a label for internal active keys when there's no mapTo
  const slugify = (s) =>
    String(s)
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "-")
      .replace(/[^a-z0-9\-]/g, "");

  // Hierarchy definition (groups -> children)
  // *Important:* children may include an optional `mapTo` that points to an agentContent key.
  // If `mapTo` exists and the key is present in agentContent, clicking will scroll to that card.
  // If `mapTo` is absent (new item) we will NOT redirect to any existing agent — only set left-nav active state.
  const hierarchicalNav = [
    {
      label: "Knowledge",
      children: [
        { label: "Semantic", mapTo: "semanticagents" }, // existing -> will scroll
        { label: "Web search", mapTo: "websearchagents" }, // existing -> will scroll
        { label: "Knowledge",  mapTo: "knowledgegraphagents" }, // NEW -> no redirect
      ],
    },
    {
      label: "Data Insights",
      children: [
        { label: "SQL", mapTo: "sqlagents" }, // existing -> will scroll
        { label: "Strategic Insights" , mapTo: "Insightagents" }, // NEW -> no redirect
        { label: "Classical ML Insights",  mapTo: "MLagents" }, // NEW -> no redirect
      ],
    },
    {
      label: "Workflows",
      children: [
        { label: "Dashboard", mapTo: "dashboardagents" }, // existing -> will scroll
        { label: "Reports" }, // NEW -> no redirect
        { label: "Alerts",   }, //  NEW -> no redirect
        { label: "Embedding" }, // NEW -> no redirect
        { label: "Automations", mapTo: "workflowagents" }, // maps to workflowagents
      ],
    },
    {
      label: "Data Pipelines",
      children: [
        { label: "Feature Engineering" }, // NEW -> no redirect
        { label: "ETL Agent" }, // NEW -> no redirect
      ],
    },
  ];

  // Toggle group expanded/collapsed (useful for mobile)
  const toggleGroup = (idx) => {
    setExpandedGroups((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  // Scroll to a specific card (unchanged)
  const scrollToCard = (tab) => {
    if (isScrolling || activeTab === tab) return;

    setIsScrolling(true);
    setActiveTab(tab);

    const cardElement = cardsRef.current[tab];
    const containerElement = containerRef.current;

    if (cardElement && containerElement) {
      const cardTop = cardElement.offsetTop;

      containerElement.scrollTo({
        top: cardTop,
        behavior: "smooth",
      });

      // highlight animation
      cardElement.classList.add("highlight");
      setTimeout(() => {
        cardElement.classList.remove("highlight");
      }, 1000);
    }

    setTimeout(() => setIsScrolling(false), 800);
  };

  // Handle scroll events to update active tab & progress (unchanged)
  useEffect(() => {
    const handleScroll = () => {
      if (isScrolling) return;

      const containerElement = containerRef.current;
      if (!containerElement) return;

      const scrollPosition = containerElement.scrollTop;
      const maxScroll = containerElement.scrollHeight - containerElement.clientHeight;
      const scrollPercent = maxScroll > 0 ? (scrollPosition / maxScroll) * 100 : 0;
      setScrollProgress(scrollPercent);

      const cardElements = Object.values(cardsRef.current);

      let activeCard = "semanticagents";
      let minDistance = Infinity;

      cardElements.forEach((card) => {
        if (!card) return;
        const cardTop = card.offsetTop;
        const cardHeight = card.offsetHeight;
        const distance = Math.abs(scrollPosition - cardTop + cardHeight / 2);
        if (distance < minDistance) {
          minDistance = distance;
          activeCard = card.getAttribute("data-tab");
        }
      });

      if (activeTab !== activeCard) {
        setActiveTab(activeCard);
      }
    };

    const containerElement = containerRef.current;
    if (containerElement) {
      containerElement.addEventListener("scroll", handleScroll, { passive: true });
      return () => containerElement.removeEventListener("scroll", handleScroll);
    }
  }, [isScrolling, activeTab]);

  // Ensure groups are expanded on larger screens by default (unchanged)
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 992px)");
    if (mq.matches) {
      const map = {};
      hierarchicalNav.forEach((_, i) => (map[i] = true));
      setExpandedGroups(map);
    } else {
      setExpandedGroups({});
    }
  }, []);

  // helper to handle child click:
  // - if child.mapTo exists and agentContent has that key -> scrollToCard(mapTo)
  // - else -> set activeTab to slug (no redirection to right section)
  const handleChildClick = (child) => {
    if (child.mapTo && agentContent[child.mapTo]) {
      scrollToCard(child.mapTo);
    } else {
      // mark the left-nav item active but do NOT change right content
      const key = slugify(child.label);
      setActiveTab(key);
    }
  };

  return (
    <>
      <section id="hastag" className="home-container">
        {/* Hero Section (unchanged) */}
        <div className="hero-section bg-dark text-light">
          <div className="container-fluid">
            <div className="hero-content">
              <h1 className="hero-title animate-fade-in display-3 fw-bold">The instant way to put agents to work</h1>
              <div className="hero-description-container">
                <p className="hero-description text-light">
                  Turn manual to magical with agents who understand your business, make informed decisions, and get work
                  done at scale in a fraction of the time.
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
              <img src={bannerImage} alt="banner-image" className="w-100" />
            </div>
          </div>
        </div>

        {/* Agents Section (right content left unchanged) */}
        <div className="agents-section">
          <div className="container-fluid">
            <h2 className="section-title">Agents that scale across every workflow</h2>

            <div className="agents-container" style={{ display: "flex", gap: "24px", alignItems: "flex-start" }}>
              {/* LEFT: Hierarchical nav (UPDATED) */}
              <div className="agents-nav" style={{ width: 280, position: "sticky", top: 100, alignSelf: "flex-start" }}>
                {hierarchicalNav.map((group, gIdx) => {
                  const isExpanded = expandedGroups[gIdx] ?? true;
                  return (
                    <div key={group.label} className="nav-group" style={{ marginBottom: 10 }}>
                      <button
                        type="button"
                        className="group-label"
                        onClick={() => toggleGroup(gIdx)}
                        aria-expanded={isExpanded}
                        style={{
                          width: "100%",
                          textAlign: "left",
                          fontWeight: 700,
                          background: "transparent",
                          border: "none",
                          padding: "8px 10px",
                          color: "#111",
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          cursor: "pointer",
                        }}
                      >
                        <span>{group.label}</span>
                        <span
                          className={`chev ${isExpanded ? "open" : ""}`}
                          style={{
                            width: 10,
                            height: 10,
                            display: "inline-block",
                            borderRight: "2px solid #666",
                            borderBottom: "2px solid #666",
                            transform: isExpanded ? "rotate(45deg)" : "rotate(-45deg)",
                            transition: "transform .18s",
                          }}
                        />
                      </button>

                      <div
                        className={`group-children ${isExpanded ? "expanded" : "collapsed"}`}
                        style={{ paddingLeft: 8, marginTop: 6 }}
                      >
                        {group.children.map((child) => {
                          // determine indicator color:
                          const mappedKey = child.mapTo;
                          const color = mappedKey && agentColors[mappedKey] ? agentColors[mappedKey].text : "#333";
                          const internalKey = mappedKey ? mappedKey : slugify(child.label); // used for active highlight
                          const isActive = activeTab === internalKey;

                          return (
                            <button
                              key={child.label}
                              onClick={() => handleChildClick(child)}
                              className={`nav-item nested ${isActive ? "active" : ""}`}
                              style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                width: "100%",
                                background: "transparent",
                                border: "none",
                                padding: "8px 10px",
                                textAlign: "left",
                                cursor: "pointer",
                                marginBottom: 6,
                                borderRadius: 6,
                                color: isActive ? color : "#333",
                                borderLeft: `3px solid ${isActive ? color : "transparent"}`,
                              }}
                            >
                              <span className="nav-label" style={{ flex: 1 }}>
                                {child.label}
                              </span>
                              <span
                                className="nav-indicator"
                                style={{
                                //   width: 24,
                                //   height: 6,
                                  backgroundColor: color,
                                  transform: isActive ? "scaleX(1)" : "scaleX(0)",
                                  transition: "transform .18s",
                                  borderRadius: 3,
                                }}
                              />
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* RIGHT: scrollable cards container (exactly as before — not edited) */}
              <div className="agents-content-wrapper" style={{ flex: 1, position: "relative" }}>
                <div
                  className="agents-content"
                  ref={containerRef}
                  style={{ maxHeight: 640, overflowY: "auto" }}
                >
                  {Object.entries(agentContent).map(([key, value]) => (
                    <div
                      key={key}
                      ref={(el) => (cardsRef.current[key] = el)}
                      data-tab={key}
                      className="agent-card"
                      style={{
                        backgroundColor: agentColors[key]?.bg || "#fff",
                        // borderRadius: 12,
                        padding: 20,
                        display: "flex",
                        alignItems: "center",
                        gap: 20,
                        // marginBottom: 20,
                      }}
                    >
                      <div className="card-content"  >
                        <div className="text-content">
                          <h4 style={{ color: agentColors[key]?.text || "#000", margin: 0 }}>{value.title}</h4>
                          <p style={{ marginTop: 8 }}>{value.description}</p>
                        </div>
                        <div className="link-container" style={{ marginTop: 12 }}>
                          <Link
                            to="/markdown"
                            className="learn-link"
                            state={{ content: value.markdownContent }}
                            style={{ color: agentColors[key]?.text || "#000", fontWeight: 600, textDecoration: "none" }}
                          >
                            Learn more <span className="link-arrow">→</span>
                          </Link>
                        </div>
                      </div>

                        <img
                          className="card-image"
                          src={imageMap[value.image] ?? "/useCase/default.webp"}
                          alt={value.title}
                          style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                        />
                    </div>
                  ))}
                </div>

                {/* Custom scroll indicator (unchanged) */}
                <div
                  className="scroll-indicator d-none"
                  style={{
                    position: "absolute",
                    right: 0,
                    top: 12,
                    width: 8,
                    bottom: 12,
                    display: "flex",
                    alignItems: "flex-start",
                    padding: 4,
                  }}
                >
                  <div
                    className="scroll-track"
                    style={{
                      width: "100%",
                      height: "100%",
                      background: "rgba(0,0,0,0.06)",
                      borderRadius: 8,
                      position: "relative",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      className="scroll-progress"
                      style={{
                        width: "100%",
                        height: `${Math.max(6, Math.min(100, scrollProgress))}%`,
                        background: "linear-gradient(180deg, rgba(0,0,0,0.12), rgba(0,0,0,0.24))",
                        position: "absolute",
                        bottom: 0,
                        left: 0,
                        transition: "height 120ms linear",
                        borderRadius: 6,
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
};

export default Platform;
