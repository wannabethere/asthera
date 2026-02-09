import React, { useMemo, useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  MessageCircle,
  Send,
  Database,
  Boxes,
  SplitSquareVertical,
  Sigma,
  Search,
  Sparkles,
  ArrowLeft,
  X,
  ChevronRight,
} from "lucide-react";

// Import centralized registry data
import {
  REGISTRY,
  EDGE_DEFINITIONS,
  MOCK_PREVIEW_ROWS,
  typeBadge,
} from "./mockRegistry";

// -----------------------------
// Helper functions
// -----------------------------

function getLayerIcon(layer) {
  switch (layer) {
    case "source":
      return Database;
    case "entity":
      return Boxes;
    case "feature":
      return SplitSquareVertical;
    case "metric":
      return Sigma;
    default:
      return Sparkles;
  }
}

function getLayerColor(layer) {
  switch (layer) {
    case "source":
      return "border-blue-500/50 bg-blue-500/10";
    case "entity":
      return "border-purple-500/50 bg-purple-500/10";
    case "feature":
      return "border-green-500/50 bg-green-500/10";
    case "metric":
      return "border-amber-500/50 bg-amber-500/10";
    default:
      return "border-zinc-700 bg-zinc-800/50";
  }
}

// -----------------------------
// Build nodes and edges
// -----------------------------
function buildNodesAndEdges() {
  const nodes = [];
  const edges = [];

  // Add sources
  REGISTRY.sources.forEach((s) => {
    nodes.push({
      id: s.id,
      layer: "source",
      title: s.label,
      subtitle: "System of record",
      badge: "SOURCE",
      tags: ["cornerstone"],
    });
  });

  // Add entities
  REGISTRY.entities.forEach((e) => {
    nodes.push({
      id: e.id,
      layer: "entity",
      title: e.label,
      subtitle: "Canonical entity",
      badge: "ENTITY",
      meta: ["cornerstone.learn.*"],
    });
  });

  // Add features
  REGISTRY.categories.forEach((c) => {
    c.features.forEach((f) => {
      nodes.push({
        id: f.id,
        layer: "feature",
        title: f.label,
        subtitle: c.label,
        badge: f.modelBased ? "ML" : typeBadge(f.type),
        question: f.question,
        description: f.description,
        derivedFrom: f.derivedFrom,
        modelBased: !!f.modelBased,
      });
    });
  });

  // Add metrics
  REGISTRY.metrics.forEach((m) => {
    nodes.push({
      id: m.id,
      layer: "metric",
      title: m.label,
      subtitle: `${m.type} • ${m.dashboard}`,
      badge: m.type,
      question: m.question,
      description: m.description,
      required_entities: m.required_entities,
      aggregation_levels: m.aggregation_levels,
      feature_patterns: m.feature_patterns,
      meta: m.schemas,
    });
  });

  // Add edges: sources -> entities
  Object.entries(EDGE_DEFINITIONS.sources_to_entities).forEach(([src, ents]) => {
    ents.forEach((e) => {
      edges.push({ source: src, target: e });
    });
  });

  // Add edges: entities -> features
  Object.entries(EDGE_DEFINITIONS.entities_to_features).forEach(([ent, feats]) => {
    feats.forEach((f) => {
      edges.push({ source: ent, target: f });
    });
  });

  // Add edges: features -> metrics
  Object.entries(EDGE_DEFINITIONS.features_to_metrics).forEach(([met, feats]) => {
    feats.forEach((f) => {
      edges.push({ source: f, target: met });
    });
  });

  return { nodes, edges };
}

