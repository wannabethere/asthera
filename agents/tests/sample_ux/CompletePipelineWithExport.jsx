import React, { useState, useRef, useEffect } from 'react';
import { 
  CheckCircle2, 
  Loader2, 
  Send,
  Shield,
  Clock,
  Sparkles,
  Grid3x3,
  Info,
  MessageSquare,
  Brain,
  Plus,
  Users,
  Download,
  ChevronDown,
  ChevronUp,
  Trash2,
  TrendingUp,
  ArrowRight,
  Database,
  Code,
  Play,
  Table,
  X,
  ArrowLeft,
  GitBranch,
  Calendar,
  Share2,
  FileCode,
  CheckCircle,
  Lock,
  User,
  UserPlus
} from 'lucide-react';

const CompletePipelineWithExport = () => {
  const [features, setFeatures] = useState([]);
  const [recommendedFeatures, setRecommendedFeatures] = useState([]);
  const [selectedFeatures, setSelectedFeatures] = useState(new Set());
  const [viewMode, setViewMode] = useState('chat'); // 'chat' | 'recommendations' | 'features' | 'transformations'
  const [metrics, setMetrics] = useState({
    total_features: 0,
    silver_features: 0,
    gold_features: 0,
    controls_covered: 0
  });
  
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatThinking, setIsChatThinking] = useState(false);
  const [isLoadingRecommendations, setIsLoadingRecommendations] = useState(false);
  const [conversationContext, setConversationContext] = useState({
    compliance_framework: null,
    severity_levels: [],
    sla_requirements: {},
  });
  
  // Feature Registry
  const [featureRegistry, setFeatureRegistry] = useState([]);
  
  // Export & Scheduler State
  const [exportFormat, setExportFormat] = useState('dbt');
  const [scheduleFrequency, setScheduleFrequency] = useState('daily');
  const [scheduleTime, setScheduleTime] = useState('02:00');
  const [selectedUsers, setSelectedUsers] = useState(new Set(['team-security', 'team-compliance']));
  const [accessLevel, setAccessLevel] = useState('read');
  
  const chatEndRef = useRef(null);

  useEffect(() => {
    setChatMessages([
      {
        role: 'assistant',
        content: "👋 **Welcome!** I'm your Feature Engineering Assistant.\n\n**Workflow:**\n1️⃣ Ask me what features you need\n2️⃣ I'll recommend KPIs and features\n3️⃣ You pick the ones you want\n4️⃣ I'll generate the complete pipeline\n\n**Try asking:**",
        timestamp: new Date(),
        suggestions: [
          "I need SOC2 vulnerability features",
          "Show me compliance monitoring KPIs"
        ]
      }
    ]);
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  useEffect(() => {
    setMetrics({
      total_features: features.length,
      silver_features: features.filter(f => f.transformation_layer === 'silver').length,
      gold_features: features.filter(f => f.transformation_layer === 'gold').length,
      controls_covered: new Set(features.map(f => f.compliance_control)).size
    });
  }, [features]);

  const handleChatSubmit = async (e, suggestedMessage = null) => {
    if (e) e.preventDefault();
    const message = suggestedMessage || chatInput;
    if (!message.trim()) return;

    addChatMessage('user', message);
    if (!suggestedMessage) setChatInput('');
    setIsChatThinking(true);

    // Call feature engineering API to get recommendations
    await fetchFeatureRecommendations(message);
    
    setIsChatThinking(false);
  };

  const fetchFeatureRecommendations = async (userQuery) => {
    setIsLoadingRecommendations(true);
    try {
      // Call the feature engineering API endpoint
      // The endpoint should be: /feature-engineering/recommend
      const response = await fetch('/feature-engineering/recommend', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_query: userQuery,
          project_id: 'default-project', // TODO: Get from context
        }),
      });

      let data;
      if (response.ok) {
        data = await response.json();
      } else {
        // Fallback to mock data for development
        console.warn('API call failed, using mock data');
        data = generateMockRecommendations(userQuery);
      }

      // Handle both direct response and nested result structure
      const recommendations = data.result?.recommended_features || data.recommended_features || [];
      
      if (recommendations.length > 0) {
        setRecommendedFeatures(recommendations);
        setViewMode('recommendations');
        addChatMessage('assistant', 
          `✨ I found **${recommendations.length} recommended features**!\n\n📋 Review the recommendations below and select the KPIs you want to include in your pipeline.`,
          ["View all recommendations"]
        );
      } else {
        addChatMessage('assistant', 
          `I couldn't find specific recommendations for that query. Could you provide more details about what features you need?`,
          ["I need SOC2 vulnerability features", "Show compliance monitoring KPIs"]
        );
      }
    } catch (error) {
      console.error('Error fetching recommendations:', error);
      // Fallback to mock data
      const mockData = generateMockRecommendations(userQuery);
      setRecommendedFeatures(mockData);
      setViewMode('recommendations');
      addChatMessage('assistant', 
        `✨ I found **${mockData.length} recommended features**!\n\n📋 Review the recommendations below and select the KPIs you want to include.`,
        []
      );
    } finally {
      setIsLoadingRecommendations(false);
    }
  };

  const generateMockRecommendations = (userQuery) => {
    // Generate mock recommendations based on query
    const lowerQuery = userQuery.toLowerCase();
    
    if (lowerQuery.includes('soc2') || lowerQuery.includes('vulnerability')) {
      return [
        {
          feature_name: "critical_vulnerability_count",
          feature_type: "count",
          natural_language_question: "Count the number of vulnerabilities where severity is Critical and state is ACTIVE",
          business_context: "This metric helps in understanding the current risk exposure from critical vulnerabilities that are still active and need immediate attention.",
          compliance_reasoning: "Monitoring the count of critical vulnerabilities supports compliance with SOC2 by ensuring that high-risk vulnerabilities are identified and managed effectively.",
          transformation_layer: "gold",
          feature_group: "vulnerability_counts",
          recommendation_score: 0.9,
          required_schemas: ["dev_assets"],
          aggregation_method: "count",
          filters_applied: ["severity = 'Critical'", "state = 'ACTIVE'"]
        },
        {
          feature_name: "high_vulnerability_count",
          feature_type: "count",
          natural_language_question: "Count the number of vulnerabilities where severity is High and state is ACTIVE",
          business_context: "This metric provides insight into the number of high-risk vulnerabilities that require remediation.",
          compliance_reasoning: "Tracking high vulnerabilities aligns with SOC2 compliance by ensuring that vulnerabilities are actively managed and mitigated.",
          transformation_layer: "gold",
          feature_group: "vulnerability_counts",
          recommendation_score: 0.9,
          required_schemas: ["dev_assets"],
          aggregation_method: "count",
          filters_applied: ["severity = 'High'", "state = 'ACTIVE'"]
        },
        {
          feature_name: "critical_sla_breached_count",
          feature_type: "count",
          natural_language_question: "Count the number of critical vulnerabilities where (current_date - detected_time) > 7 days",
          business_context: "This metric indicates how many critical vulnerabilities have exceeded the SLA for remediation.",
          compliance_reasoning: "This metric supports SOC2 compliance by ensuring that critical vulnerabilities are addressed within the required timeframe.",
          transformation_layer: "gold",
          feature_group: "sla_metrics",
          recommendation_score: 0.85,
          required_schemas: ["dev_assets"],
          aggregation_method: "count",
          filters_applied: ["severity = 'Critical'", "state != 'remediated'"]
        },
        {
          feature_name: "avg_remediation_time_days",
          feature_type: "metric",
          natural_language_question: "Calculate the average number of days between detected_time and remediation_time for vulnerabilities where state is REMEDIATED",
          business_context: "This metric provides insight into the efficiency of the remediation process.",
          compliance_reasoning: "Tracking average remediation time supports SOC2 compliance by ensuring that vulnerabilities are addressed promptly.",
          transformation_layer: "gold",
          feature_group: "remediation_metrics",
          recommendation_score: 0.8,
          required_schemas: ["dev_assets"],
          aggregation_method: "avg",
          filters_applied: ["state = 'REMEDIATED'"]
        }
      ];
    }
    
    // Default recommendations
    return [
      {
        feature_name: "default_metric",
        feature_type: "metric",
        natural_language_question: "Calculate a metric based on your requirements",
        business_context: "This is a placeholder recommendation.",
        compliance_reasoning: "Please provide more specific requirements.",
        transformation_layer: "gold",
        feature_group: "default",
        recommendation_score: 0.5,
        required_schemas: [],
        aggregation_method: "count",
        filters_applied: []
      }
    ];
  };

  const addChatMessage = (role, content, suggestions = []) => {
    setChatMessages(prev => [...prev, {
      role,
      content,
      timestamp: new Date(),
      suggestions
    }]);
  };

  const handleSelectRecommendations = () => {
    // Convert selected recommendations to features with pipeline structure
    const selectedRecs = recommendedFeatures.filter((_, idx) => selectedFeatures.has(idx));
    
    const newFeatures = selectedRecs.map((rec, idx) => ({
      id: Date.now() + idx,
      feature_name: rec.feature_name,
      transformation_layer: rec.transformation_layer || 'gold',
      compliance_control: rec.compliance_reasoning?.match(/SOC2\s+CC\d+\.\d+/)?.[0] || 'General',
      natural_language_question: rec.natural_language_question,
      business_context: rec.business_context,
      compliance_reasoning: rec.compliance_reasoning,
      feature_group: rec.feature_group,
      recommendation_score: rec.recommendation_score,
      // Generate pipeline structure (simplified for now)
      silver_pipeline: {
        source_tables: rec.required_schemas.map(schema => ({
          name: schema.replace('*: ', ''),
          layer: "bronze",
          columns: rec.required_fields || []
        })),
        destination_table: {
          name: `silver_${rec.feature_name}`,
          layer: "silver",
          columns: [rec.feature_name, "updated_at"]
        },
        transformation_description: `Transform ${rec.required_schemas.join(', ')} to calculate ${rec.natural_language_question}`,
        sample_output: []
      },
      gold_pipeline: rec.transformation_layer === 'gold' ? {
        source_tables: [{
          name: `silver_${rec.feature_name}`,
          layer: "silver",
          columns: [rec.feature_name, "updated_at"]
        }],
        destination_table: {
          name: `gold_${rec.feature_name}`,
          layer: "gold",
          columns: [rec.feature_name, "aggregated_value", "updated_at"]
        },
        transformation_description: `Aggregate ${rec.feature_name} using ${rec.aggregation_method}`,
        sample_output: []
      } : null
    }));

    // Add to registry
    setFeatureRegistry(prev => [...prev, ...newFeatures]);
    setFeatures(prev => [...prev, ...newFeatures]);
    setSelectedFeatures(new Set());
    setViewMode('features');
    
    addChatMessage('assistant', 
      `✅ Added **${newFeatures.length} features** to your registry!\n\n📊 You can now view the complete pipeline or add more features.`,
      ["View pipeline", "Add more features"]
    );
  };

  const toggleFeatureSelection = (featureId) => {
    const newSelected = new Set(selectedFeatures);
    if (newSelected.has(featureId)) {
      newSelected.delete(featureId);
    } else {
      newSelected.add(featureId);
    }
    setSelectedFeatures(newSelected);
  };

  const toggleRecommendationSelection = (index) => {
    const newSelected = new Set(selectedFeatures);
    if (newSelected.has(index)) {
      newSelected.delete(index);
    } else {
      newSelected.add(index);
    }
    setSelectedFeatures(newSelected);
  };

  const toggleUserSelection = (userId) => {
    const newUsers = new Set(selectedUsers);
    if (newUsers.has(userId)) {
      newUsers.delete(userId);
    } else {
      newUsers.add(userId);
    }
    setSelectedUsers(newUsers);
  };

  const getSelectedFeatures = () => features.filter(f => selectedFeatures.has(f.id));

  const exportFormats = [
    { id: 'dbt', name: 'dbt Models', icon: FileCode, description: 'SQL models with dependencies' },
    { id: 'airflow', name: 'Airflow DAG', icon: GitBranch, description: 'Python DAG with tasks' },
    { id: 'databricks', name: 'Databricks Notebook', icon: Code, description: 'Spark transformations' },
    { id: 'sql', name: 'Raw SQL', icon: Database, description: 'Standalone SQL scripts' }
  ];

  const scheduleOptions = [
    { id: 'hourly', name: 'Hourly', cron: '0 * * * *' },
    { id: 'daily', name: 'Daily', cron: '0 2 * * *' },
    { id: 'weekly', name: 'Weekly', cron: '0 2 * * 0' },
    { id: 'custom', name: 'Custom', cron: 'Custom...' }
  ];

  const availableUsers = [
    { id: 'team-security', name: 'Security Team', type: 'team', icon: Shield },
    { id: 'team-compliance', name: 'Compliance Team', type: 'team', icon: CheckCircle },
    { id: 'team-engineering', name: 'Engineering Team', type: 'team', icon: Code },
    { id: 'user-john', name: 'John Doe (Security Lead)', type: 'user', icon: User },
    { id: 'user-sarah', name: 'Sarah Chen (Compliance)', type: 'user', icon: User }
  ];

  return (
    <div className="h-screen bg-slate-100 flex overflow-hidden">
      {/* LEFT: Chat */}
      <div className="w-1/2 border-r-2 border-slate-300 flex flex-col bg-white">
        <div className="p-6 border-b bg-gradient-to-r from-indigo-600 to-purple-600">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center">
              <Brain className="w-7 h-7 text-indigo-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Feature Engineering Assistant</h1>
              <p className="text-indigo-100 text-sm">Complete Pipeline: Build → Transform → Export → Schedule → Share</p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-slate-50">
          {chatMessages.map((message, idx) => (
            <div key={idx} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] ${
                message.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-white text-slate-900 border'
              } rounded-lg p-4 shadow-md`}>
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                {message.suggestions?.length > 0 && (
                  <div className="mt-3 pt-3 border-t flex flex-wrap gap-2">
                    {message.suggestions.map((s, i) => (
                      <button key={i} onClick={() => handleChatSubmit(null, s)}
                        className="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-full text-xs font-medium border border-indigo-200">
                        {s}
                      </button>
                    ))}
                  </div>
                )}
                <p className="text-xs mt-2 opacity-60">{message.timestamp.toLocaleTimeString()}</p>
              </div>
            </div>
          ))}
          {isChatThinking && (
            <div className="flex justify-start">
              <div className="bg-white border rounded-lg p-4 shadow-md">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
                  <span className="text-sm text-slate-600">Generating...</span>
                </div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="p-4 border-t-2 bg-white">
          <form onSubmit={handleChatSubmit} className="flex gap-2 mb-3">
            <input type="text" value={chatInput} onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask for features..." className="flex-1 px-4 py-3 border-2 rounded-lg focus:ring-2 focus:ring-indigo-500"
              disabled={isChatThinking} />
            <button type="submit" disabled={!chatInput.trim() || isChatThinking}
              className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-slate-300">
              <Send className="w-5 h-5" />
            </button>
          </form>
          <div className="flex gap-2">
            <button onClick={() => handleChatSubmit(null, "I need SOC2 vulnerability features")}
              className="px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-700 rounded-lg text-sm border-2 flex items-center gap-1">
              <Plus className="w-4 h-4" />SOC2
            </button>
            {viewMode === 'features' && selectedFeatures.size > 0 && (
              <button onClick={() => setViewMode('transformations')}
                className="px-3 py-1.5 bg-green-100 hover:bg-green-200 text-green-700 rounded-lg text-sm border-2 border-green-300 flex items-center gap-1 font-medium">
                <GitBranch className="w-4 h-4" />View Pipeline ({selectedFeatures.size})
              </button>
            )}
            {viewMode === 'recommendations' && recommendedFeatures.length > 0 && (
              <button onClick={() => setViewMode('chat')}
                className="px-3 py-1.5 bg-indigo-100 hover:bg-indigo-200 text-indigo-700 rounded-lg text-sm border-2 border-indigo-300 flex items-center gap-1 font-medium">
                <ArrowLeft className="w-4 h-4" />Back to Chat
              </button>
            )}
          </div>
        </div>
      </div>

      {/* RIGHT: Recommendations, Features or Pipeline */}
      <div className="w-1/2 flex flex-col bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="p-6 bg-white border-b-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              {(viewMode === 'transformations' || viewMode === 'features') && (
                <button onClick={() => {
                  if (viewMode === 'transformations') setViewMode('features');
                  else if (viewMode === 'features') setViewMode('recommendations');
                  else setViewMode('chat');
                }} className="p-2 hover:bg-slate-100 rounded-lg">
                  <ArrowLeft className="w-5 h-5" />
                </button>
              )}
              <div>
                <h2 className="text-2xl font-bold flex items-center gap-2">
                  {viewMode === 'chat' ? (
                    <><MessageSquare className="w-6 h-6 text-indigo-600" />Chat</>
                  ) : viewMode === 'recommendations' ? (
                    <><Sparkles className="w-6 h-6 text-purple-600" />Recommendations</>
                  ) : viewMode === 'features' ? (
                    <><Sparkles className="w-6 h-6 text-indigo-600" />Feature Registry</>
                  ) : (
                    <><GitBranch className="w-6 h-6 text-emerald-600" />Complete Pipeline</>
                  )}
                </h2>
                <p className="text-sm text-slate-600">
                  {viewMode === 'chat' ? 'Ask for feature recommendations' :
                   viewMode === 'recommendations' ? `Select KPIs to add (${selectedFeatures.size} selected)` :
                   viewMode === 'features' ? `${features.length} features in registry` :
                   `${selectedFeatures.size} selected`}
                </p>
              </div>
            </div>
          </div>
          {viewMode === 'recommendations' && recommendedFeatures.length > 0 && (
            <div className="mt-4">
              <button 
                onClick={handleSelectRecommendations}
                disabled={selectedFeatures.size === 0}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-slate-300 text-white rounded-lg font-bold flex items-center gap-2">
                <Plus className="w-4 h-4" />
                Add {selectedFeatures.size > 0 ? `${selectedFeatures.size} ` : ''}Selected to Registry
              </button>
            </div>
          )}
          {viewMode === 'features' && features.length > 0 && (
            <div className="grid grid-cols-4 gap-3 mt-4">
              <div className="bg-indigo-50 rounded-lg p-3 border-2 border-indigo-200">
                <div className="text-2xl font-bold text-indigo-600">{metrics.total_features}</div>
                <div className="text-xs text-slate-600">Total</div>
              </div>
              <div className="bg-emerald-50 rounded-lg p-3 border-2 border-emerald-200">
                <div className="text-2xl font-bold text-emerald-600">{metrics.silver_features}</div>
                <div className="text-xs text-slate-600">Silver</div>
              </div>
              <div className="bg-amber-50 rounded-lg p-3 border-2 border-amber-200">
                <div className="text-2xl font-bold text-amber-600">{metrics.gold_features}</div>
                <div className="text-xs text-slate-600">Gold</div>
              </div>
              <div className="bg-purple-50 rounded-lg p-3 border-2 border-purple-200">
                <div className="text-2xl font-bold text-purple-600">{selectedFeatures.size}</div>
                <div className="text-xs text-slate-600">Selected</div>
              </div>
            </div>
          )}
        </div>

        {viewMode === 'chat' && (
          <div className="flex-1 overflow-y-auto p-6 flex items-center justify-center">
            <div className="text-center max-w-md">
              <Brain className="w-16 h-16 text-indigo-600 mx-auto mb-4" />
              <h3 className="text-xl font-semibold mb-2">Start a Conversation</h3>
              <p className="text-sm text-slate-600">Ask me what features or KPIs you need, and I'll recommend them!</p>
            </div>
          </div>
        )}

        {viewMode === 'recommendations' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-3">
            {isLoadingRecommendations ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <Loader2 className="w-12 h-12 text-indigo-600 mx-auto mb-4 animate-spin" />
                  <p className="text-sm text-slate-600">Generating recommendations...</p>
                </div>
              </div>
            ) : recommendedFeatures.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <Info className="w-16 h-16 text-slate-400 mx-auto mb-4" />
                  <h3 className="text-xl font-semibold mb-2">No Recommendations Yet</h3>
                  <p className="text-sm text-slate-600">Ask a question in the chat to get feature recommendations!</p>
                </div>
              </div>
            ) : (
              recommendedFeatures.map((rec, index) => (
                <div key={index} className={`bg-white rounded-lg shadow-md border-2 ${
                  selectedFeatures.has(index) ? 'border-purple-400 bg-purple-50/50' : 'border-slate-200'
                }`}>
                  <div className="p-4 flex items-start gap-3">
                    <input type="checkbox" checked={selectedFeatures.has(index)}
                      onChange={() => toggleRecommendationSelection(index)}
                      className="mt-1 w-5 h-5 text-purple-600 rounded cursor-pointer" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-semibold">{rec.feature_name}</h3>
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                          rec.transformation_layer === 'silver' 
                            ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                        }`}>{(rec.transformation_layer || 'gold').toUpperCase()}</span>
                        {rec.recommendation_score && (
                          <span className="px-2 py-0.5 rounded text-xs bg-blue-100 text-blue-700">
                            {Math.round(rec.recommendation_score * 100)}% match
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-slate-700 mb-2 font-medium">{rec.natural_language_question}</p>
                      {rec.business_context && (
                        <p className="text-xs text-slate-600 mb-1">💼 {rec.business_context}</p>
                      )}
                      {rec.compliance_reasoning && (
                        <p className="text-xs text-slate-600">🛡️ {rec.compliance_reasoning}</p>
                      )}
                      {rec.feature_group && (
                        <div className="mt-2">
                          <span className="text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded">
                            Group: {rec.feature_group}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {viewMode === 'features' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-3">
            {features.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <Database className="w-16 h-16 text-indigo-600 mx-auto mb-4" />
                  <h3 className="text-xl font-semibold mb-2">Feature Registry Empty</h3>
                  <p className="text-sm text-slate-600">Select recommendations to add features to your registry!</p>
                </div>
              </div>
            ) : (
              features.map((feature) => (
                <div key={feature.id} className={`bg-white rounded-lg shadow-md border-2 ${
                  selectedFeatures.has(feature.id) ? 'border-green-400 bg-green-50/50' : 'border-slate-200'
                }`}>
                  <div className="p-4 flex items-start gap-3">
                    <input type="checkbox" checked={selectedFeatures.has(feature.id)}
                      onChange={() => toggleFeatureSelection(feature.id)}
                      className="mt-1 w-5 h-5 text-green-600 rounded cursor-pointer" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className="font-semibold">{feature.feature_name}</h3>
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                          feature.transformation_layer === 'silver' 
                            ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
                        }`}>{feature.transformation_layer.toUpperCase()}</span>
                      </div>
                      <p className="text-sm text-slate-700">{feature.natural_language_question}</p>
                      {feature.business_context && (
                        <p className="text-xs text-slate-600 mt-1">💼 {feature.business_context}</p>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {viewMode === 'transformations' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {getSelectedFeatures().map((feature, idx) => (
              <div key={feature.id} className="bg-white rounded-lg border-2 border-slate-200 overflow-hidden">
                {/* Header */}
                <div className="p-4 bg-slate-50 border-b-2">
                  <div className="flex items-center gap-3">
                    <span className="text-xl font-bold text-slate-400">#{idx + 1}</span>
                    <div className="flex-1">
                      <h3 className="text-lg font-bold">{feature.feature_name}</h3>
                      <p className="text-sm text-slate-600 italic">{feature.natural_language_question}</p>
                    </div>
                  </div>
                </div>

                {/* STEP 1: Bronze → Silver */}
                <div className="p-6 bg-gradient-to-br from-blue-50 to-cyan-50 border-b-2">
                  <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
                    <div className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-xs">1</div>
                    BRONZE → SILVER
                  </h4>
                  <div className="flex items-center justify-center gap-4 mb-4">
                    <div className="space-y-2">
                      {feature.silver_pipeline.source_tables.map((t, i) => (
                        <div key={i} className="bg-slate-700 border-2 border-slate-800 rounded-lg p-3 min-w-[180px]">
                          <div className="flex items-center gap-2 mb-2">
                            <Database className="w-4 h-4 text-slate-300" />
                            <div>
                              <div className="text-xs font-bold text-slate-400 uppercase">BRONZE</div>
                              <div className="text-sm font-bold text-white">{t.name}</div>
                            </div>
                          </div>
                          <div className="text-xs text-slate-300 space-y-0.5">
                            {t.columns.slice(0, 3).map((c, j) => <div key={j}>• {c}</div>)}
                          </div>
                        </div>
                      ))}
                    </div>
                    <ArrowRight className="w-8 h-8 text-emerald-600" />
                    <div className="bg-emerald-100 border-2 border-emerald-400 rounded-lg p-3 min-w-[180px]">
                      <div className="flex items-center gap-2 mb-2">
                        <Database className="w-4 h-4 text-emerald-600" />
                        <div>
                          <div className="text-xs font-bold text-emerald-900 uppercase">SILVER</div>
                          <div className="text-sm font-bold text-emerald-700">{feature.silver_pipeline.destination_table.name}</div>
                        </div>
                      </div>
                      <div className="text-xs text-emerald-600 space-y-0.5">
                        {feature.silver_pipeline.destination_table.columns.map((c, j) => <div key={j}>• {c}</div>)}
                      </div>
                    </div>
                  </div>
                  <div className="bg-white rounded-lg p-3 border border-emerald-300 mb-3">
                    <p className="text-xs text-slate-700">{feature.silver_pipeline.transformation_description}</p>
                  </div>
                  <button className="w-full px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold flex items-center justify-center gap-2 text-sm">
                    <Play className="w-4 h-4" />Run Silver
                  </button>
                </div>

                {/* STEP 2: Silver → Gold */}
                {feature.gold_pipeline && (
                  <div className="p-6 bg-gradient-to-br from-amber-50 to-orange-50 border-b-2">
                    <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
                      <div className="w-6 h-6 bg-amber-600 text-white rounded-full flex items-center justify-center text-xs">2</div>
                      SILVER → GOLD
                    </h4>
                    <div className="flex items-center justify-center gap-4 mb-4">
                      <div className="space-y-2">
                        {feature.gold_pipeline.source_tables.map((t, i) => (
                          <div key={i} className="bg-emerald-100 border-2 border-emerald-400 rounded-lg p-3 min-w-[180px]">
                            <div className="flex items-center gap-2 mb-2">
                              <Database className="w-4 h-4 text-emerald-600" />
                              <div>
                                <div className="text-xs font-bold text-emerald-900 uppercase">SILVER</div>
                                <div className="text-sm font-bold text-emerald-700">{t.name}</div>
                              </div>
                            </div>
                            <div className="text-xs text-emerald-600 space-y-0.5">
                              {t.columns.slice(0, 3).map((c, j) => <div key={j}>• {c}</div>)}
                            </div>
                          </div>
                        ))}
                      </div>
                      <ArrowRight className="w-8 h-8 text-amber-600" />
                      <div className="bg-amber-100 border-2 border-amber-400 rounded-lg p-3 min-w-[180px]">
                        <div className="flex items-center gap-2 mb-2">
                          <Database className="w-4 h-4 text-amber-600" />
                          <div>
                            <div className="text-xs font-bold text-amber-900 uppercase">GOLD</div>
                            <div className="text-sm font-bold text-amber-700">{feature.gold_pipeline.destination_table.name}</div>
                          </div>
                        </div>
                        <div className="text-xs text-amber-600 space-y-0.5">
                          {feature.gold_pipeline.destination_table.columns.map((c, j) => <div key={j}>• {c}</div>)}
                        </div>
                      </div>
                    </div>
                    <div className="bg-white rounded-lg p-3 border border-amber-300 mb-3">
                      <p className="text-xs text-slate-700">{feature.gold_pipeline.transformation_description}</p>
                    </div>
                    <button className="w-full px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-bold flex items-center justify-center gap-2 text-sm">
                      <Play className="w-4 h-4" />Run Gold
                    </button>
                  </div>
                )}

                {/* STEP 3: Export, Schedule & Share */}
                <div className="p-6 bg-gradient-to-br from-purple-50 to-pink-50">
                  <h4 className="text-sm font-bold mb-4 flex items-center gap-2">
                    <div className="w-6 h-6 bg-purple-600 text-white rounded-full flex items-center justify-center text-xs">3</div>
                    EXPORT, SCHEDULE & SHARE
                  </h4>

                  {/* Export Format */}
                  <div className="mb-4">
                    <label className="text-xs font-bold text-slate-700 mb-2 block">EXPORT FORMAT</label>
                    <div className="grid grid-cols-2 gap-2">
                      {exportFormats.map(format => (
                        <button key={format.id}
                          onClick={() => setExportFormat(format.id)}
                          className={`p-3 rounded-lg border-2 text-left transition-all ${
                            exportFormat === format.id 
                              ? 'bg-purple-100 border-purple-400' 
                              : 'bg-white border-slate-200 hover:border-purple-300'
                          }`}>
                          <div className="flex items-center gap-2 mb-1">
                            <format.icon className="w-4 h-4 text-purple-600" />
                            <span className="text-sm font-bold text-slate-900">{format.name}</span>
                          </div>
                          <p className="text-xs text-slate-600">{format.description}</p>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Schedule */}
                  <div className="mb-4">
                    <label className="text-xs font-bold text-slate-700 mb-2 block flex items-center gap-2">
                      <Calendar className="w-4 h-4" />SCHEDULE
                    </label>
                    <div className="flex gap-2 mb-2">
                      {scheduleOptions.map(opt => (
                        <button key={opt.id}
                          onClick={() => setScheduleFrequency(opt.id)}
                          className={`px-3 py-2 rounded-lg text-xs font-bold border-2 ${
                            scheduleFrequency === opt.id 
                              ? 'bg-purple-600 text-white border-purple-600' 
                              : 'bg-white text-slate-700 border-slate-200'
                          }`}>
                          {opt.name}
                        </button>
                      ))}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-xs text-slate-600 mb-1 block">Time (UTC)</label>
                        <input type="time" value={scheduleTime} onChange={(e) => setScheduleTime(e.target.value)}
                          className="w-full px-3 py-2 border-2 border-slate-200 rounded-lg text-sm" />
                      </div>
                      <div>
                        <label className="text-xs text-slate-600 mb-1 block">Cron Expression</label>
                        <input type="text" value={scheduleOptions.find(o => o.id === scheduleFrequency)?.cron}
                          className="w-full px-3 py-2 border-2 border-slate-200 rounded-lg text-sm bg-slate-50" readOnly />
                      </div>
                    </div>
                  </div>

                  {/* Share & Permissions */}
                  <div className="mb-4">
                    <label className="text-xs font-bold text-slate-700 mb-2 block flex items-center gap-2">
                      <Share2 className="w-4 h-4" />SHARING & PERMISSIONS
                    </label>
                    <div className="space-y-2 mb-3">
                      {availableUsers.map(user => (
                        <div key={user.id}
                          className={`flex items-center justify-between p-2 rounded-lg border-2 ${
                            selectedUsers.has(user.id) 
                              ? 'bg-purple-50 border-purple-300' 
                              : 'bg-white border-slate-200'
                          }`}>
                          <div className="flex items-center gap-2">
                            <input type="checkbox" checked={selectedUsers.has(user.id)}
                              onChange={() => toggleUserSelection(user.id)}
                              className="w-4 h-4 text-purple-600 rounded cursor-pointer" />
                            <user.icon className="w-4 h-4 text-slate-600" />
                            <span className="text-sm font-medium text-slate-900">{user.name}</span>
                            <span className="text-xs text-slate-500">({user.type})</span>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => setAccessLevel('read')}
                        className={`flex-1 px-3 py-2 rounded-lg text-xs font-bold border-2 ${
                          accessLevel === 'read' ? 'bg-blue-600 text-white' : 'bg-white text-slate-700 border-slate-200'
                        }`}>
                        <Lock className="w-3 h-3 inline mr-1" />Read Only
                      </button>
                      <button onClick={() => setAccessLevel('write')}
                        className={`flex-1 px-3 py-2 rounded-lg text-xs font-bold border-2 ${
                          accessLevel === 'write' ? 'bg-blue-600 text-white' : 'bg-white text-slate-700 border-slate-200'
                        }`}>
                        <UserPlus className="w-3 h-3 inline mr-1" />Read & Write
                      </button>
                    </div>
                  </div>

                  {/* Final Export Button */}
                  <button className="w-full px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-bold flex items-center justify-center gap-2 shadow-lg">
                    <Download className="w-5 h-5" />
                    Export Pipeline ({exportFormat.toUpperCase()})
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default CompletePipelineWithExport;
