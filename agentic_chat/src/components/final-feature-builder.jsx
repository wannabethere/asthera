import React, { useState } from 'react';
import { 
  Bot, Send, ThumbsUp, ThumbsDown, Copy, MessageSquare, Network,
  Database, TrendingUp, FileText, Shield, BarChart3, Sparkles,
  Eye, Save, PlayCircle, Plus, Zap, Bell, Layout, Users, X, 
  CheckCircle, Circle, BookOpen, ZoomIn, ZoomOut
} from 'lucide-react';

const FinalFeatureBuilder = () => {
  // State management
  const [activeTab, setActiveTab] = useState('conversation');
  const [selectedMessageKnowledge, setSelectedMessageKnowledge] = useState(null);
  const [currentStep, setCurrentStep] = useState(2);
  const [completionPercentage, setCompletionPercentage] = useState(40);
  const [queryInput, setQueryInput] = useState('');
  const [zoom, setZoom] = useState(1);

  // Workflow steps
  const workflowSteps = [
    { id: 1, name: 'Select Data', status: 'completed' },
    { id: 2, name: 'Build Features', status: 'current' },
    { id: 3, name: 'Configure Risk', status: 'pending' },
    { id: 4, name: 'Preview Results', status: 'pending' },
    { id: 5, name: 'Save Pipeline', status: 'pending' }
  ];

  // Knowledge graph data for each message
  const knowledgeGraphs = {
    message1: {
      title: "Compliance Dataset Analysis",
      mainInsight: "This dataset contains transactional data related to compliance controls, including details about frameworks, status, scores, and audit history. The AI identified this as a compliance dataset based on column names and data patterns.",
      nodes: [
        {
          id: 1,
          type: "user-action",
          label: "User uploaded compliance_controls.csv",
          position: { x: 100, y: 50 }
        },
        {
          id: 2,
          type: "analysis",
          label: "Dataset schema analysis",
          details: "Identified 23 columns including control_id, framework, domain, status, score, implementation_date, owner, description, evidence_required, last_audit, automation_level, criticality",
          position: { x: 300, y: 50 }
        },
        {
          id: 3,
          type: "insight",
          label: "Compliance dataset detected",
          details: "Based on column names and data patterns, this appears to be a compliance controls dataset commonly used for SOC2, ISO27001, or similar frameworks",
          position: { x: 500, y: 50 }
        },
        {
          id: 4,
          type: "recommendation",
          label: "Suggested 3 feature categories",
          details: "Compliance Story (priority, maturity), Risk Assessment (likelihood, impact), Custom transformations",
          position: { x: 300, y: 200 }
        },
        {
          id: 5,
          type: "context",
          label: "Industry patterns applied",
          details: "Compliance datasets typically benefit from: priority classification, maturity scoring, risk quantification (FAIR methodology), framework alignment checks",
          position: { x: 500, y: 200 }
        }
      ],
      connections: [
        { from: 1, to: 2, label: "triggers" },
        { from: 2, to: 3, label: "identifies" },
        { from: 3, to: 4, label: "leads to" },
        { from: 4, to: 5, label: "based on" }
      ],
      relatedInsights: [
        {
          title: "Column Distribution",
          description: "23 columns detected: 15 text-based, 8 numeric. Key columns for feature engineering: score, status, implementation_date, criticality",
          icon: Database
        },
        {
          title: "Framework Coverage",
          description: "Dataset likely covers multiple compliance frameworks (SOC2, ISO27001, NIST). Framework column suggests multi-framework tracking.",
          icon: Shield
        },
        {
          title: "Risk Opportunities",
          description: "Presence of criticality and automation_level columns enables sophisticated risk scoring using likelihood × impact methodology",
          icon: TrendingUp
        }
      ],
      statistics: {
        "Total Rows": "1,247",
        "Total Columns": "23",
        "Detected Type": "Compliance Controls",
        "Confidence": "95%"
      }
    }
  };

  // Messages data
  const messages = [
    {
      id: 'message1',
      role: 'assistant',
      content: `👋 Hi! I've loaded **compliance_controls.csv** with 1247 rows and 23 columns.\n\nI can see this is a compliance dataset. I can help you build:\n\n**Compliance Story Features** - Priority, maturity, framework alignment\n\n**Risk Assessment Features** - Likelihood, impact, risk scores\n\n**Custom Features** - Any other data transformations\n\nWhat features would you like to create?`,
      suggestions: [
        "Build compliance story features",
        "Add risk scoring features",
        "Show me the data columns"
      ],
      hasKnowledge: true
    }
  ];

  const handleKnowledgeClick = (messageId) => {
    setSelectedMessageKnowledge(messageId);
    setActiveTab('knowledge');
  };

  const AssistantMessage = ({ message }) => (
    <div className="flex gap-3 mb-6">
      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
        <Bot className="w-5 h-5 text-white" />
      </div>
      <div className="flex-1">
        <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
          <div className="prose prose-sm max-w-none text-gray-800">
            {message.content.split('\n').map((line, i) => {
              if (line.startsWith('**') && line.endsWith('**')) {
                return <p key={i} className="font-semibold mb-2">{line.replace(/\*\*/g, '')}</p>;
              }
              if (line.trim() === '') return null;
              return <p key={i} className="mb-2 last:mb-0">{line}</p>;
            })}
          </div>
          
          {message.suggestions && (
            <div className="mt-4 flex flex-wrap gap-2">
              {message.suggestions.map((suggestion, idx) => (
                <button
                  key={idx}
                  className="text-xs bg-gray-100 text-gray-700 px-3 py-2 rounded-lg hover:bg-gray-200 transition-all"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          )}
        </div>
        
        <div className="flex items-center gap-2 mt-2 ml-2">
          <button className="p-1 hover:bg-gray-100 rounded transition-all" title="Like">
            <ThumbsUp className="w-3 h-3 text-gray-400 hover:text-green-600" />
          </button>
          <button className="p-1 hover:bg-gray-100 rounded transition-all" title="Dislike">
            <ThumbsDown className="w-3 h-3 text-gray-400 hover:text-red-600" />
          </button>
          <button className="p-1 hover:bg-gray-100 rounded transition-all" title="Copy">
            <Copy className="w-3 h-3 text-gray-400 hover:text-blue-600" />
          </button>
          {message.hasKnowledge && (
            <button
              onClick={() => handleKnowledgeClick(message.id)}
              className="flex items-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 rounded hover:bg-blue-100 border border-blue-200 transition-all ml-2"
              title="View knowledge graph"
            >
              <BookOpen className="w-3 h-3" />
              <span className="text-xs font-medium">Knowledge</span>
            </button>
          )}
          <span className="text-xs text-gray-400 ml-1">Just now</span>
        </div>
      </div>
    </div>
  );

  const WorkflowProgressBar = () => (
    <div className="bg-white border-b border-gray-200 px-6 py-4">
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">Pipeline Progress</span>
          <span className="text-sm font-semibold text-blue-600">{Math.round(completionPercentage)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div 
            className="bg-gradient-to-r from-blue-500 to-purple-600 h-2 rounded-full transition-all duration-500"
            style={{ width: `${completionPercentage}%` }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between">
        {workflowSteps.map((step, index) => (
          <div key={step.id} className="flex items-center flex-1">
            <div 
              className={`flex items-center gap-2 cursor-pointer ${
                step.status === 'completed' ? 'text-green-600' :
                step.status === 'current' ? 'text-blue-600' :
                'text-gray-400'
              }`}
            >
              {step.status === 'completed' ? (
                <CheckCircle className="w-6 h-6" />
              ) : step.status === 'current' ? (
                <div className="w-6 h-6 rounded-full border-4 border-blue-600 bg-white animate-pulse" />
              ) : (
                <Circle className="w-6 h-6" />
              )}
              <span className={`text-sm font-medium whitespace-nowrap ${
                step.status === 'current' ? 'font-semibold' : ''
              }`}>
                {step.name}
              </span>
            </div>
            {index < workflowSteps.length - 1 && (
              <div className={`flex-1 h-1 mx-2 ${
                step.status === 'completed' ? 'bg-green-600' : 'bg-gray-300'
              }`} />
            )}
          </div>
        ))}
      </div>
    </div>
  );

  const ConversationView = () => (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto">
          {messages.map((message) => (
            <AssistantMessage key={message.id} message={message} />
          ))}
        </div>
      </div>

      <div className="border-t border-gray-200 bg-white p-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-lg border-2 border-gray-200 shadow-sm hover:border-blue-300 transition-all">
            <div className="p-4">
              <div className="flex items-start gap-3">
                <MessageSquare className="w-5 h-5 text-gray-400 mt-1" />
                <div className="flex-1">
                  <textarea
                    value={queryInput}
                    onChange={(e) => setQueryInput(e.target.value)}
                    placeholder="Ask me to build features... (e.g., 'Build compliance story features')"
                    className="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none text-sm"
                    rows={2}
                  />
                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-xs text-gray-500">Shift + Enter for new line</span>
                    <button className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-all">
                      <Send className="w-4 h-4" />
                      <span className="font-medium">Send</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div className="text-center text-sm text-gray-500 mt-4">
            💡 Try: "Build compliance features" • "Add risk scoring" • "Create custom feature"
          </div>
        </div>
      </div>
    </div>
  );

  const KnowledgeView = () => {
    if (!selectedMessageKnowledge || !knowledgeGraphs[selectedMessageKnowledge]) {
      return (
        <div className="flex-1 flex items-center justify-center bg-gray-50">
          <div className="text-center">
            <Network className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-700 mb-2">No Knowledge Selected</h3>
            <p className="text-sm text-gray-500">Click "Knowledge" on any message to view its reasoning</p>
          </div>
        </div>
      );
    }

    const knowledge = knowledgeGraphs[selectedMessageKnowledge];

    return (
      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 p-6 overflow-y-auto bg-gray-50">
          {/* Main Insight */}
          <div className="bg-white rounded-lg border-2 border-gray-200 p-6 mb-6 max-w-6xl mx-auto">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-blue-600" />
              Main Insight
            </h3>
            <p className="text-gray-700 leading-relaxed">{knowledge.mainInsight}</p>
          </div>

          {/* Knowledge Graph */}
          <div className="bg-white rounded-lg border-2 border-gray-200 p-6 min-h-[500px] mb-6 max-w-6xl mx-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <Network className="w-5 h-5 text-purple-600" />
                Reasoning Flow
              </h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setZoom(Math.max(0.5, zoom - 0.1))}
                  className="p-2 bg-gray-100 rounded-lg hover:bg-gray-200 border border-gray-300"
                  title="Zoom out"
                >
                  <ZoomOut className="w-4 h-4 text-gray-600" />
                </button>
                <button
                  onClick={() => setZoom(Math.min(2, zoom + 0.1))}
                  className="p-2 bg-gray-100 rounded-lg hover:bg-gray-200 border border-gray-300"
                  title="Zoom in"
                >
                  <ZoomIn className="w-4 h-4 text-gray-600" />
                </button>
              </div>
            </div>
            <svg width="100%" height="400" style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}>
              {knowledge.connections.map((conn, idx) => {
                const fromNode = knowledge.nodes.find(n => n.id === conn.from);
                const toNode = knowledge.nodes.find(n => n.id === conn.to);
                return (
                  <g key={idx}>
                    <line
                      x1={fromNode.position.x + 75}
                      y1={fromNode.position.y + 30}
                      x2={toNode.position.x + 75}
                      y2={toNode.position.y + 30}
                      stroke="#cbd5e1"
                      strokeWidth="2"
                      markerEnd="url(#arrowhead)"
                    />
                    <text
                      x={(fromNode.position.x + toNode.position.x) / 2 + 75}
                      y={(fromNode.position.y + toNode.position.y) / 2 + 20}
                      fill="#64748b"
                      fontSize="12"
                      textAnchor="middle"
                    >
                      {conn.label}
                    </text>
                  </g>
                );
              })}

              <defs>
                <marker
                  id="arrowhead"
                  markerWidth="10"
                  markerHeight="10"
                  refX="9"
                  refY="3"
                  orient="auto"
                >
                  <polygon points="0 0, 10 3, 0 6" fill="#cbd5e1" />
                </marker>
              </defs>

              {knowledge.nodes.map((node) => {
                const colors = {
                  'user-action': { bg: '#dbeafe', border: '#3b82f6', text: '#1e40af' },
                  'analysis': { bg: '#fef3c7', border: '#f59e0b', text: '#92400e' },
                  'insight': { bg: '#d1fae5', border: '#10b981', text: '#065f46' },
                  'recommendation': { bg: '#e9d5ff', border: '#a855f7', text: '#6b21a8' },
                  'context': { bg: '#fce7f3', border: '#ec4899', text: '#9f1239' }
                };
                const color = colors[node.type];

                return (
                  <g key={node.id}>
                    <foreignObject
                      x={node.position.x}
                      y={node.position.y}
                      width="150"
                      height="60"
                    >
                      <div
                        className="h-full rounded-lg p-2 border-2 cursor-pointer hover:shadow-lg transition-all"
                        style={{
                          backgroundColor: color.bg,
                          borderColor: color.border
                        }}
                        title={node.details}
                      >
                        <div
                          className="text-xs font-semibold leading-tight"
                          style={{ color: color.text }}
                        >
                          {node.label}
                        </div>
                        <div className="text-xs text-gray-600 mt-1 capitalize">
                          {node.type.replace('-', ' ')}
                        </div>
                      </div>
                    </foreignObject>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Statistics */}
          <div className="bg-white rounded-lg border-2 border-gray-200 p-6 max-w-6xl mx-auto">
            <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-green-600" />
              Statistics
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(knowledge.statistics).map(([key, value]) => (
                <div key={key} className="text-center bg-gradient-to-br from-blue-50 to-purple-50 rounded-lg p-4 border border-blue-200">
                  <div className="text-2xl font-bold text-blue-600">{value}</div>
                  <div className="text-xs text-gray-600 mt-1">{key}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Panel - Related Insights */}
        <div className="w-80 bg-white border-l border-gray-200 p-6 overflow-y-auto">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Related Insights</h3>
          <div className="space-y-4">
            {knowledge.relatedInsights.map((insight, idx) => {
              const Icon = insight.icon;
              return (
                <div
                  key={idx}
                  className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-blue-300 transition-all cursor-pointer"
                >
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                      <Icon className="w-4 h-4 text-blue-600" />
                    </div>
                    <div className="flex-1">
                      <div className="font-semibold text-sm text-gray-900 mb-1">
                        {insight.title}
                      </div>
                      <div className="text-xs text-gray-600 leading-relaxed">
                        {insight.description}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-6">
            <h4 className="text-sm font-semibold text-gray-900 mb-3">Node Types</h4>
            <div className="space-y-2 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-blue-200 border-2 border-blue-500"></div>
                <span className="text-gray-700">User Action</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-yellow-200 border-2 border-yellow-500"></div>
                <span className="text-gray-700">Analysis</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-green-200 border-2 border-green-500"></div>
                <span className="text-gray-700">Insight</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-purple-200 border-2 border-purple-500"></div>
                <span className="text-gray-700">Recommendation</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-pink-200 border-2 border-pink-500"></div>
                <span className="text-gray-700">Context</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 flex">
      <div className="flex-1 flex flex-col">
        {/* Header with Tabs */}
        <div className="bg-white border-b border-gray-200">
          <div className="px-6 py-4">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h1 className="text-xl font-bold text-gray-900">🎯 Feature Builder</h1>
                <p className="text-sm text-gray-600">compliance_controls.csv • 1,247 rows × 23 columns</p>
              </div>
              <div className="flex items-center gap-2">
                <button className="flex items-center gap-2 px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 border border-blue-300 transition-all">
                  <PlayCircle className="w-4 h-4" />
                  Dry Run
                </button>
                <button className="flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-all">
                  <Save className="w-4 h-4" />
                  Save Pipeline
                </button>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 border-b border-gray-200">
              <button
                onClick={() => setActiveTab('conversation')}
                className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-all ${
                  activeTab === 'conversation'
                    ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                <MessageSquare className="w-4 h-4" />
                Conversation
              </button>
              <button
                onClick={() => setActiveTab('knowledge')}
                className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-all ${
                  activeTab === 'knowledge'
                    ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                <Network className="w-4 h-4" />
                Knowledge
              </button>
            </div>
          </div>

          {/* Pipeline Progress */}
          <WorkflowProgressBar />
        </div>

        {/* Tab Content */}
        {activeTab === 'conversation' ? <ConversationView /> : <KnowledgeView />}
      </div>

      {/* Right Sidebar - Feature Pipeline */}
      <div className="w-96 bg-white border-l border-gray-200 overflow-y-auto flex-shrink-0">
        <div className="p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-6">Feature Pipeline</h2>
          
          <div className="bg-purple-50 rounded-lg p-4 mb-6 border border-purple-200">
            <h3 className="text-sm font-semibold text-purple-900 mb-3">Pipeline Status</h3>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-purple-700">• Features:</span>
                <span className="font-semibold text-purple-900">0</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-purple-700">• Risk features:</span>
                <span className="font-semibold text-purple-900">0</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-purple-700">• New columns:</span>
                <span className="font-semibold text-purple-900">+0</span>
              </div>
            </div>
          </div>

          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Quick Actions</h3>
            <div className="space-y-2">
              <button className="w-full text-left p-3 bg-blue-50 rounded-lg hover:bg-blue-100 text-sm border border-blue-200 flex items-center gap-2 transition-all">
                <Sparkles className="w-4 h-4 text-blue-600" />
                💡 Build Compliance Features
              </button>
              <button className="w-full text-left p-3 bg-red-50 rounded-lg hover:bg-red-100 text-sm border border-red-200 flex items-center gap-2 transition-all">
                <TrendingUp className="w-4 h-4 text-red-600" />
                🎲 Add Risk Scoring
              </button>
              <button className="w-full text-left p-3 bg-green-50 rounded-lg hover:bg-green-100 text-sm border border-green-200 flex items-center gap-2 transition-all">
                <Plus className="w-4 h-4 text-green-600" />
                ➕ Custom Feature
              </button>
              <button className="w-full text-left p-3 bg-gray-50 rounded-lg hover:bg-gray-100 text-sm border border-gray-200 flex items-center gap-2 transition-all">
                <Eye className="w-4 h-4 text-gray-600" />
                👁️ Preview Transformation
              </button>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-3">Example Features</h3>
            <div className="space-y-3">
              <div className="p-3 bg-white rounded-lg border border-gray-200 hover:border-blue-300 transition-all cursor-pointer">
                <div className="font-medium text-sm text-gray-900 mb-1">is_high_priority</div>
                <div className="text-xs text-gray-600">Boolean classification</div>
              </div>
              <div className="p-3 bg-white rounded-lg border border-gray-200 hover:border-blue-300 transition-all cursor-pointer">
                <div className="font-medium text-sm text-gray-900 mb-1">maturity_level</div>
                <div className="text-xs text-gray-600">4-level categorization</div>
              </div>
              <div className="p-3 bg-white rounded-lg border border-gray-200 hover:border-blue-300 transition-all cursor-pointer">
                <div className="font-medium text-sm text-gray-900 mb-1">risk_score</div>
                <div className="text-xs text-gray-600">Likelihood × Impact</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FinalFeatureBuilder;
