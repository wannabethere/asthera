import React, { useMemo, useState, useEffect } from "react";
import ReactFlow, { Background, Controls, MiniMap, Handle, Position } from "reactflow";
import "reactflow/dist/style.css";

import { makeScorecard } from "./scoreCardSchema";
import {
  REGISTRY,
  FEATURES_FLAT,
  EDGES,
  mockKpiValue,
  mockKpiTarget,
  mockKpiScore,
  getScoreColor,
  getObjectiveScore,
} from "./mockRegistry";

// -----------------------------
// Small UI helpers
// -----------------------------
function Btn({ children, onClick, disabled, variant = "secondary" }) {
  const base =
    "px-3 py-2 rounded-xl text-sm border border-zinc-800 transition";
  const styles =
    variant === "primary"
      ? "bg-zinc-800 text-zinc-100 hover:bg-zinc-700"
      : "bg-zinc-900 text-zinc-200 hover:bg-zinc-800";
  return (
    <button className={`${base} ${styles} ${disabled ? "opacity-50" : ""}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

function Input({ value, onChange, placeholder }) {
  return (
    <input
      className="w-full px-3 py-2 rounded-xl border border-zinc-800 bg-zinc-950/40 text-zinc-100 placeholder:text-zinc-500"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
    />
  );
}

function Chip({ children }) {
  return (
    <span className="text-[10px] px-2 py-1 rounded-full bg-zinc-800 text-zinc-200">
      {children}
    </span>
  );
}

// -----------------------------
// ReactFlow Node
// -----------------------------
function CardNode({ data }) {
  return (
    <div className="min-w-[220px] rounded-2xl border border-zinc-800 bg-zinc-900/70 p-3">
      <Handle type="target" position={Position.Left} style={{ opacity: 0.6 }} />
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-zinc-100 truncate">{data.title}</div>
          <div className="mt-1 text-xs text-zinc-400 truncate">{data.subtitle}</div>
        </div>
        {data.badge ? <Chip>{data.badge}</Chip> : null}
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0.6 }} />
    </div>
  );
}
const nodeTypes = { card: CardNode };

// -----------------------------
// Build Graph
// -----------------------------
function buildGraph() {
  const nodes = [];
  const edges = [];

  const X = { src: 40, ent: 320, feat: 620, met: 950 };

  REGISTRY.sources.forEach((s, i) => {
    nodes.push({
      id: s.id,
      type: "card",
      position: { x: X.src, y: 60 + i * 130 },
      data: { layer: "source", title: s.label, subtitle: "Source", badge: "SOURCE" },
    });
  });

  REGISTRY.entities.forEach((e, i) => {
    nodes.push({
      id: e.id,
      type: "card",
      position: { x: X.ent, y: 60 + i * 160 },
      data: { layer: "entity", title: e.label, subtitle: "Entity", badge: "ENTITY" },
    });
  });

  FEATURES_FLAT.forEach((f, i) => {
    nodes.push({
      id: f.id,
      type: "card",
      position: { x: X.feat, y: 40 + i * 90 }, // Adjusted spacing for more features
      data: {
        layer: "feature",
        title: f.label,
        subtitle: f.category,
        badge: f.dataType,
        description: f.description,
        derivedFrom: f.derivedFrom,
      },
    });
  });

  REGISTRY.metrics.forEach((m, i) => {
    nodes.push({
      id: m.id,
      type: "card",
      position: { x: X.met, y: 120 + i * 200 },
      data: {
        layer: "metric",
        title: m.label,
        subtitle: `${m.metricType} • ${m.dashboardSection}`,
        badge: m.metricType,
        description: m.description,
      },
    });
  });

  EDGES.forEach(([a, b], i) => edges.push({ id: `e-${i}`, source: a, target: b, animated: true }));

  return { nodes, edges };
}

// -----------------------------
// Hierarchy Builder (McBig-style)
// - Objective = dashboardSection
// - KPI = each pinned metric
// - Sub-KPI = optionally pinned features (or feature deps of the metric)
// -----------------------------
function buildHierarchyFromPinned({ pinnedNodes, includeSubKpis = true }) {
  const pinnedById = new Map(pinnedNodes.map((n) => [n.id, n]));
  const pinnedMetrics = pinnedNodes.filter((n) => n.data.layer === "metric");

  // group metrics by dashboard section
  const bySection = new Map(); // section => metrics[]
  pinnedMetrics.forEach((m) => {
    const section = (m.data.subtitle.split("•")[1] || "Metrics").trim();
    if (!bySection.has(section)) bySection.set(section, []);
    bySection.get(section).push(m);
  });

  const objectives = [];
  for (const [section, metrics] of bySection.entries()) {
    const obj = {
      id: `obj.${slug(section)}`,
      title: section,
      kpis: metrics.map((m) => {
        const kpi = {
          id: `kpi.${slug(m.data.title)}`,
          nodeId: m.id,
          label: m.data.title,
          value: null,
          target: null,
          score: null,
          children: [],
        };

        if (includeSubKpis) {
          // Add sub-KPIs from metric dependencies if those features exist in graph
          const metricDef = REGISTRY.metrics.find((x) => x.id === m.id);
          const deps = metricDef?.dependsOnFeatures || [];
          kpi.children = deps
            .filter((fid) => pinnedById.has(fid)) // only if user pinned the feature
            .map((fid) => ({
              id: `sub.${slug(fid)}`,
              nodeId: fid,
              label: pinnedById.get(fid).data.title,
              value: null,
              target: null,
              score: null,
            }));
        }

        return kpi;
      }),
    };
    objectives.push(obj);
  }

  // Stable ordering
  objectives.sort((a, b) => a.title.localeCompare(b.title));
  objectives.forEach((o) => o.kpis.sort((a, b) => a.label.localeCompare(b.label)));

  return objectives;
}

function slug(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
}

// -----------------------------
// McBig-style KPI Table (indentation + collapsible objectives)
// Matches the scorecard image with colored score indicators
// -----------------------------
function HierarchicalKpiTable({ scorecard, onFocusNode }) {
  const [collapsed, setCollapsed] = useState(() => new Set());

  const objectives = scorecard?.hierarchy?.objectives || [];

  function toggle(objId) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(objId)) next.delete(objId);
      else next.add(objId);
      return next;
    });
  }

  return (
    <div className="rounded-2xl border border-zinc-700 overflow-hidden bg-zinc-900/80">
      {/* Header */}
      <div className="bg-zinc-800 px-4 py-2.5 flex items-center justify-between border-b border-zinc-700">
        <div className="text-sm font-semibold text-zinc-100">Objective/KPI</div>
        <div className="flex items-center gap-8 text-xs text-zinc-300">
          <span className="w-16 text-right">Value</span>
          <span className="w-16 text-right">Target</span>
          <span className="w-14 text-right">Score</span>
        </div>
      </div>

      <div className="divide-y divide-zinc-800">
        {objectives.length === 0 ? (
          <div className="p-4 text-sm text-zinc-400">
            Pin metrics (and optionally features) to populate this table.
          </div>
        ) : (
          objectives.map((obj) => {
            const isCollapsed = collapsed.has(obj.id);
            const objScore = getObjectiveScore(obj.kpis);
            
            return (
              <div key={obj.id}>
                {/* Objective header row - dark background like in image */}
                <div className="bg-zinc-800/80 px-4 py-2 flex items-center justify-between">
                  <button
                    onClick={() => toggle(obj.id)}
                    className="flex items-center gap-2 text-sm font-semibold text-zinc-100 hover:text-white"
                    title="Collapse/expand"
                  >
                    <span className="text-zinc-400 text-xs">
                      {isCollapsed ? "▶" : "▼"}
                    </span>
                    {obj.title}
                  </button>
                  <div className="flex items-center gap-8">
                    <span className="w-16" />
                    <span className="w-16" />
                    <span className="w-14 flex justify-end">
                      <span className={`inline-block h-3 w-3 rounded-full ${objScore.color}`} title={objScore.score} />
                    </span>
                  </div>
                </div>

                {/* KPI rows */}
                {!isCollapsed && (
                  <div className="divide-y divide-zinc-800/60">
                    {obj.kpis.map((kpi) => {
                      const score = mockKpiScore(kpi.nodeId);
                      const scoreColor = getScoreColor(score);
                      
                      return (
                        <div key={kpi.id}>
                          {/* KPI row - indented */}
                          <div className="px-4 py-2 flex items-center justify-between hover:bg-zinc-800/30">
                            <button
                              onClick={() => onFocusNode(kpi.nodeId)}
                              className="flex items-center gap-2 text-sm text-zinc-200 hover:text-white pl-6"
                              title="Focus on graph"
                            >
                              {kpi.label}
                            </button>
                            <div className="flex items-center gap-8 text-sm">
                              <span className="w-16 text-right text-zinc-200">{mockKpiValue(kpi.nodeId)}</span>
                              <span className="w-16 text-right text-zinc-300">{mockKpiTarget(kpi.nodeId)}</span>
                              <span className="w-14 flex justify-end">
                                <span className={`inline-block h-3 w-3 rounded-full ${scoreColor}`} title={score} />
                              </span>
                            </div>
                          </div>

                          {/* Sub-KPI rows (indent further) */}
                          {kpi.children?.map((sub) => (
                            <div 
                              key={sub.id} 
                              className="px-4 py-1.5 flex items-center justify-between bg-zinc-900/50 hover:bg-zinc-800/20"
                            >
                              <button
                                onClick={() => onFocusNode(sub.nodeId)}
                                className="flex items-center gap-2 text-xs text-zinc-400 hover:text-zinc-200 pl-12"
                                title="Focus on graph"
                              >
                                <span className="text-zinc-600">↳</span>
                                {sub.label}
                              </button>
                              <div className="flex items-center gap-8 text-xs">
                                <span className="w-16 text-right text-zinc-500">—</span>
                                <span className="w-16 text-right text-zinc-500">—</span>
                                <span className="w-14" />
                              </div>
                            </div>
                          ))}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

// Mock placeholder outputs imported from mockRegistry.js
// mockKpiValue, mockKpiTarget, mockKpiScore

// -----------------------------
// Saved Scorecards (localStorage)
// -----------------------------
const LS_KEY = "hr_compliance_scorecards_v1";

function loadSavedScorecards() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveScorecards(list) {
  localStorage.setItem(LS_KEY, JSON.stringify(list));
}

// -----------------------------
// Main
// -----------------------------
export default function HRComplianceStrategyMapMock() {
  const initial = useMemo(() => buildGraph(), []);
  const [nodes] = useState(initial.nodes);
  const [edges] = useState(initial.edges);

  const [activeId, setActiveId] = useState(null);
  const [pinnedIds, setPinnedIds] = useState([]);

  // Scorecard management
  const [saved, setSaved] = useState([]);
  const [scorecardName, setScorecardName] = useState("Audit Readiness – HR Compliance");
  const [scorecardDesc, setScorecardDesc] = useState("Mock scorecard built from strategy map selections.");
  const [importText, setImportText] = useState("");

  useEffect(() => {
    setSaved(loadSavedScorecards());
  }, []);

  const activeNode = useMemo(() => nodes.find((n) => n.id === activeId) || null, [nodes, activeId]);
  const pinnedNodes = useMemo(() => {
    const s = new Set(pinnedIds);
    return nodes.filter((n) => s.has(n.id));
  }, [nodes, pinnedIds]);

  // Build hierarchy from pinned selections:
  // - metrics are KPIs under objective groups
  // - features pinned can become sub-KPIs under the metric (dependency-driven)
  const draftObjectives = useMemo(() => buildHierarchyFromPinned({ pinnedNodes }), [pinnedNodes]);

  const draftScorecard = useMemo(() => {
    return makeScorecard({
      name: scorecardName,
      description: scorecardDesc,
      pinnedNodeIds: pinnedIds,
      objectives: draftObjectives,
    });
  }, [scorecardName, scorecardDesc, pinnedIds, draftObjectives]);

  const isPinned = activeId ? pinnedIds.includes(activeId) : false;

  function togglePinned(id) {
    if (!id) return;
    setPinnedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  function focusNode(id) {
    setActiveId(id);
  }

  function onSaveDraft() {
    const next = [draftScorecard, ...saved].slice(0, 50); // cap for demo
    setSaved(next);
    saveScorecards(next);
  }

  function onDelete(id) {
    const next = saved.filter((s) => s.id !== id);
    setSaved(next);
    saveScorecards(next);
  }

  function onLoad(id) {
    const sc = saved.find((s) => s.id === id);
    if (!sc) return;
    setScorecardName(sc.name || "");
    setScorecardDesc(sc.description || "");
    setPinnedIds(sc.selection?.pinnedNodeIds || []);
  }

  function onExportDraft() {
    const json = JSON.stringify(draftScorecard, null, 2);
    navigator.clipboard?.writeText(json);
    alert("Draft scorecard JSON copied to clipboard.");
  }

  function onImport() {
    try {
      const parsed = JSON.parse(importText);
      if (!parsed?.selection?.pinnedNodeIds) throw new Error("Missing selection.pinnedNodeIds");
      const nextPinned = parsed.selection.pinnedNodeIds;
      setScorecardName(parsed.name || "Imported Scorecard");
      setScorecardDesc(parsed.description || "");
      setPinnedIds(nextPinned);
      alert("Imported scorecard loaded into draft.");
    } catch (e) {
      alert(`Import failed: ${String(e.message || e)}`);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
      <div className="max-w-[1400px] mx-auto">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-2xl font-semibold">HR Compliance Strategy Map</div>
            <div className="mt-1 text-sm text-zinc-400">
              Pin items from the map → build hierarchical KPI list → save/export as JSON.
            </div>
          </div>
          <div className="flex gap-2">
            <Btn onClick={() => setActiveId("met.compliance_gap_count")}>Focus compliance_gap_count</Btn>
            <Btn onClick={() => setActiveId(null)}>Clear</Btn>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-12 gap-4">
          {/* Graph */}
          <div className="col-span-12 lg:col-span-8 rounded-2xl border border-zinc-800 bg-zinc-900/30 overflow-hidden">
            <div className="px-4 py-3 border-b border-zinc-800 text-sm font-semibold">Strategy Map</div>
            <div className="h-[580px]">
              <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodeClick={(_, n) => setActiveId(n.id)}
                fitView
                proOptions={{ hideAttribution: true }}
              >
                <Background />
                <Controls />
                <MiniMap maskColor="rgba(0,0,0,0.45)" nodeBorderRadius={12} />
              </ReactFlow>
            </div>
          </div>

          {/* Right column */}
          <div className="col-span-12 lg:col-span-4 space-y-4">
            {/* Inspector */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-zinc-100">Inspector</div>
                  <div className="mt-1 text-xs text-zinc-400">
                    Click a node to inspect, then pin it for the scorecard.
                  </div>
                </div>
                <Btn onClick={() => togglePinned(activeId)} disabled={!activeNode} variant="primary">
                  {isPinned ? "Remove" : "Pin"}
                </Btn>
              </div>

              {activeNode ? (
                <div className="mt-3 space-y-2">
                  <div className="text-sm text-zinc-100 font-semibold">{activeNode.data.title}</div>
                  <div className="text-xs text-zinc-400">{activeNode.data.subtitle}</div>
                  {activeNode.data.description ? (
                    <div className="text-sm text-zinc-200">{activeNode.data.description}</div>
                  ) : null}
                  {activeNode.data.derivedFrom?.length ? (
                    <div>
                      <div className="text-xs text-zinc-400 mt-2">Derived from</div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {activeNode.data.derivedFrom.map((x) => (
                          <Chip key={x}>{x}</Chip>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="mt-3 text-sm text-zinc-400">No node selected.</div>
              )}
            </div>

            {/* Draft Scorecard Controls */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 space-y-3">
              <div className="text-sm font-semibold text-zinc-100">Draft Scorecard</div>
              <Input value={scorecardName} onChange={setScorecardName} placeholder="Scorecard name" />
              <Input value={scorecardDesc} onChange={setScorecardDesc} placeholder="Short description" />

              <div className="flex flex-wrap gap-2">
                <Btn onClick={onSaveDraft} variant="primary">Save</Btn>
                <Btn onClick={onExportDraft}>Export JSON</Btn>
                <Btn onClick={() => setPinnedIds([])}>Clear Pinned</Btn>
              </div>

              <div className="text-xs text-zinc-400">
                Tip: pin features like <span className="text-zinc-200">is_overdue</span> to show them as sub-KPIs beneath a KPI.
              </div>
            </div>

            {/* Hierarchical KPI Table */}
            <HierarchicalKpiTable scorecard={draftScorecard} onFocusNode={focusNode} />

            {/* Saved Scorecards */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold text-zinc-100">Saved Scorecards</div>
                <div className="text-xs text-zinc-400">{saved.length}</div>
              </div>

              {saved.length === 0 ? (
                <div className="text-sm text-zinc-400">No saved scorecards yet.</div>
              ) : (
                <div className="space-y-2">
                  {saved.slice(0, 8).map((s) => (
                    <div key={s.id} className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-3">
                      <div className="text-sm text-zinc-100 font-semibold">{s.name}</div>
                      <div className="text-xs text-zinc-400 mt-1">
                        {s.hierarchy?.objectives?.length || 0} objectives • {s.selection?.pinnedNodeIds?.length || 0} pinned
                      </div>
                      <div className="mt-2 flex gap-2">
                        <Btn onClick={() => onLoad(s.id)} variant="primary">Load</Btn>
                        <Btn onClick={() => onDelete(s.id)}>Delete</Btn>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="pt-2 border-t border-zinc-800">
                <div className="text-xs text-zinc-400 mb-2">Import scorecard JSON</div>
                <textarea
                  className="w-full h-28 rounded-xl border border-zinc-800 bg-zinc-950/40 text-zinc-100 p-3 text-xs"
                  value={importText}
                  onChange={(e) => setImportText(e.target.value)}
                  placeholder="{ ...scorecard JSON... }"
                />
                <div className="mt-2 flex gap-2">
                  <Btn onClick={onImport} variant="primary">Import</Btn>
                  <Btn onClick={() => setImportText("")}>Clear</Btn>
                </div>
              </div>
            </div>

            {/* Tiny note */}
            <div className="text-xs text-zinc-500">
              Mock only: values/targets/scores are placeholders. Your backend will compute them per objective/KPI at query time.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
