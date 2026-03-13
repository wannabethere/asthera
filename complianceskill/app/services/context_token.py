"""
Context Token Service

Mints and resolves signed tokens for context delivery.
Follows the design from agent_adapter.md Section 8.
"""

import logging
import hmac
import hashlib
import json
from typing import Optional
from uuid import uuid4
import base64

from app.adapters.base import ComposedContext
from app.storage.cache import CacheClient

logger = logging.getLogger(__name__)


class ContextTokenService:
    """
    Service for minting and resolving context tokens.
    
    Context is never sent inline - gateway mints a short-lived signed token
    pointing to pre-computed context in Redis.
    """
    
    def __init__(self, cache: CacheClient, secret_key: str):
        """
        Initialize context token service.
        
        Args:
            cache: Cache client for Redis storage
            secret_key: Secret key for HMAC signing
        """
        self.cache = cache
        self.secret_key = secret_key.encode() if isinstance(secret_key, str) else secret_key
    
    async def mint(
        self,
        context: ComposedContext,
        ttl: int = 300
    ) -> str:
        """
        Mint a signed context token.
        
        Args:
            context: Composed context to store
            ttl: Time-to-live in seconds (default 5 minutes)
        
        Returns:
            Signed token string
        """
        # Generate unique context key
        ctx_key = f"ctx:{uuid4().hex}"
        
        # Store context in Redis
        await self.cache.set(
            ctx_key,
            context.model_dump(),
            ttl=ttl,
        )
        
        # Sign the key
        token = self._sign(ctx_key)
        
        logger.debug(f"Minted context token for key {ctx_key}")
        return token
    
    async def resolve(self, token: str) -> ComposedContext:
        """
        Resolve a context token to ComposedContext.
        
        Args:
            token: Signed token string
        
        Returns:
            ComposedContext instance
        
        Raises:
            ContextExpiredError: If token is invalid or expired
        """
        # Verify and extract context key
        try:
            ctx_key = self._verify(token)
        except Exception as e:
            raise ContextExpiredError(f"Invalid token: {e}") from e
        
        # Fetch context from Redis
        context_data = await self.cache.get(ctx_key)
        
        if not context_data:
            raise ContextExpiredError(f"Context expired or not found for key {ctx_key}")
        
        # Deserialize to ComposedContext
        try:
            return ComposedContext(**context_data)
        except Exception as e:
            raise ContextExpiredError(f"Failed to deserialize context: {e}") from e
    
    def _sign(self, ctx_key: str) -> str:
        """Sign a context key using HMAC-SHA256"""
        signature = hmac.new(
            self.secret_key,
            ctx_key.encode(),
            hashlib.sha256
        ).digest()
        
        # Encode as base64 for URL safety
        sig_b64 = base64.urlsafe_b64encode(signature).decode()
        
        # Return token format: v1.hmac.{key}.{signature}
        return f"v1.hmac.{ctx_key}.{sig_b64}"
    
    def _verify(self, token: str) -> str:
        """Verify token signature and extract context key"""
        parts = token.split(".")
        if len(parts) != 4 or parts[0] != "v1" or parts[1] != "hmac":
            raise ValueError("Invalid token format")
        
        ctx_key = parts[2]
        provided_sig = parts[3]
        
        # Recompute signature
        expected_sig = base64.urlsafe_b64encode(
            hmac.new(
                self.secret_key,
                ctx_key.encode(),
                hashlib.sha256
            ).digest()
        ).decode()
        
        # Constant-time comparison
        if not hmac.compare_digest(provided_sig, expected_sig):
            raise ValueError("Invalid token signature")
        
        return ctx_key


class ContextExpiredError(Exception):
    """Raised when a context token is invalid or expired"""
    pass