// -----------------------------
// Node Card Component
// -----------------------------
function NodeCard({ node, isSelected, isConnected, onClick, nodeRef }) {
  const Icon = getLayerIcon(node.layer);
  const colorClass = getLayerColor(node.layer);
  const opacity = isSelected ? "opacity-100" : isConnected ? "opacity-100" : "opacity-40";

  return (
    <button
      ref={nodeRef}
      data-node-id={node.id}
      onClick={() => onClick(node)}
      className={`w-full text-left p-3 rounded-xl border ${colorClass} ${opacity} 
        hover:opacity-100 hover:scale-[1.02] transition-all duration-200
        ${isSelected ? "ring-2 ring-white/30" : ""}`}
    >
      <div className="flex items-start gap-2">
        <Icon className="w-4 h-4 text-zinc-300 mt-0.5 flex-shrink-0" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold text-zinc-100 truncate">{node.title}</span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-300 flex-shrink-0">
              {node.badge}
            </span>
          </div>
          {node.subtitle && (
            <div className="text-xs text-zinc-400 mt-0.5 truncate">{node.subtitle}</div>
          )}
        </div>
      </div>
    </button>
  );
}

// -----------------------------
// Edge Lines SVG Component
// -----------------------------
function EdgeLines({ edges, nodePositions, selectedId, connectedIds }) {
  if (!nodePositions || Object.keys(nodePositions).length === 0) return null;

  return (
    <svg className="absolute inset-0 pointer-events-none" style={{ zIndex: 0 }}>
      <defs>
        <linearGradient id="edge-gradient-default" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="rgba(113, 113, 122, 0.3)" />
          <stop offset="100%" stopColor="rgba(113, 113, 122, 0.15)" />
        </linearGradient>
        <linearGradient id="edge-gradient-active" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="rgba(59, 130, 246, 0.6)" />
          <stop offset="100%" stopColor="rgba(168, 85, 247, 0.6)" />
        </linearGradient>
      </defs>
      {edges.map((edge, idx) => {
        const from = nodePositions[edge.source];
        const to = nodePositions[edge.target];
        if (!from || !to) return null;

        const isActive = 
          selectedId === edge.source || 
          selectedId === edge.target ||
          connectedIds.has(edge.source) || 
          connectedIds.has(edge.target);

        // Calculate curve control points
        const startX = from.right;
        const startY = from.centerY;
        const endX = to.left;
        const endY = to.centerY;
        const midX = (startX + endX) / 2;

        const path = `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`;

        return (
          <path
            key={idx}
            d={path}
            fill="none"
            stroke={isActive ? "url(#edge-gradient-active)" : "url(#edge-gradient-default)"}
            strokeWidth={isActive ? 2 : 1}
            opacity={selectedId && !isActive ? 0.15 : isActive ? 1 : 0.4}
            className="transition-all duration-300"
          />
        );
      })}
    </svg>
  );
}

