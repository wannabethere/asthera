# Contextual Graph Integration for Metadata Transfer Learning Agents

## Overview

The metadata transfer learning agents should use **Contextual Graph Service** to make context-aware decisions throughout the workflow. This document explains how each agent integrates with contextual graphs and the decision-making logic.

## What are Contextual Graphs?

Contextual graphs store:
1. **Context Definitions**: Organizational/situational contexts (industry, size, maturity, frameworks)
2. **Contextual Edges**: Context-aware relationships between entities (controls → requirements → evidence)
3. **Control-Context Profiles**: How controls apply in specific contexts (risk scores, implementation complexity, effort)

## Decision-Making Flow

```
Target Domain Documents
    ↓
1. Pattern Recognition Agent
    → Uses Contextual Graph to find similar contexts
    → Retrieves context-aware patterns from source domains
    ↓
2. Domain Adaptation Agent
    → Finds matching contexts for target domain
    → Uses context-aware mappings (exact/similar/analogical)
    → Adapts patterns based on organizational context
    ↓
3. Metadata Generation Agent
    → Identifies risks using context-aware control profiles
    → Generates metadata entries with context-specific scores
    ↓
4. Validation Agent
    → Validates against context-specific patterns
    → Refines based on context constraints
```

## Agent Integration Details

### 1. Pattern Recognition Agent

**Current State**: Loads source metadata directly
**With Contextual Graphs**: 

```python
async def _load_source_metadata(self, source_domains: List[str]) -> List[Dict[str, Any]]:
    # 1. Find relevant contexts for source domains
    context_query = f"Compliance metadata patterns for {', '.join(source_domains)}"
    relevant_contexts = await self.contextual_graph_service.search_contexts(
        ContextSearchRequest(
            description=context_query,
            top_k=5
        )
    )
    
    # 2. Get context-aware control profiles (these contain patterns)
    all_patterns = []
    for context in relevant_contexts.data["contexts"]:
        controls = await self.contextual_graph_service.get_priority_controls(
            PriorityControlsRequest(
                context_id=context["context_id"],
                top_k=20
            )
        )
        # Extract patterns from control profiles
        for control in controls.data["controls"]:
            pattern = self._extract_pattern_from_profile(control)
            all_patterns.append(pattern)
    
    # 3. Also load traditional metadata (fallback)
    traditional_metadata = await self.metadata_service.load_source_metadata(source_domains)
    
    return all_patterns + traditional_metadata
```

**Decision Logic**:
- **If context found**: Use context-aware patterns (more accurate, domain-specific)
- **If no context**: Fall back to traditional metadata loading
- **Pattern confidence**: Higher for context-matched patterns

### 2. Domain Adaptation Agent

**Current State**: Creates mappings based on patterns only
**With Contextual Graphs**:

```python
async def _create_domain_mappings(
    self,
    patterns: List[MetadataPattern],
    source_domains: List[str],
    target_domain: str,
    target_documents: List[str]
) -> List[DomainMapping]:
    # 1. Find matching context for target domain
    target_context_query = f"{target_domain} compliance context: {target_documents[0][:500]}"
    target_contexts = await self.contextual_graph_service.search_contexts(
        ContextSearchRequest(
            description=target_context_query,
            top_k=3
        )
    )
    
    # 2. For each source pattern, find context-aware mappings
    mappings = []
    for pattern in patterns:
        # Find source context
        source_contexts = await self.contextual_graph_service.search_contexts(
            ContextSearchRequest(
                description=f"{pattern.source_domain} context",
                filters={"regulatory_frameworks": pattern.source_domain},
                top_k=1
            )
        )
        
        if source_contexts.data["contexts"] and target_contexts.data["contexts"]:
            source_ctx = source_contexts.data["contexts"][0]
            target_ctx = target_contexts.data["contexts"][0]
            
            # Use multi-hop query to find analogical mappings
            mapping_query = f"Map {pattern.pattern_name} from {source_ctx['context_id']} to {target_ctx['context_id']}"
            reasoning = await self.contextual_graph_service.multi_hop_query(
                MultiHopQueryRequest(
                    query=mapping_query,
                    context_id=target_ctx["context_id"],
                    max_hops=2
                )
            )
            
            # Extract mappings from reasoning path
            mappings.extend(self._extract_mappings_from_reasoning(reasoning, pattern))
    
    return mappings
```

**Decision Logic**:
- **Context Match Found**: Use context-aware analogical reasoning
- **No Context Match**: Use LLM-based mapping (current approach)
- **Mapping Type Decision**:
  - **Exact**: Same context, same industry → exact match
  - **Similar**: Similar context (same industry, different size) → similar match
  - **Analogical**: Different context → analogical match with lower confidence

### 3. Metadata Generation Agent

**Current State**: Identifies risks from documents, generates metadata
**With Contextual Graphs**:

