// scorecardSchema.js

/**
 * Persistable Scorecard JSON (v1)
 *
 * Store this in DB (Postgres/Doc store) or in your metadata layer.
 *
 * NOTE: values/targets/scores are intentionally optional, because your backend
 * will compute them at query time for an "asOf" date, OU scope, etc.
 */
export function makeScorecard({
    name,
    description = "",
    pinnedNodeIds = [],
    objectives = [],
    createdBy = "demo-user",
  }) {
    return {
      schemaVersion: "scorecard.v1",
      id: `sc_${cryptoRandomId()}`,
      name,
      description,
      domain: "hr_compliance",
      framework: "cornerstone.learn",
      entityType: "training_assignment",
      createdAt: new Date().toISOString(),
      createdBy,
  
      // The raw selection from the map (nodes pinned)
      selection: {
        pinnedNodeIds,
      },
  
      // Hierarchy definition for McBig-style KPI list
      // objectives[] contains groups; each group contains KPI items.
      // Each KPI can contain optional child KPIs (sub-kpis), which is how you get indentation.
      hierarchy: {
        objectives,
      },
  
      // Optional runtime hints (filters/scoping). Your backend can interpret these.
      runtime: {
        asOfDate: null,
        orgUnitScope: {
          departmentOU: null,
          locationOU: null,
          role: null,
        },
      },
    };
  }
  
  /**
   * Example objective structure:
   * {
   *   id: "obj.compliance_gap",
   *   title: "Compliance Gap",
   *   kpis: [
   *     {
   *       id: "kpi.compliance_gap_count",
   *       nodeId: "met.compliance_gap_count",
   *       label: "compliance_gap_count",
   *       value: null,
   *       target: null,
   *       score: null,
   *       children: [
   *         { id: "sub.is_overdue", nodeId: "feat.is_overdue", label: "is_overdue" }
   *       ]
   *     }
   *   ]
   * }
   */
  
  export const SCORECARD_JSON_SCHEMA_V1 = {
    $id: "scorecard.v1",
    type: "object",
    required: ["schemaVersion", "id", "name", "domain", "framework", "entityType", "createdAt", "selection", "hierarchy"],
    properties: {
      schemaVersion: { type: "string", enum: ["scorecard.v1"] },
      id: { type: "string" },
      name: { type: "string" },
      description: { type: "string" },
      domain: { type: "string" },
      framework: { type: "string" },
      entityType: { type: "string" },
      createdAt: { type: "string" },
      createdBy: { type: "string" },
  
      selection: {
        type: "object",
        required: ["pinnedNodeIds"],
        properties: {
          pinnedNodeIds: { type: "array", items: { type: "string" } },
        },
      },
  
      hierarchy: {
        type: "object",
        required: ["objectives"],
        properties: {
          objectives: {
            type: "array",
            items: {
              type: "object",
              required: ["id", "title", "kpis"],
              properties: {
                id: { type: "string" },
                title: { type: "string" },
                kpis: {
                  type: "array",
                  items: {
                    type: "object",
                    required: ["id", "nodeId", "label"],
                    properties: {
                      id: { type: "string" },
                      nodeId: { type: "string" },
                      label: { type: "string" },
                      value: {},
                      target: {},
                      score: {},
                      children: {
                        type: "array",
                        items: {
                          type: "object",
                          required: ["id", "nodeId", "label"],
                          properties: {
                            id: { type: "string" },
                            nodeId: { type: "string" },
                            label: { type: "string" },
                            value: {},
                            target: {},
                            score: {},
                          },
                        },
                      },
                    },
                  },
                },
              },
            },
          },
        },
      },
  
      runtime: {
        type: "object",
        properties: {
          asOfDate: { type: ["string", "null"] },
          orgUnitScope: {
            type: "object",
            properties: {
              departmentOU: { type: ["string", "null"] },
              locationOU: { type: ["string", "null"] },
              role: { type: ["string", "null"] },
            },
          },
        },
      },
    },
  };
  
  function cryptoRandomId() {
    // Browser-safe id helper
    return Math.random().toString(16).slice(2) + Math.random().toString(16).slice(2);
  }
  