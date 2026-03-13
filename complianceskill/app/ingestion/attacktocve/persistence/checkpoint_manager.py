"""
Checkpoint Manager for Batch Enrichment
========================================
Manages checkpointing for long-running batch enrichment processes.
Allows resuming from the last checkpoint after interruption.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manages checkpoints for batch enrichment processes."""
    
    def __init__(self, checkpoint_dir: str | Path):
        """
        Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.checkpoint_dir / "checkpoint.json"
        self.state: Dict[str, Any] = {}
        self.load_checkpoint()
    
    def load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint state from file."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
                logger.info(
                    f"📂 Loaded checkpoint from: {self.checkpoint_file}\n"
                    f"   Framework: {self.state.get('framework', 'unknown')}\n"
                    f"   Processed: {len(self.state.get('processed_scenarios', []))} / "
                    f"{self.state.get('total_scenarios', 0)} scenarios\n"
                    f"   Last updated: {self.state.get('last_updated', 'unknown')}"
                )
                return self.state
            except Exception as e:
                logger.error(f"⚠️  Failed to load checkpoint: {e}")
                self.state = {}
        else:
            logger.info("No existing checkpoint found - starting fresh")
        return {}
    
    def save_checkpoint(
        self,
        framework: str,
        processed_scenarios: List[str],
        total_scenarios: int,
        results: List[Dict[str, Any]],
        registry_state: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Save checkpoint state to file.
        
        Args:
            framework: Framework identifier
            processed_scenarios: List of scenario IDs that have been processed
            total_scenarios: Total number of scenarios
            results: List of scenario enrichment results
            registry_state: Optional registry state snapshot
            metadata: Optional metadata
        """
        self.state = {
            "framework": framework,
            "processed_scenarios": processed_scenarios,
            "total_scenarios": total_scenarios,
            "results": results,
            "registry_state": registry_state or {},
            "metadata": metadata or {},
            "last_updated": datetime.now().isoformat(),
            "checkpoint_count": self.state.get("checkpoint_count", 0) + 1,
        }
        
        try:
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2)
            logger.debug(f"💾 Checkpoint saved: {len(processed_scenarios)}/{total_scenarios} scenarios")
        except Exception as e:
            logger.error(f"⚠️  Failed to save checkpoint: {e}")
    
    def get_processed_scenarios(self) -> Set[str]:
        """Get set of scenario IDs that have been processed."""
        return set(self.state.get("processed_scenarios", []))
    
    def get_results(self) -> List[Dict[str, Any]]:
        """Get saved results from checkpoint."""
        return self.state.get("results", [])
    
    def get_registry_state(self) -> Dict[str, Any]:
        """Get saved registry state from checkpoint."""
        return self.state.get("registry_state", {})
    
    def has_checkpoint(self) -> bool:
        """Check if a checkpoint exists."""
        return bool(self.state and self.state.get("processed_scenarios"))
    
    def get_progress(self) -> Dict[str, Any]:
        """Get progress information."""
        processed = len(self.state.get("processed_scenarios", []))
        total = self.state.get("total_scenarios", 0)
        progress_pct = (processed / total * 100) if total > 0 else 0
        
        return {
            "framework": self.state.get("framework", "unknown"),
            "processed": processed,
            "total": total,
            "remaining": total - processed,
            "progress_pct": round(progress_pct, 1),
            "last_updated": self.state.get("last_updated", "unknown"),
            "checkpoint_count": self.state.get("checkpoint_count", 0),
        }
    
    def clear_checkpoint(self) -> None:
        """Clear checkpoint (start fresh)."""
        if self.checkpoint_file.exists():
            try:
                # Backup old checkpoint
                backup_file = self.checkpoint_dir / f"checkpoint_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                if self.checkpoint_file.exists():
                    import shutil
                    shutil.copy(self.checkpoint_file, backup_file)
                    logger.info(f"📦 Backed up checkpoint to: {backup_file}")
                
                self.checkpoint_file.unlink()
                self.state = {}
                logger.info("🗑️  Checkpoint cleared")
            except Exception as e:
                logger.error(f"⚠️  Failed to clear checkpoint: {e}")
    
    def export_status(self, output_file: Optional[str] = None) -> Path:
        """Export checkpoint status to a readable file."""
        if output_file:
            status_file = Path(output_file)
        else:
            status_file = self.checkpoint_dir / "status.txt"
        
        progress = self.get_progress()
        
        status_text = f"""
Batch Enrichment Status
{'=' * 60}
Framework: {progress['framework']}
Progress: {progress['processed']} / {progress['total']} scenarios ({progress['progress_pct']}%)
Remaining: {progress['remaining']} scenarios
Last Updated: {progress['last_updated']}
Checkpoint Count: {progress['checkpoint_count']}

Processed Scenarios:
{chr(10).join(f"  - {sid}" for sid in self.state.get('processed_scenarios', [])[:20])}
{'  ...' if len(self.state.get('processed_scenarios', [])) > 20 else ''}
"""
        
        try:
            with open(status_file, 'w', encoding='utf-8') as f:
                f.write(status_text)
            logger.info(f"📄 Status exported to: {status_file}")
        except Exception as e:
            logger.error(f"⚠️  Failed to export status: {e}")
        
        return status_file