```python
async def _identify_risks(
    self,
    documents: List[str],
    target_domain: str,
    adaptation_strategy: Dict[str, Any]
) -> List[Dict[str, Any]]:
    # 1. Find target context
    context_query = f"{target_domain} organizational context: {documents[0][:500]}"
    contexts = await self.contextual_graph_service.search_contexts(
        ContextSearchRequest(
            description=context_query,
            top_k=1
        )
    )
    
    if not contexts.data["contexts"]:
        # Fallback to current LLM-based approach
        return await self._identify_risks_llm_only(documents, target_domain)
    
    target_context_id = contexts.data["contexts"][0]["context_id"]
    
    # 2. Get context-aware control profiles (these indicate risks)
    controls = await self.contextual_graph_service.get_priority_controls(
        PriorityControlsRequest(
            context_id=target_context_id,
            query=f"Risks and threats in {target_domain}",
            top_k=20
        )
    )
    
    # 3. Extract risks from control profiles
    risks = []
    for control in controls.data["controls"]:
        profile = control["context_profile"]
        if profile["risk_level"] in ["high", "critical"]:
            risks.append({
                "risk_name": control["control_id"],
                "category": "threat",
                "description": control["reasoning"],
                "severity_indicators": f"Risk level: {profile['risk_level']}, Residual risk: {profile.get('residual_risk_score', 0)}",
                "likelihood_indicators": f"Implementation complexity: {profile.get('implementation_complexity', 'unknown')}",
                "impact_indicators": f"Estimated effort: {profile.get('estimated_effort_hours', 0)} hours",
                "regulatory_source": target_domain,
                "context_id": target_context_id
            })
    
    # 4. Also use LLM to identify document-specific risks
    llm_risks = await self._identify_risks_llm_only(documents, target_domain)
    
    # Combine and deduplicate
    return self._merge_risks(risks, llm_risks)
```

**Decision Logic**:
- **Context Found + Controls Available**: Use context-aware risk identification (more accurate)
- **Context Found but No Controls**: Use LLM with context as guidance
- **No Context**: Use LLM-only approach (current)

```python
async def _generate_metadata_entries(
    self,
    risks: List[Dict[str, Any]],
    patterns: List,
    mappings: List[DomainMapping],
    target_domain: str,
    target_framework: Optional[str],
    adaptation_strategy: Dict[str, Any]
) -> List[MetadataEntry]:
    # 1. Get context for scoring decisions
    context_id = risks[0].get("context_id") if risks else None
    if context_id:
        # Get context-aware scoring patterns
        context_controls = await self.contextual_graph_service.get_priority_controls(
            PriorityControlsRequest(
                context_id=context_id,
                top_k=50
            )
        )
        
        # Use context profiles to inform scoring
        scoring_reference = {
            c["control_id"]: c["context_profile"] 
            for c in context_controls.data["controls"]
        }
    else:
        scoring_reference = {}
    
    # 2. Generate entries with context-aware scoring
    entries = []
    for risk in risks:
        # Find similar control in context
        similar_control = self._find_similar_control(risk, scoring_reference)
        
        if similar_control:
            # Use context profile for scoring
            profile = similar_control["context_profile"]
            entry = MetadataEntry(
                domain_name=target_domain,
                framework_name=target_framework,
                metadata_category="threat",
                enum_type="risk_type",
                code=risk["risk_name"],
                description=risk["description"],
                numeric_score=self._calculate_context_score(profile),
                priority_order=profile.get("priority_in_context", 1),
                severity_level=self._map_risk_level_to_severity(profile["risk_level"]),
                risk_score=profile.get("residual_risk_score"),
                rationale=f"Based on context profile: {similar_control['reasoning']}"
            )
        else:
            # Fallback to LLM generation
            entry = await self._generate_entry_llm(risk, patterns, mappings)
        
        entries.append(entry)
    
    return entries
```

**Decision Logic**:
- **Context Control Found**: Use context profile scores (more accurate, organization-specific)
- **No Context Control**: Use LLM with pattern guidance
- **Score Calculation**: 
  - High risk in context → Higher numeric_score
  - Implementation complexity → Affects priority_order
  - Residual risk → Direct risk_score

### 4. Validation Agent

**Current State**: Validates against patterns only
**With Contextual Graphs**:

