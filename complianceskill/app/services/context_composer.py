"""
Context Composition Service

Assembles budget-aware context from memory tiers and delivers it to agents.
Follows the design from agent_adapter.md Section 8.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from app.adapters.base import ComposedContext
from app.adapters.registry import AgentMeta
from app.storage.cache import CacheClient

logger = logging.getLogger(__name__)


@dataclass
class ContextBudget:
    """
    Token budget per agent following agent_adapter.md Section 8.
    """
    total: int                      # from AgentMeta.context_window_tokens
    system_reserved: int            # agent persona + tool schemas
    turn_reserved: int              # always raw, never compressed
    session_budget: int             # history summary + working memory
    response_reserved: int          # space for agent output
    
    @classmethod
    def from_agent_meta(cls, meta: AgentMeta) -> "ContextBudget":
        """Create budget from agent metadata"""
        return cls(
            total=meta.context_window_tokens,
            system_reserved=meta.system_ctx_tokens,
            turn_reserved=meta.turn_ctx_tokens,
            session_budget=meta.session_ctx_tokens,
            response_reserved=meta.response_reserve_tokens,
        )


class ContextComposer:
    """
    Composes context from memory tiers with budget awareness.
    """
    
    def __init__(self, cache: CacheClient):
        """
        Initialize context composer.
        
        Args:
            cache: Cache client for Redis/working memory access
        """
        self.cache = cache
    
    async def compose(
        self,
        thread_id: str,
        user_input: str,
        agent_meta: AgentMeta,
        claims: Dict[str, Any],
        step_index: int = 0,
    ) -> ComposedContext:
        """
        Compose context for agent invocation.
        
        Args:
            thread_id: Thread identifier
            user_input: Current user input
            agent_meta: Agent metadata
            claims: Resolved JWT claims
            step_index: Step index in multi-agent plan (for budget splitting)
        
        Returns:
            ComposedContext ready for agent
        """
        budget = ContextBudget.from_agent_meta(agent_meta)
        
        # In multi-agent plans, session budget is split across steps
        if step_index > 0:
            budget.session_budget = budget.session_budget // (step_index + 1)
        
        # Layer 1 — System context (static, from registry)
        system_ctx = self._build_system_context(agent_meta, claims)
        
        # Layer 2 — Session context (dynamic, budget-constrained)
        session_ctx = await self._build_session_context(
            thread_id=thread_id,
            claims=claims,
            token_limit=budget.session_budget,
        )
        
        # Layer 3 — Turn context (last N raw messages + current input)
        turn_ctx = await self._build_turn_context(
            thread_id=thread_id,
            user_input=user_input,
            token_limit=budget.turn_reserved,
        )
        
        # Layer 4 — Long-term memory (if available)
        memory = None
        if agent_meta.requires_memory:
            memory = await self._build_memory_context(
                thread_id=thread_id,
                tenant_id=claims.get("tenant_id", "default"),
                memory_keys=agent_meta.requires_memory_keys,
            )
        
        return ComposedContext(
            system=system_ctx,
            session=session_ctx,
            turn=turn_ctx,
            memory=memory,
        )
    
    def _build_system_context(
        self,
        agent_meta: AgentMeta,
        claims: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build system context (static, from registry)"""
        return {
            "agent_id": agent_meta.agent_id,
            "display_name": agent_meta.display_name,
            "capabilities": agent_meta.capabilities,
            "tenant_id": claims.get("tenant_id", "default"),
            "user_id": claims.get("sub", "unknown"),
            "roles": claims.get("roles", []),
        }
    
    async def _build_session_context(
        self,
        thread_id: str,
        claims: Dict[str, Any],
        token_limit: int,
    ) -> Dict[str, Any]:
        """
        Build session context from working memory.
        
        Tries: raw messages → trimmed → summary+raw → trimmed fallback
        """
        # Try to get working memory from Redis
        working_mem_key = f"thread:{thread_id}:working_mem"
        messages = await self.cache.get(working_mem_key)
        
        if not messages:
            # Cache miss - return empty session context
            # In production, would fallback to Postgres
            logger.warning(f"Working memory cache miss for thread {thread_id}")
            return {
                "type": "empty",
                "messages": [],
            }
        
        if not isinstance(messages, list):
            messages = []
        
        # Count tokens (simplified - would use actual tokenizer in production)
        token_count = self._estimate_tokens(messages)
        
        if token_count <= token_limit:
            return {
                "type": "raw",
                "messages": messages,
            }
        
        # Try trim first
        trimmed = self._trim_to_budget(messages, token_limit)
        coverage = self._calculate_coverage(trimmed, messages)
        
        if coverage > 0.7:
            return {
                "type": "trimmed",
                "messages": trimmed,
            }
        
        # Use cached rolling summary + last 5 raw
        summary_key = f"thread:{thread_id}:summary"
        summary = await self.cache.get(summary_key)
        recent = messages[-5:] if len(messages) >= 5 else messages
        
        if summary and self._fits_budget(summary, recent, token_limit):
            return {
                "type": "summary+raw",
                "summary": summary,
                "recent": recent,
            }
        
        # Fallback: use trimmed
        return {
            "type": "trimmed_fallback",
            "messages": trimmed,
        }
    
    async def _build_turn_context(
        self,
        thread_id: str,
        user_input: str,
        token_limit: int,
    ) -> Dict[str, Any]:
        """Build turn context (last N raw messages + current input)"""
        # Get recent messages from working memory
        working_mem_key = f"thread:{thread_id}:working_mem"
        messages = await self.cache.get(working_mem_key)
        
        if not isinstance(messages, list):
            messages = []
        
        # Take last 3 messages + current input
        recent = messages[-3:] if len(messages) >= 3 else messages
        recent.append({
            "role": "user",
            "content": user_input,
            "timestamp": None,  # Would be set in production
        })
        
        return {
            "recent": recent,
            "current_input": user_input,
        }
    
    async def _build_memory_context(
        self,
        thread_id: str,
        tenant_id: str,
        memory_keys: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Build long-term memory context if required"""
        if not memory_keys:
            return None
        
        # Get memory facts from cache
        memory_key = f"memory:{tenant_id}:facts"
        facts = await self.cache.get(memory_key)
        
        if not facts:
            return None
        
        # Filter by memory_keys if specified
        if memory_keys:
            filtered = {k: facts.get(k) for k in memory_keys if k in facts}
            return {"facts": filtered} if filtered else None
        
        return {"facts": facts}
    
    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate token count (simplified - would use actual tokenizer)"""
        # Rough estimate: 1 token ≈ 4 characters
        total_chars = sum(
            len(str(msg.get("content", "")))
            for msg in messages
        )
        return total_chars // 4
    
    def _trim_to_budget(
        self,
        messages: List[Dict[str, Any]],
        token_limit: int
    ) -> List[Dict[str, Any]]:
        """Trim messages to fit token budget"""
        # Simple strategy: keep most recent messages that fit
        trimmed = []
        current_tokens = 0
        
        for msg in reversed(messages):
            msg_tokens = self._estimate_tokens([msg])
            if current_tokens + msg_tokens <= token_limit:
                trimmed.insert(0, msg)
                current_tokens += msg_tokens
            else:
                break
        
        return trimmed
    
    def _calculate_coverage(
        self,
        trimmed: List[Dict[str, Any]],
        original: List[Dict[str, Any]]
    ) -> float:
        """Calculate coverage ratio of trimmed vs original"""
        if not original:
            return 1.0
        return len(trimmed) / len(original)
    
    def _fits_budget(
        self,
        summary: str,
        recent: List[Dict[str, Any]],
        token_limit: int
    ) -> bool:
        """Check if summary + recent messages fit budget"""
        summary_tokens = len(summary) // 4
        recent_tokens = self._estimate_tokens(recent)
        return (summary_tokens + recent_tokens) <= token_limit