// -----------------------------
// Inspector Panel
// -----------------------------
function InspectorPanel({ node, onClose }) {
  const [activeTab, setActiveTab] = useState("about");

  if (!node) {
    return (
      <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-6">
        <h3 className="text-sm font-semibold text-zinc-100 mb-2">Inspector</h3>
        <p className="text-sm text-zinc-400">Click a node to see its details, lineage, and data preview.</p>
      </div>
    );
  }

  const Icon = getLayerIcon(node.layer);

  return (
    <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl overflow-hidden">
      <div className="p-4 border-b border-zinc-800">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-zinc-800 flex items-center justify-center">
              <Icon className="w-4 h-4 text-zinc-200" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-zinc-100">{node.title}</h3>
              {node.subtitle && <p className="text-xs text-zinc-400 mt-0.5">{node.subtitle}</p>}
            </div>
          </div>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-zinc-800">
        {["about", "lineage", "data"].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 px-4 py-2 text-xs font-medium transition-colors
              ${activeTab === tab ? "text-zinc-100 bg-zinc-800" : "text-zinc-400 hover:text-zinc-200"}`}
          >
            {tab === "about" ? "What is this?" : tab === "lineage" ? "Lineage" : "Data Preview"}
          </button>
        ))}
      </div>

      <div className="p-4 max-h-[400px] overflow-auto">
        {activeTab === "about" && (
          <div className="space-y-4">
            {node.question && (
              <div>
                <div className="text-xs text-zinc-500 mb-1">Question</div>
                <div className="text-sm text-zinc-100">{node.question}</div>
              </div>
            )}
            {node.description && (
              <div>
                <div className="text-xs text-zinc-500 mb-1">Description</div>
                <div className="text-sm text-zinc-100">{node.description}</div>
              </div>
            )}
            {node.derivedFrom?.length > 0 && (
              <div>
                <div className="text-xs text-zinc-500 mb-2">Derived From</div>
                <div className="flex flex-wrap gap-2">
                  {node.derivedFrom.map((d) => (
                    <span key={d} className="text-xs px-2 py-1 rounded-full bg-zinc-800 text-zinc-200">
                      {d}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {node.modelBased && (
              <div className="p-3 rounded-xl border border-zinc-700 bg-zinc-800/50">
                <div className="flex items-center gap-2 text-sm text-zinc-100">
                  <Sparkles className="w-4 h-4" />
                  Model-based output
                </div>
                <p className="text-xs text-zinc-400 mt-1">
                  This is an ML prediction. Treat as a probabilistic estimate.
                </p>
              </div>
            )}
          </div>
        )}

        {activeTab === "lineage" && (
          <div className="space-y-3">
            <div className="text-xs text-zinc-500">Lineage (simplified)</div>
            <pre className="text-xs text-zinc-300 bg-zinc-800/50 rounded-xl p-3 whitespace-pre-wrap">
              {makeLineageText(node)}
            </pre>
          </div>
        )}

        {activeTab === "data" && (
          <div className="space-y-3">
            <div className="text-xs text-zinc-500">Sample rows (mocked)</div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-zinc-700">
                    <th className="text-left p-2 text-zinc-400">employee_id</th>
                    <th className="text-left p-2 text-zinc-400">course</th>
                    <th className="text-left p-2 text-zinc-400">due_date</th>
                    <th className="text-left p-2 text-zinc-400">is_overdue</th>
                    <th className="text-left p-2 text-zinc-400">progress%</th>
                  </tr>
                </thead>
                <tbody>
                  {MOCK_PREVIEW_ROWS.map((r, i) => (
                    <tr key={i} className="border-b border-zinc-800">
                      <td className="p-2 text-zinc-200">{r.employee_id}</td>
                      <td className="p-2 text-zinc-200">{r.course}</td>
                      <td className="p-2 text-zinc-200">{r.due_date}</td>
                      <td className="p-2 text-zinc-200">{String(r.is_overdue)}</td>
                      <td className="p-2 text-zinc-200">{r.progress_percent}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function makeLineageText(node) {
  if (node.layer === "source") return `${node.title}`;
  if (node.layer === "entity") return `Sources\n  └─ (connected sources)\n\nEntity\n  └─ ${node.title}`;
  if (node.layer === "feature") {
    const df = (node.derivedFrom || []).map((x) => `  └─ ${x}`).join("\n");
    return `Upstream\n${df || "  └─ (unknown)"}\n\nFeature\n  └─ ${node.title}`;
  }
  if (node.layer === "metric") {
    const req = node.required_entities?.map((x) => `  └─ ${x}`).join("\n") || "";
    const pats = node.feature_patterns?.map((x) => `  └─ ${x}`).join("\n") || "";
    return `Required Entities\n${req}\n\nFeature Patterns\n${pats}\n\nMetric\n  └─ ${node.title}`;
  }
  return node.title;
}

// -----------------------------
// Chat Panel
// -----------------------------
function ChatPanel({ selectedNode }) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    {
      id: "m1",
      role: "assistant",
      text: "Ask me about any metric, feature, or data lineage. Example: 'Why is compliance_gap_count high for Sales?'",
    },
  ]);

  const contextHint = selectedNode
    ? `Context: ${selectedNode.layer} → ${selectedNode.title}`
    : "Context: None selected";

  function send() {
    const trimmed = input.trim();
    if (!trimmed) return;

    setMessages((m) => [...m, { id: `u-${Date.now()}`, role: "user", text: trimmed }]);
    setInput("");

    setTimeout(() => {
      const suggestion = selectedNode
        ? `I can explain how ${selectedNode.title} is computed, show sample rows, or trace upstream sources.`
        : "Select a node in the strategy map and I'll explain its lineage and data preview.";

      setMessages((m) => [
        ...m,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          text: `${suggestion}\n\nTry: "Show upstream features" or "Explain this metric".`,
        },
      ]);
    }, 350);
  }

  return (
    <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl overflow-hidden">
      <div className="p-3 border-b border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageCircle className="w-4 h-4 text-zinc-300" />
          <span className="text-sm font-medium text-zinc-100">Strategy Chat</span>
        </div>
        <span className="text-xs px-2 py-1 rounded-full bg-zinc-800 text-zinc-300">{contextHint}</span>
      </div>

      <div className="h-[200px] overflow-auto p-3 space-y-2">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`rounded-xl px-3 py-2 text-sm border ${
              m.role === "user"
                ? "bg-zinc-950/40 border-zinc-800 text-zinc-100 ml-8"
                : "bg-zinc-900 border-zinc-800 text-zinc-100 mr-8"
            }`}
          >
            <div className="text-[10px] text-zinc-400 mb-1">{m.role === "user" ? "You" : "Assistant"}</div>
            <div className="whitespace-pre-wrap leading-relaxed">{m.text}</div>
          </div>
        ))}
      </div>

      <div className="p-3 border-t border-zinc-800 flex items-center gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about lineage, metrics..."
          className="flex-1 px-3 py-2 text-sm bg-zinc-950/40 border border-zinc-800 rounded-xl text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button
          onClick={send}
          className="p-2 bg-zinc-800 hover:bg-zinc-700 rounded-xl transition-colors"
        >
          <Send className="w-4 h-4 text-zinc-100" />
        </button>
      </div>
    </div>
  );
}

// -----------------------------
// KPI Scorecard
// -----------------------------
function KpiScorecard({ selectedMetrics }) {
  if (!selectedMetrics.length) {
    return (
      <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl p-4">
        <h3 className="text-sm font-semibold text-zinc-100 mb-2">KPI Scorecard</h3>
        <p className="text-sm text-zinc-400">Select metrics from the map to build a scorecard.</p>
      </div>
    );
  }

  return (
    <div className="bg-zinc-900/80 border border-zinc-800 rounded-2xl overflow-hidden">
      <div className="p-3 border-b border-zinc-800">
        <h3 className="text-sm font-semibold text-zinc-100">KPI Scorecard</h3>
        <p className="text-xs text-zinc-400 mt-0.5">Aggregated KPIs (mock values)</p>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-zinc-800">
            <th className="text-left p-2 text-zinc-400">KPI</th>
            <th className="text-right p-2 text-zinc-400">Value</th>
            <th className="text-right p-2 text-zinc-400">Target</th>
            <th className="text-right p-2 text-zinc-400">Status</th>
          </tr>
        </thead>
        <tbody>
          {selectedMetrics.map((m) => (
            <tr key={m.id} className="border-b border-zinc-800">
              <td className="p-2 text-zinc-200 font-medium">{m.title}</td>
              <td className="p-2 text-zinc-200 text-right">
                {m.badge === "COUNT" ? Math.floor(Math.random() * 500 + 50) : `${(Math.random() * 100).toFixed(1)}%`}
              </td>
              <td className="p-2 text-zinc-200 text-right">
                {m.badge === "COUNT" ? "≤ 100" : "≥ 95%"}
              </td>
              <td className="p-2 text-right">
                <span
                  className={`inline-block w-2.5 h-2.5 rounded-full ${
                    Math.random() > 0.5 ? "bg-green-500" : "bg-amber-500"
                  }`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// -----------------------------
// Main Component
// -----------------------------
export default function HRComplianceStrategyMap() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [pinnedIds, setPinnedIds] = useState([]);
  const [nodePositions, setNodePositions] = useState({});
  const mapContainerRef = useRef(null);
  const nodeRefs = useRef({});

  const { nodes, edges } = useMemo(() => buildNodesAndEdges(), []);

  const selectedNode = useMemo(() => nodes.find((n) => n.id === selectedId), [nodes, selectedId]);

  const connectedIds = useMemo(() => {
    if (!selectedId) return new Set();
    const connected = new Set();
    edges.forEach((e) => {
      if (e.source === selectedId) connected.add(e.target);
      if (e.target === selectedId) connected.add(e.source);
    });
    return connected;
  }, [selectedId, edges]);

  // Calculate node positions for edge drawing
  const updateNodePositions = useCallback(() => {
    if (!mapContainerRef.current) return;
    
    const containerRect = mapContainerRef.current.getBoundingClientRect();
    const positions = {};
    
    Object.entries(nodeRefs.current).forEach(([id, el]) => {
      if (el) {
        const rect = el.getBoundingClientRect();
        positions[id] = {
          left: rect.left - containerRect.left,
          right: rect.right - containerRect.left,
          top: rect.top - containerRect.top,
          bottom: rect.bottom - containerRect.top,
          centerY: rect.top - containerRect.top + rect.height / 2,
        };
      }
    });
    
    setNodePositions(positions);
  }, []);

  // Update positions on mount and when nodes change
  useEffect(() => {
    const timer = setTimeout(updateNodePositions, 100);
    window.addEventListener('resize', updateNodePositions);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', updateNodePositions);
    };
  }, [updateNodePositions, nodes]);

  // Store ref for a node
  const setNodeRef = useCallback((id) => (el) => {
    nodeRefs.current[id] = el;
  }, []);

  const filteredNodes = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return nodes;
    return nodes.filter(
      (n) =>
        n.title.toLowerCase().includes(q) ||
        (n.subtitle || "").toLowerCase().includes(q) ||
        (n.question || "").toLowerCase().includes(q)
    );
  }, [nodes, search]);

  const pinnedMetrics = useMemo(
    () => nodes.filter((n) => pinnedIds.includes(n.id) && n.layer === "metric"),
    [nodes, pinnedIds]
  );

  const groupedNodes = useMemo(() => {
    const groups = {
      source: [],
      entity: [],
      feature: [],
      metric: [],
    };
    filteredNodes.forEach((n) => {
      if (groups[n.layer]) groups[n.layer].push(n);
    });
    return groups;
  }, [filteredNodes]);

  function handleNodeClick(node) {
    setSelectedId(node.id);
  }

  function togglePin(id) {
    setPinnedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="max-w-[1600px] mx-auto p-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <button
              onClick={() => navigate("/")}
              className="flex items-center gap-2 text-zinc-400 hover:text-zinc-100 mb-3 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="text-sm">Back to Home</span>
            </button>
            <h1 className="text-2xl font-semibold tracking-tight">HR Compliance Strategy Map</h1>
            <p className="text-sm text-zinc-400 mt-1">
              Sources → Entities → Features → Metrics. Click any node to inspect lineage and data.
            </p>
          </div>
          <div className="relative">
            <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search nodes..."
              className="pl-9 w-[300px] px-3 py-2 text-sm bg-zinc-900/80 border border-zinc-800 rounded-xl text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
          </div>
        </div>

        <div className="grid grid-cols-12 gap-4">
          {/* Strategy Map - 4 columns layout */}
          <div className="col-span-12 lg:col-span-8 bg-zinc-900/50 border border-zinc-800 rounded-2xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                Strategy Map
              </h2>
              <div className="flex items-center gap-4 text-xs text-zinc-400">
                <span className="flex items-center gap-1">
                  <Database className="w-3 h-3" /> Sources
                </span>
                <ChevronRight className="w-3 h-3" />
                <span className="flex items-center gap-1">
                  <Boxes className="w-3 h-3" /> Entities
                </span>
                <ChevronRight className="w-3 h-3" />
                <span className="flex items-center gap-1">
                  <SplitSquareVertical className="w-3 h-3" /> Features
                </span>
                <ChevronRight className="w-3 h-3" />
                <span className="flex items-center gap-1">
                  <Sigma className="w-3 h-3" /> Metrics
                </span>
              </div>
            </div>

            <div ref={mapContainerRef} className="relative grid grid-cols-4 gap-4">
              {/* Edge Lines SVG */}
              <EdgeLines 
                edges={edges} 
                nodePositions={nodePositions} 
                selectedId={selectedId}
                connectedIds={connectedIds}
              />

              {/* Sources */}
              <div className="space-y-2 relative z-10">
                <div className="text-xs text-zinc-500 font-medium mb-2">Sources ({groupedNodes.source.length})</div>
                {groupedNodes.source.map((n) => (
                  <NodeCard
                    key={n.id}
                    node={n}
                    nodeRef={setNodeRef(n.id)}
                    isSelected={selectedId === n.id}
                    isConnected={!selectedId || connectedIds.has(n.id)}
                    onClick={handleNodeClick}
                  />
                ))}
              </div>

              {/* Entities */}
              <div className="space-y-2 relative z-10">
                <div className="text-xs text-zinc-500 font-medium mb-2">Entities ({groupedNodes.entity.length})</div>
                {groupedNodes.entity.map((n) => (
                  <NodeCard
                    key={n.id}
                    node={n}
                    nodeRef={setNodeRef(n.id)}
                    isSelected={selectedId === n.id}
                    isConnected={!selectedId || connectedIds.has(n.id)}
                    onClick={handleNodeClick}
                  />
                ))}
              </div>

              {/* Features */}
              <div className="space-y-2 max-h-[600px] overflow-auto pr-2 relative z-10">
                <div className="text-xs text-zinc-500 font-medium mb-2 sticky top-0 bg-zinc-900/90 py-1">
                  Features ({groupedNodes.feature.length})
                </div>
                {groupedNodes.feature.map((n) => (
                  <NodeCard
                    key={n.id}
                    node={n}
                    nodeRef={setNodeRef(n.id)}
                    isSelected={selectedId === n.id}
                    isConnected={!selectedId || connectedIds.has(n.id)}
                    onClick={handleNodeClick}
                  />
                ))}
              </div>

              {/* Metrics */}
              <div className="space-y-2 relative z-10">
                <div className="text-xs text-zinc-500 font-medium mb-2">Metrics ({groupedNodes.metric.length})</div>
                {groupedNodes.metric.map((n) => (
                  <NodeCard
                    key={n.id}
                    node={n}
                    nodeRef={setNodeRef(n.id)}
                    isSelected={selectedId === n.id}
                    isConnected={!selectedId || connectedIds.has(n.id)}
                    onClick={handleNodeClick}
                  />
                ))}
              </div>
            </div>

            {/* Quick actions */}
            <div className="mt-4 pt-4 border-t border-zinc-800 flex items-center justify-between">
              <p className="text-xs text-zinc-400">
                Tip: select a metric (e.g., <span className="text-zinc-200">compliance_gap_count</span>) to see upstream
                features.
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setSelectedId("met.compliance_gap_count")}
                  className="px-3 py-1.5 text-xs bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors"
                >
                  Open compliance_gap_count
                </button>
                <button
                  onClick={() => setSelectedId("feat.is_overdue")}
                  className="px-3 py-1.5 text-xs bg-zinc-800 hover:bg-zinc-700 rounded-lg transition-colors"
                >
                  Open is_overdue
                </button>
              </div>
            </div>
          </div>

          {/* Right panel */}
          <div className="col-span-12 lg:col-span-4 space-y-4">
            <KpiScorecard selectedMetrics={pinnedMetrics} />

            <InspectorPanel
              node={selectedNode}
              onClose={() => setSelectedId(null)}
            />

            {selectedNode && selectedNode.layer === "metric" && (
              <button
                onClick={() => togglePin(selectedNode.id)}
                className={`w-full px-4 py-2 text-sm rounded-xl border transition-colors ${
                  pinnedIds.includes(selectedNode.id)
                    ? "bg-amber-500/20 border-amber-500/50 text-amber-200 hover:bg-amber-500/30"
                    : "bg-zinc-800 border-zinc-700 text-zinc-100 hover:bg-zinc-700"
                }`}
              >
                {pinnedIds.includes(selectedNode.id) ? "Remove from Scorecard" : "Add to Scorecard"}
              </button>
            )}

            <ChatPanel selectedNode={selectedNode} />
          </div>
        </div>

        <div className="mt-6 text-xs text-zinc-500 text-center">
          Front-end mock. Connect to backend for real data lineage and metrics.
        </div>
      </div>
    </div>
  );
}