```python
async def _validate_metadata(
    self,
    entries: List[MetadataEntry],
    target_domain: str,
    patterns: List
) -> Dict[str, Any]:
    # 1. Find target context
    context_query = f"{target_domain} compliance validation context"
    contexts = await self.contextual_graph_service.search_contexts(
        ContextSearchRequest(
            description=context_query,
            top_k=1
        )
    )
    
    validation_results = {}
    
    for entry in entries:
        if contexts.data["contexts"]:
            context_id = contexts.data["contexts"][0]["context_id"]
            
            # 2. Check if entry aligns with context-aware controls
            similar_controls = await self.contextual_graph_service.search_controls(
                ControlSearchRequest(
                    context_id=context_id,
                    query=entry.description,
                    top_k=3
                )
            )
            
            if similar_controls.data["controls"]:
                # Validate against context profile
                control = similar_controls.data["controls"][0]
                profile = control["context_profile"]
                
                validation_results[entry.code] = {
                    "is_valid": True,
                    "completeness_score": self._check_completeness(entry, profile),
                    "consistency_score": self._check_consistency(entry, profile),
                    "accuracy_score": self._check_accuracy(entry, profile),
                    "issues": [],
                    "suggestions": self._generate_suggestions(entry, profile)
                }
            else:
                # Fallback to pattern-based validation
                validation_results[entry.code] = await self._validate_against_patterns(entry, patterns)
        else:
            # No context, use pattern validation
            validation_results[entry.code] = await self._validate_against_patterns(entry, patterns)
    
    return validation_results
```

**Decision Logic**:
- **Context + Control Found**: Validate against context profile (organization-specific validation)
- **Context but No Control**: Use pattern validation with context awareness
- **No Context**: Use pattern-only validation (current approach)

## Key Decision Points

### When to Use Contextual Graphs

1. **Pattern Recognition**:
   - ✅ Always try to find relevant contexts first
   - ✅ Use context-aware patterns if available
   - ⚠️ Fallback to traditional metadata if no context

2. **Domain Adaptation**:
   - ✅ Use multi-hop reasoning for analogical mappings
   - ✅ Context similarity determines mapping type (exact/similar/analogical)
   - ⚠️ Use LLM mapping if no context match

3. **Metadata Generation**:
   - ✅ Use context profiles for risk identification
   - ✅ Use context profiles for scoring decisions
   - ⚠️ Use LLM generation if no context control found

4. **Validation**:
   - ✅ Validate against context profiles if available
   - ✅ Use context-specific quality thresholds
   - ⚠️ Use pattern validation as fallback

### Context Matching Strategy

```python
def should_use_context(context_result, confidence_threshold=0.7):
    """Decide if context is reliable enough to use"""
    if not context_result.data["contexts"]:
        return False
    
    top_context = context_result.data["contexts"][0]
    # Check combined score if available
    combined_score = top_context.get("combined_score", 0.0)
    
    return combined_score >= confidence_threshold
```

### Scoring Decisions

Context-aware scoring uses:
- **Risk Level** → Severity Level mapping
- **Residual Risk Score** → Risk Score
- **Implementation Complexity** → Priority Order
- **Estimated Effort** → Weight adjustment

## Integration Architecture

```
MetadataTransferLearningWorkflow
    ↓
    ┌─────────────────────────────────────┐
    │  ContextualGraphService (injected)  │
    │  - search_contexts()                │
    │  - get_priority_controls()          │
    │  - multi_hop_query()                │
    │  - search_controls()                │
    └─────────────────────────────────────┘
    ↓
    PatternRecognitionAgent
    ├─→ Uses: search_contexts()
    └─→ Uses: get_priority_controls()
    ↓
    DomainAdaptationAgent
    ├─→ Uses: search_contexts()
    ├─→ Uses: multi_hop_query()
    └─→ Uses: search_controls()
    ↓
    MetadataGenerationAgent
    ├─→ Uses: search_contexts()
    ├─→ Uses: get_priority_controls()
    └─→ Uses: search_controls()
    ↓
    ValidationAgent
    ├─→ Uses: search_contexts()
    └─→ Uses: search_controls()
```

## Benefits

1. **Context-Aware Decisions**: Agents make decisions based on organizational context
2. **More Accurate Scoring**: Scores reflect actual organizational risk profiles
3. **Better Mappings**: Analogical reasoning through context relationships
4. **Organization-Specific**: Generated metadata fits the specific organization
5. **Fallback Safety**: Always falls back to LLM if context unavailable

## Example Flow

```
User: Generate metadata for "healthcare_compliance" domain
Documents: ["HIPAA requires encryption of PHI..."]

1. Pattern Recognition:
   → Search contexts: "healthcare compliance patterns"
   → Find: context_healthcare_large_hospital
   → Get controls: 50 healthcare controls with profiles
   → Extract patterns: Encryption patterns, PHI handling patterns

2. Domain Adaptation:
   → Search contexts: "healthcare compliance organizational context"
   → Find: context_healthcare_medium_clinic
   → Multi-hop query: "Map encryption patterns to clinic context"
   → Result: Analogical mapping (hospital → clinic, adjust complexity)

3. Metadata Generation:
   → Get priority controls for clinic context
   → Find: "PHI_ENCRYPTION" control with profile
   → Profile shows: risk_level="high", residual_risk=0.75
   → Generate entry: numeric_score=85, severity_level=8, risk_score=0.75

4. Validation:
   → Validate against clinic context profile
   → Check: Score aligns with profile? ✅
   → Check: Description matches context? ✅
   → Result: Valid, confidence=0.92
```

