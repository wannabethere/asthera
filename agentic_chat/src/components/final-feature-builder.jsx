import React, { useState, useCallback, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  Bot, Send, ThumbsUp, ThumbsDown, Copy, MessageSquare, Network,
  Database, TrendingUp, FileText, Shield, BarChart3, Sparkles,
  Eye, Save, PlayCircle, Plus, Zap, Bell, Layout, Users, X, 
  CheckCircle, Circle, BookOpen, ZoomIn, ZoomOut, Loader2, ChevronRight
} from 'lucide-react';
import { useLeenStream } from '../hooks/useLeenStream';
import { getLeenState } from '../services/api';

// LangGraph steps (Leen planner interrupts)
const LEEN_STEPS = [
  { id: 1, name: 'Select Data Sources', key: 'wait_for_datasource_selection' },
  { id: 2, name: 'Select Capabilities', key: 'wait_for_capabilities_selection' },
  { id: 3, name: 'Select Data Models', key: 'wait_for_datamodel_selection' },
  { id: 4, name: 'Confirm Build', key: 'wait_for_build_confirm' },
];

const FinalFeatureBuilder = () => {
  const [activeTab, setActiveTab] = useState('conversation');
  const [selectedMessageKnowledge, setSelectedMessageKnowledge] = useState(null);
  const [queryInput, setQueryInput] = useState('Asset risk management report for cloud automation that monitors for SOC2 compliance');
  const [zoom, setZoom] = useState(1);
  const [plannerSummary, setPlannerSummary] = useState(null);
  const [streamingMessages, setStreamingMessages] = useState([]);
  const [leenStep, setLeenStep] = useState(0);
  const [interruptPayload, setInterruptPayload] = useState(null);
  const [stateSnapshot, setStateSnapshot] = useState(null);
  const [selection, setSelection] = useState({});
  const sessionIdRef = useRef(null);

  const { streamLeen, isStreaming, error, currentStep: streamStep, sessionId, cancelStream } = useLeenStream();

  const runStream = useCallback(async (request, onResult) => {
    let finalResult = null;
    const sid = await streamLeen(request, (event) => {
      if (event.event_type === 'result' && event.result) finalResult = event.result;
      if (event.event_type === 'graph_completed' && event.final_state) finalResult = finalResult || event.final_state;
      if (event.event_type === 'graph_error') setPlannerSummary((p) => ({ ...p, error: event.error }));
    });
    if (sid) sessionIdRef.current = sid;
    console.log('[FinalFeatureBuilder] runStream done:', { finalResult, sid, request });
    onResult(finalResult, sid);
  }, [streamLeen]);

  const handleStartOrResume = useCallback(async (resumePayload = null) => {
    const goal = queryInput.trim();
    if (!goal && !resumePayload) return;

    if (!resumePayload) {
      setStreamingMessages((prev) => [...prev, { role: 'user', content: goal }]);
      setPlannerSummary(null);
      setInterruptPayload(null);
      setLeenStep(0);
    }

    try {
      await runStream(
        resumePayload ? { session_id: sessionIdRef.current || sessionId, resume: resumePayload } : { goal },
        async (finalResult, sid) => {
          const s = sid || sessionIdRef.current || sessionId;
          console.log('[FinalFeatureBuilder] onResult:', { finalResult, sid, sessionIdRef: sessionIdRef.current });
          if (s) {
            try {
              const stateRes = await getLeenState(s);
              console.log('[FinalFeatureBuilder] getLeenState:', stateRes);
              const interruptType = stateRes.interrupt_type || '';
              const payload = stateRes.interrupt_payload || {};
              setStateSnapshot(stateRes.state_snapshot || {});
              if (interruptType) {
                console.log('[FinalFeatureBuilder] At interrupt:', interruptType, payload);
                setInterruptPayload(payload);
                const stepIdx = LEEN_STEPS.findIndex((st) => st.key === interruptType);
                setLeenStep(stepIdx >= 0 ? stepIdx + 1 : 1);
                setActiveTab('conversation');
              } else {
                console.log('[FinalFeatureBuilder] Completed, showing summary');
                const qa = (finalResult?.qa_response || stateRes.qa_response || '').trim();
                const summary = finalResult?.planner_summary || {};
                const execTables = finalResult?.execution_tables || summary?.execution_tables || [];
                setPlannerSummary({
                  qaResponse: qa,
                  plannerSummary: summary,
                  executionTables: execTables,
                  deliveryOutcomes: finalResult?.delivery_outcomes,
                });
                setStreamingMessages((prev) => [
                  ...prev,
                  { role: 'assistant', content: qa ? 'Here is your planner summary:' : 'Build complete.', hasKnowledge: true, suggestions: [] },
                ]);
                setLeenStep(5);
                setInterruptPayload(null);
                setActiveTab(qa ? 'summary' : 'conversation');
              }
            } catch (err) {
              console.log('[FinalFeatureBuilder] getLeenState error:', err);
              if (finalResult) {
                const qa = (finalResult.qa_response || '').trim();
                const summary = finalResult.planner_summary || {};
                const execTables = finalResult.execution_tables || summary.execution_tables || [];
                setPlannerSummary({
                  qaResponse: qa,
                  plannerSummary: summary,
                  executionTables: execTables,
                  deliveryOutcomes: finalResult.delivery_outcomes,
                });
                setLeenStep(5);
                setInterruptPayload(null);
                setActiveTab('summary');
              } else {
                setInterruptPayload({ message: 'Unable to load state. You may need to retry.' });
                setLeenStep(1);
              }
            }
          } else if (finalResult) {
            const qa = (finalResult.qa_response || '').trim();
            const summary = finalResult.planner_summary || {};
            const execTables = finalResult.execution_tables || summary.execution_tables || [];
            setPlannerSummary({
              qaResponse: qa,
              plannerSummary: summary,
              executionTables: execTables,
              deliveryOutcomes: finalResult.delivery_outcomes,
            });
            setLeenStep(5);
            setInterruptPayload(null);
            setActiveTab('summary');
          }
        }
      );
    } catch (e) {
      setPlannerSummary((p) => ({ ...p, error: e.message }));
    }
  }, [queryInput, sessionId, runStream]);

  const handleResume = useCallback((resumePayload) => {
    setSelection({});
    handleStartOrResume(resumePayload);
  }, [handleStartOrResume]);

  // Default selection to "all" when Step 2 payload loads
  useEffect(() => {
    if (!interruptPayload || leenStep !== 2) return;
    const caps = interruptPayload.applicable_data_capabilities || [];
    const policyMetrics = interruptPayload.policy_metrics || [];
    setSelection((prev) => {
      const capDefault = caps.length && !prev.selected_capability_ids?.length ? caps.map((_, i) => String(i)) : prev.selected_capability_ids;
      const pmDefault = policyMetrics.length && !prev.selected_policy_metric_ids?.length ? policyMetrics.map((_, i) => String(i)) : prev.selected_policy_metric_ids;
      if (capDefault !== prev.selected_capability_ids || pmDefault !== prev.selected_policy_metric_ids) {
        return { ...prev, selected_capability_ids: capDefault || prev.selected_capability_ids, selected_policy_metric_ids: pmDefault || prev.selected_policy_metric_ids };
      }
      return prev;
    });
  }, [interruptPayload, leenStep]);

  const workflowSteps = LEEN_STEPS.map((s, i) => ({
    ...s,
    status: leenStep > s.id ? 'completed' : leenStep === s.id ? 'current' : 'pending',
  }));

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

  const completionPercentage = leenStep === 5 ? 100 : leenStep * 25;

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
              className={`flex items-center gap-2 ${
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

  const StepSelectionPanel = () => {
    if (leenStep === 5) return null;
    if (!interruptPayload && leenStep >= 1 && leenStep <= 4) {
      return (
        <div className="mt-6 bg-amber-50 border border-amber-200 rounded-lg p-4">
          <p className="text-sm text-amber-800">Loading step options... If this persists, the backend may not be running on port 8040.</p>
        </div>
      );
    }
    if (!interruptPayload) return null;

    const handleSubmit = () => {
      if (leenStep === 1) {
        const sources = interruptPayload.available_datasources || interruptPayload.source_categories || [];
        const defaultIds = sources.length ? sources.slice(0, 3).map((d) => d.id || d.name) : ['snyk', 'qualys', 'wiz'];
        const payload = {
          selected_source_ids: selection.selected_source_ids?.length ? selection.selected_source_ids : defaultIds,
          selected_playbook_id: selection.selected_playbook_id,
          selected_compliance_framework: selection.selected_compliance_framework || 'SOC2',
        };
        handleResume(payload);
      } else if (leenStep === 2) {
        const caps = interruptPayload.applicable_data_capabilities || [];
        const policyMetrics = interruptPayload.policy_metrics || [];
        const payload = {
          selected_capability_ids: selection.selected_capability_ids?.length ? selection.selected_capability_ids : caps.map((_, i) => String(i)),
          selected_policy_metric_ids: selection.selected_policy_metric_ids?.length ? selection.selected_policy_metric_ids : policyMetrics.map((_, i) => String(i)),
        };
        handleResume(payload);
      } else if (leenStep === 3) {
        const models = interruptPayload.available_data_models || [];
        const payload = {
          selected_datamodel_ids: selection.selected_datamodel_ids || models.map((m) => m.model_id || m.name).filter(Boolean).slice(0, 5),
        };
        handleResume(payload);
      } else if (leenStep === 4) {
        const buckets = interruptPayload.feature_buckets || [];
        const payload = {
          action: 'continue',
          selected_bucket_ids_for_build: selection.selected_bucket_ids_for_build || buckets.slice(0, 3),
        };
        handleResume(payload);
      }
    };

    return (
      <div className="bg-white rounded-lg border-2 border-blue-200 p-6 shadow-sm mb-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Database className="w-5 h-5 text-blue-600" />
          Step {leenStep}: {LEEN_STEPS[leenStep - 1]?.name}
        </h3>
        <p className="text-sm text-gray-600 mb-4">{interruptPayload.message || `Complete step ${leenStep} to continue.`}</p>

        {leenStep === 1 && (
          <div className="space-y-3">
            {(interruptPayload.available_datasources || interruptPayload.source_categories || []).map((ds) => (
              <label key={ds.id || ds.name} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={(selection.selected_source_ids || []).includes(ds.id || ds.name)}
                  onChange={(e) => {
                    const ids = selection.selected_source_ids || [];
                    const id = ds.id || ds.name;
                    setSelection((s) => ({
                      ...s,
                      selected_source_ids: e.target.checked ? [...ids, id] : ids.filter((x) => x !== id),
                    }));
                  }}
                />
                <span>{ds.name || ds.id}</span>
              </label>
            ))}
          </div>
        )}
        {leenStep === 2 && (
          <div className="space-y-4">
            {((interruptPayload.policy_metrics || []).length > 0) && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                <h4 className="text-sm font-semibold text-amber-900 mb-2 flex items-center gap-2">
                  <Shield className="w-4 h-4" />
                  {interruptPayload.selected_compliance_framework || 'SOC2'} Controls & Risks
                </h4>
                <p className="text-xs text-amber-700 mb-2">Select which controls/risks to include (used for data model fetching and metric planning)</p>
                <div className="space-y-2 max-h-32 overflow-y-auto">
                  {(interruptPayload.policy_metrics || []).map((pm, i) => (
                    <label key={i} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={(selection.selected_policy_metric_ids || []).includes(String(i))}
                        onChange={(e) => {
                          const ids = selection.selected_policy_metric_ids || [];
                          setSelection((s) => ({
                            ...s,
                            selected_policy_metric_ids: e.target.checked ? [...ids, String(i)] : ids.filter((x) => x !== String(i)),
                          }));
                        }}
                      />
                      <span className="text-sm text-amber-800">
                        {pm.name || pm.description || 'Control'}{pm.description && pm.name ? `: ${pm.description}` : ''}
                      </span>
                    </label>
                  ))}
                </div>
              </div>
            )}
            {((interruptPayload.policy_mapped_capabilities || []).length > 0) && (
              <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                <h4 className="text-sm font-semibold text-green-900 mb-2 flex items-center gap-2">
                  <Database className="w-4 h-4" />
                  Policy-Mapped Connector Capabilities
                </h4>
                <p className="text-xs text-green-700 mb-2">Capabilities from each connector that support the identified controls/risks</p>
                <ul className="text-sm text-green-800 space-y-1 max-h-32 overflow-y-auto">
                  {(interruptPayload.policy_mapped_capabilities || []).map((pmc, i) => (
                    <li key={i}>
                      • {pmc.capability || pmc.description}
                      {pmc.connector && <span className="text-green-600 ml-1">({pmc.connector})</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Data Capabilities</h4>
              <p className="text-xs text-gray-500 mb-2">Select from connector capabilities</p>
              <div className="space-y-3">
                {(interruptPayload.applicable_data_capabilities || []).map((cap, i) => (
                  <label key={i} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={(selection.selected_capability_ids || []).includes(String(i))}
                      onChange={(e) => {
                        const ids = selection.selected_capability_ids || [];
                        setSelection((s) => ({
                          ...s,
                          selected_capability_ids: e.target.checked ? [...ids, String(i)] : ids.filter((x) => x !== String(i)),
                        }));
                      }}
                    />
                    <span>
                      {cap.capability || cap.name || cap.description || `Capability ${i + 1}`}
                      {cap.connector && (
                        <span className="text-gray-500 text-xs ml-1">({cap.connector})</span>
                      )}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}
        {leenStep === 3 && (
          <div className="space-y-4">
            {((interruptPayload.policy_metrics || []).length > 0 || (interruptPayload.evaluated_metrics || []).length > 0) && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                <h4 className="text-sm font-semibold text-amber-900 mb-2 flex items-center gap-2">
                  <Shield className="w-4 h-4" />
                  {interruptPayload.selected_compliance_framework || 'SOC2'} Controls & Risks
                </h4>
                <ul className="text-sm text-amber-800 space-y-1 max-h-32 overflow-y-auto">
                  {(interruptPayload.policy_metrics || []).map((pm, i) => (
                    <li key={i}>• {pm.name || pm.description || 'Control'}{pm.description && pm.name ? `: ${pm.description}` : ''}</li>
                  ))}
                  {(interruptPayload.evaluated_metrics || []).filter((em) => em?.supported !== false).map((em, i) => (
                    <li key={`eval-${i}`}>• {em.metric_name || em.name || 'Metric'}</li>
                  ))}
                </ul>
              </div>
            )}
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Data Models</h4>
              <div className="space-y-3">
                {(interruptPayload.available_data_models || []).map((dm) => (
                  <label key={dm.model_id || dm.name} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={(selection.selected_datamodel_ids || []).includes(dm.model_id || dm.name)}
                      onChange={(e) => {
                        const ids = selection.selected_datamodel_ids || [];
                        const id = dm.model_id || dm.name;
                        setSelection((s) => ({
                          ...s,
                          selected_datamodel_ids: e.target.checked ? [...ids, id] : ids.filter((x) => x !== id),
                        }));
                      }}
                    />
                    <span>[{dm.source}] {dm.name || dm.model_id}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}
        {leenStep === 4 && (
          <div className="space-y-3">
            {(interruptPayload.feature_buckets || []).map((b) => (
              <label key={b} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={(selection.selected_bucket_ids_for_build || []).includes(b)}
                  onChange={(e) => {
                    const ids = selection.selected_bucket_ids_for_build || [];
                    setSelection((s) => ({
                      ...s,
                      selected_bucket_ids_for_build: e.target.checked ? [...ids, b] : ids.filter((x) => x !== b),
                    }));
                  }}
                />
                <span>{b}</span>
              </label>
            ))}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={isStreaming}
          className="mt-6 flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
        >
          {isStreaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <ChevronRight className="w-4 h-4" />}
          Continue
        </button>
      </div>
    );
  };

  const displayMessages = streamingMessages.length > 0
    ? streamingMessages.map((m, i) => ({
        id: `stream-${i}`,
        role: m.role,
        content: m.content || '',
        suggestions: m.suggestions,
        hasKnowledge: m.hasKnowledge,
      }))
    : messages;

  const ConversationView = () => (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto">
          {displayMessages.map((message, idx) => (
            message.role === 'user' ? (
              <div key={message.id || idx} className="flex justify-end mb-6">
                <div className="bg-blue-50 rounded-lg border border-blue-200 px-4 py-3 max-w-[80%]">
                  <p className="text-sm text-gray-800">{message.content}</p>
                </div>
              </div>
            ) : (
              <AssistantMessage key={message.id || idx} message={message} />
            )
          ))}
          {isStreaming && (
            <div className="flex gap-3 mb-6">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                <Loader2 className="w-5 h-5 text-white animate-spin" />
              </div>
              <div className="flex-1 bg-white rounded-lg border border-gray-200 p-4">
                <p className="text-sm text-gray-600">
                  {streamStep ? `Processing: ${streamStep}` : 'Building features...'}
                </p>
              </div>
            </div>
          )}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
              {error}
            </div>
          )}
          <StepSelectionPanel />
          {(plannerSummary?.qaResponse || plannerSummary?.error || plannerSummary?.executionTables?.length) && (
            <div className="mt-6 bg-white rounded-lg border-2 border-blue-200 p-6 shadow-sm">
              <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5 text-blue-600" />
                Planner Summary
              </h3>
              {plannerSummary.error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                  {plannerSummary.error}
                </div>
              )}
              {plannerSummary.qaResponse && (
                <div className="prose prose-sm max-w-none text-gray-800">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {plannerSummary.qaResponse}
                  </ReactMarkdown>
                </div>
              )}
              {plannerSummary.executionTables?.length > 0 && (
                <div className="mt-6 pt-4 border-t border-gray-200">
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Tables to Retrieve</h4>
                  <ul className="text-sm text-gray-600 space-y-1">
                    {plannerSummary.executionTables.slice(0, 10).map((t, i) => (
                      <li key={i}>• {t.table || t.name} ({t.source || ''}) – {t.metrics_using?.length || 0} metrics</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-gray-200 bg-white p-6">
        <div className="max-w-4xl mx-auto">
          {(leenStep === 0 || leenStep === 5) && (
            <>
              <div className="bg-white rounded-lg border-2 border-gray-200 shadow-sm hover:border-blue-300 transition-all">
                <div className="p-4">
                  <div className="flex items-start gap-3">
                    <MessageSquare className="w-5 h-5 text-gray-400 mt-1" />
                    <div className="flex-1">
                      <textarea
                        value={queryInput}
                        onChange={(e) => setQueryInput(e.target.value)}
                        placeholder="e.g., Build VM report with open/closed counts and MTTR"
                        className="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none text-sm"
                        rows={3}
                        disabled={isStreaming}
                        autoComplete="off"
                        aria-label="Goal for VM report or Asset Inventory"
                      />
                      <div className="mt-2 flex items-center justify-between">
                        <span className="text-xs text-gray-500">4-step flow: sources → capabilities → models → build</span>
                        <div className="flex gap-2">
                          {isStreaming && (
                            <button
                              onClick={() => cancelStream()}
                              className="flex items-center gap-2 px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200"
                            >
                              Cancel
                            </button>
                          )}
                          {leenStep === 5 && !isStreaming && (
                            <button
                              onClick={() => { setLeenStep(0); setPlannerSummary(null); setStreamingMessages([]); setQueryInput(''); sessionIdRef.current = null; }}
                              className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
                            >
                              Start Over
                            </button>
                          )}
                          <button
                            onClick={() => handleStartOrResume()}
                            disabled={isStreaming || !queryInput.trim()}
                            className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {isStreaming ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <PlayCircle className="w-4 h-4" />
                            )}
                            <span className="font-medium">{isStreaming ? 'Processing...' : 'Start'}</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="text-center text-sm text-gray-500 mt-4">
                💡 Step 1: Set goal → Step 2: Select sources → Step 3: Capabilities → Step 4: Data models → Step 5: Confirm build
              </div>
            </>
          )}
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
              {(plannerSummary?.qaResponse || plannerSummary?.error || plannerSummary?.executionTables?.length) && (
                <button
                  onClick={() => setActiveTab('summary')}
                  className={`flex items-center gap-2 px-6 py-3 text-sm font-medium transition-all ${
                    activeTab === 'summary'
                      ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  <FileText className="w-4 h-4" />
                  Summary
                </button>
              )}
            </div>
          </div>

          {/* Pipeline Progress */}
          <WorkflowProgressBar />
        </div>

        {/* Tab Content */}
        {activeTab === 'conversation' && <ConversationView />}
        {activeTab === 'knowledge' && <KnowledgeView />}
        {activeTab === 'summary' && plannerSummary && (plannerSummary.qaResponse || plannerSummary.error || plannerSummary.executionTables?.length) && (
          <div className="flex-1 overflow-y-auto p-6 bg-gray-50">
            <div className="max-w-4xl mx-auto bg-white rounded-lg border-2 border-gray-200 p-8 shadow-sm">
              <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                <FileText className="w-6 h-6 text-blue-600" />
                Planner Summary
              </h2>
              {plannerSummary.error && (
                <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
                  {plannerSummary.error}
                </div>
              )}
              {plannerSummary.qaResponse && (
                <div className="prose prose-lg max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {plannerSummary.qaResponse}
                  </ReactMarkdown>
                </div>
              )}
              {plannerSummary.executionTables?.length > 0 && (
                <div className="mt-8 pt-6 border-t border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Tables to Retrieve</h3>
                  <ul className="space-y-2 text-gray-700">
                    {plannerSummary.executionTables.map((t, i) => (
                      <li key={i} className="flex items-center gap-2">
                        <Database className="w-4 h-4 text-blue-600" />
                        <span className="font-medium">{t.table || t.name}</span>
                        <span className="text-gray-500">({t.source || 'unknown'})</span>
                        <span className="text-sm text-gray-600">– {t.metrics_using?.length || 0} metrics</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {plannerSummary.plannerSummary?.data_models_summary?.length > 0 && (
                <div className="mt-8 pt-6 border-t border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Data Models</h3>
                  <ul className="space-y-2 text-gray-700">
                    {plannerSummary.plannerSummary.data_models_summary.map((dm, i) => (
                      <li key={i}>
                        <span className="font-medium">[{dm.source}] {dm.name || dm.model_id}</span>
                        <span className="text-sm text-gray-600"> – {dm.metrics?.length || 0} metrics</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Right Sidebar - Stage Responses (Markdown for validation) */}
      <div className="w-[420px] bg-white border-l border-gray-200 overflow-y-auto flex-shrink-0">
        <div className="p-4">
          <h2 className="text-lg font-bold text-gray-900 mb-3">Stage Responses</h2>
          <p className="text-xs text-gray-500 mb-4">Full output of each planner stage for validation</p>
          {stateSnapshot && Object.keys(stateSnapshot).length > 0 ? (
            <div className="prose prose-sm max-w-none text-gray-800">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {[
                  stateSnapshot.goal && `## Goal\n${stateSnapshot.goal}`,
                  (stateSnapshot.action_plan?.length > 0) && `## 1. Action Plan\n${stateSnapshot.action_plan.map((s, i) => `${i + 1}. ${s}`).join('\n')}\n\n**Reasoning:** ${stateSnapshot.reasoning_plan || '(none)'}`,
                  (stateSnapshot.applicable_data_capabilities?.length > 0) && `## 2. Applicable Data Capabilities\n${stateSnapshot.applicable_data_capabilities.map((c) => `- **${c.connector}**: ${c.capability}`).join('\n')}`,
                  (stateSnapshot.policy_metrics?.length > 0) && `## 3. Policy Metrics (SOC2)\n${stateSnapshot.policy_metrics.map((m) => `- ${m.name || m.description || 'Control'}${m.description && m.name ? `: ${m.description}` : ''}`).join('\n')}\n\n**Reasoning:** ${stateSnapshot.policy_retrieval_reasoning || '(none)'}`,
                  (stateSnapshot.policy_mapped_capabilities?.length > 0) && `## 4. Policy-Mapped Capabilities\n${stateSnapshot.policy_mapped_capabilities.map((p) => `- **${p.connector}**: ${p.capability || p.description}`).join('\n')}`,
                  (stateSnapshot.data_capability_metrics?.length > 0) && `## 5. Data Capability Metrics\n${stateSnapshot.data_capability_metrics.map((m) => `- **${m.name}**: ${(m.description || '').slice(0, 100)}`).join('\n')}\n\n**Reasoning:** ${stateSnapshot.data_capability_reasoning || '(none)'}`,
                  (stateSnapshot.scored_metrics?.length > 0) && `## 6. Scored Metrics\n${stateSnapshot.scored_metrics.map((m) => `- ${m.metric_name || m.name} (score: ${m.score})`).join('\n')}\n\n**Reasoning:** ${stateSnapshot.grade_metrics_reasoning || '(none)'}`,
                  (stateSnapshot.evaluated_metrics?.length > 0) && `## 7. Evaluated Metrics\n${stateSnapshot.evaluated_metrics.map((m) => {
                    const name = m.metric_name || m.name;
                    const desc = m.description ? `\n  ${m.description}` : '';
                    const status = m.supported ? 'supported' : 'not supported';
                    const tables = m.source_tables?.length ? ` [tables: ${m.source_tables.join(', ')}]` : '';
                    return `- **${name}** (${status})${tables}${desc}`;
                  }).join('\n')}\n\n**Reasoning:** ${stateSnapshot.evaluate_metrics_reasoning || '(none)'}`,
                  (stateSnapshot.feature_buckets?.length > 0) && `## 8. Feature Buckets\n${stateSnapshot.feature_buckets.join(', ')}\n\n**Reasoning:** ${stateSnapshot.feature_bucket_thinking || '(none)'}\n\n**Next steps:** ${stateSnapshot.feature_bucket_next_steps || '(none)'}`,
                  (stateSnapshot.agent_thinking?.length > 0) && `## Agent Thinking\n${stateSnapshot.agent_thinking.map((a) => `### ${a.agent}\n${a.thinking}`).join('\n\n')}`,
                  stateSnapshot.qa_response && `## QA Response\n${stateSnapshot.qa_response}`,
                  (stateSnapshot.execution_tables?.length > 0) && `## Execution Tables\n${stateSnapshot.execution_tables.map((t) => `- **${t.table}** (${t.source}): ${(t.metrics_using || []).join(', ')}`).join('\n')}`,
                ].filter(Boolean).join('\n\n---\n\n') || 'No stage data yet. Run the planner to see outputs.'}
              </ReactMarkdown>
            </div>
          ) : (
            <div className="text-sm text-gray-500 italic py-8">
              No state yet. Start a run to see stage responses.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default FinalFeatureBuilder;
