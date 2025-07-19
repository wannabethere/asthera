#!/usr/bin/env python3
import json
import uuid
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dateutil import parser as dateparser
import re

from sqlalchemy import text

from app.schemas.document_schemas import DocumentType
from app.services.database.dbservice import DatabaseService
from app.services.database.connection_service import connection_service
from ..storage.base import IStorage

logger = logging.getLogger(__name__)

class PostgresStorage(IStorage):
    """
    Storage implementation for PostgreSQL database.
    Handles storing documents, metrics, and other data in PostgreSQL tables.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the PostgreSQL storage.
        
        Args:
            config: Configuration parameters
        """
        self.config = config or {}
        self.db_service = DatabaseService()
        self.engine = connection_service.postgres_engine
        
        # Flag to enable/disable debug logging
        self.debug = self.config.get("debug", False)
    
    def store_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store a document in PostgreSQL document_versions1 table.
        
        Args:
            document: The document to store
            
        Returns:
            Result dictionary with status and document ID
        """
        try:
            # Extract document fields
            content = document.get("content", "")
            metadata = document.get("metadata", {})
            source_type = document.get("source_type", "unknown")
            document_type = document.get("document_type", DocumentType.GENERIC.value)
            
            # Generate a document ID if not provided
            doc_id = document.get("id", "") or str(uuid.uuid4())
            
            # Add document ID to metadata if not present
            if "document_id" not in metadata:
                metadata["document_id"] = doc_id
            
            # Store in PostgreSQL
            self._log_info(f"Storing document {doc_id} in PostgreSQL document_versions1 table")
            stored_doc_id = self.db_service.store_document(
                content=content,
                metadata=metadata,
                source_type=source_type,
                document_type=document_type
            )
            
            return {
                "success": True,
                "document_id": doc_id,
                "stored_id": stored_doc_id,
                "storage": "postgresql_document_versions1"
            }
        except Exception as e:
            logger.error(f"Error storing document in PostgreSQL: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def store_metrics(self, metrics_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store metrics in PostgreSQL metrics table.
        
        Args:
            metrics_data: The metrics data to store
            
        Returns:
            Result dictionary with status and metrics count
        """
        try:
            # Convert metrics data to metrics format
            metrics = self._convert_to_metrics_format(metrics_data)
            
            # Insert metrics into the database
            self._log_info(f"Inserting {len(metrics)} metrics into the PostgreSQL metrics table")
            self._insert_metrics(metrics)
            
            return {
                "success": True,
                "metrics_count": len(metrics),
                "storage": "postgresql_metrics"
            }
        except Exception as e:
            logger.error(f"Error storing metrics in PostgreSQL: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def store_gong_stats(self, stats_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store Gong call statistics in PostgreSQL metrics table.
        
        Args:
            stats_data: The Gong call statistics data to store
            
        Returns:
            Result dictionary with status and metrics count
        """
        try:
            # Convert Gong stats to metrics format
            metrics = self._convert_gong_stats_to_metrics(stats_data)
            
            # Insert metrics into the database
            self._log_info(f"Inserting {len(metrics)} Gong metrics into the PostgreSQL metrics table")
            self._insert_metrics(metrics)
            
            return {
                "success": True,
                "metrics_count": len(metrics),
                "storage": "postgresql_metrics"
            }
        except Exception as e:
            logger.error(f"Error storing Gong stats in PostgreSQL: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _convert_to_metrics_format(self, data: Dict[str, Any]) -> List[Tuple]:
        """
        Convert generic data to metrics format for database insertion.
        
        Args:
            data: The data to convert
            
        Returns:
            List of metrics ready for database insertion
        """
        # This is a placeholder for a generic conversion
        # Implementations should override this for specific data types
        metrics = []
        
        # Generate a source ID for this batch of metrics
        source_id = str(uuid.uuid4())
        
        # Use current time as default timestamp
        timestamp = datetime.now()
        
        # Extract metrics from data
        for key, value in data.items():
            if isinstance(value, (int, float)):
                # Create a simple metric for numeric values
                metrics.append((
                    key,  # metric_name
                    data.get("source", "Unknown"),  # source
                    data.get("category", "general"),  # category
                    data.get("source_type", "unknown"),  # source_type
                    value,  # value
                    data.get("measure", "count"),  # measure
                    source_id,  # source_id
                    json.dumps(data.get("metadata", {})),  # metadata
                    timestamp,  # timestamp
                    data.get("aggregation_period", "daily")  # aggregation_period
                ))
        
        return metrics
    
    def _convert_gong_stats_to_metrics(self, stats_data: Dict[str, Any]) -> List[Tuple]:
        """
        Convert Gong call statistics to metrics format for database insertion.
        Adapted from load_stats_to_postgres.py.
        
        Args:
            stats_data: The Gong call statistics data
            
        Returns:
            List of metrics ready for database insertion
        """
        metrics = []
        
        for call in stats_data.get("calls", []):
            call_id = call.get("id")
            source = "Gong"
            source_type = "gong transcript"
            
            # Create metadata JSON with call details including call_id
            metadata = {
                "url": call.get("url", ""),
                "title": call.get("title", ""),
                "call_id": call_id  # Include call_id in metadata
            }
            
            # Convert date_timestamp to datetime object
            try:
                # First try to use the timestamp directly
                date_timestamp = call.get("date_timestamp", 0)
                if date_timestamp:
                    call_timestamp = datetime.fromtimestamp(date_timestamp)
                else:
                    # If no timestamp, try to parse the date string
                    date_str = call.get("date", "")
                    if date_str:
                        call_timestamp = dateparser.parse(date_str)
                    else:
                        # Default to current time if no date information available
                        call_timestamp = datetime.now()
            except Exception as e:
                # If timestamp conversion fails, use current time
                logger.warning(f"Invalid timestamp for call {call_id}, using current time: {e}")
                call_timestamp = datetime.now()
            
            # Generate a single UUID for all metrics from this call
            source_id = str(uuid.uuid4())
            
            # Process stats metrics
            stats = call.get("stats", {})
            
            # Add keyword occurrences metric
            metrics.append((
                "Keyword Occurrences",
                source,
                "content",
                source_type,
                stats.get("keyword_occurrences", 0),
                "count",
                source_id,
                json.dumps(metadata),
                call_timestamp,
                "daily"
            ))
            
            # Add participant count metrics
            metrics.append((
                "Total Participants",
                source,
                "engagement",
                source_type,
                stats.get("participant_count", 0),
                "count",
                source_id,
                json.dumps(metadata),
                call_timestamp,
                "daily"
            ))
            
            metrics.append((
                "Internal Participants",
                source,
                "engagement",
                source_type,
                stats.get("tellius_participant_count", 0),
                "count",
                source_id,
                json.dumps(metadata),
                call_timestamp,
                "daily"
            ))
            
            # Add talk time metric
            metrics.append((
                "Total Talk Time",
                source,
                "interaction",
                source_type,
                stats.get("total_talk_time_seconds", 0),
                "seconds",
                source_id,
                json.dumps(metadata),
                call_timestamp,
                "daily"
            ))
            
            # Add question count metric
            metrics.append((
                "Questions Asked",
                source,
                "interaction",
                source_type,
                stats.get("question_count", 0),
                "count",
                source_id,
                json.dumps(metadata),
                call_timestamp,
                "daily"
            ))
            
            # Add internal and external question count metrics
            metrics.append((
                "Internal Questions Asked",
                source,
                "interaction",
                source_type,
                stats.get("internal_question_count", 0),
                "count",
                source_id,
                json.dumps(metadata),
                call_timestamp,
                "daily"
            ))
            
            metrics.append((
                "External Questions Asked",
                source,
                "interaction",
                source_type,
                stats.get("external_question_count", 0),
                "count",
                source_id,
                json.dumps(metadata),
                call_timestamp,
                "daily"
            ))
            
            # Add action item metrics
            metrics.append((
                "Action Items",
                source,
                "content",
                source_type,
                stats.get("action_item_count", 0),
                "count",
                source_id,
                json.dumps(metadata),
                call_timestamp,
                "daily"
            ))
            
            metrics.append((
                "Action Items Resolved",
                source,
                "content",
                source_type,
                stats.get("action_items_resolved_count", 0),
                "count",
                source_id,
                json.dumps(metadata),
                call_timestamp,
                "daily"
            ))
            
            metrics.append((
                "Internal Calls Made",
                source,
                "interaction",
                source_type,
                stats.get("tellius_calls_made", 0),
                "count",
                source_id,
                json.dumps(metadata),
                call_timestamp,
                "daily"
            ))
            
            # Add tracker-specific metrics
            for tracker in call.get("trackers", []):
                tracker_name = tracker.get("name", "Unknown Tracker")
                tracker_count = tracker.get("count", 0)
                
                metrics.append((
                    f"Tracker: {tracker_name}",
                    source,
                    "tracker",
                    source_type,
                    tracker_count,
                    "count",
                    source_id,
                    json.dumps(metadata),
                    call_timestamp,
                    "daily"
                ))
                
            # Extract and add interaction stats as separate metrics
            interaction = call.get("interaction", {})
            interaction_stats = interaction.get("stats", [])
            
            for stat in interaction_stats:
                stat_name = stat.get("name", "Unknown Stat")
                stat_value = stat.get("value", 0)
                
                # Determine measure type based on the stat name
                measure_type = "ratio"  # Default
                if "Monologue" in stat_name or "Story" in stat_name:
                    measure_type = "seconds"
                
                metrics.append((
                    f"Interaction: {stat_name}",
                    source,
                    "interaction_stat",
                    source_type,
                    stat_value,
                    measure_type,
                    source_id,
                    json.dumps(metadata),
                    call_timestamp,
                    "daily"
                ))
                
            # Add tracker mentions with speaker information
            tracker_mentions = stats.get("tracker_mentions", [])
            for mention in tracker_mentions:
                # Get speaker information
                speaker_name = mention.get("speaker_name", "Unknown Speaker")
                speaker_affiliation = mention.get("speaker_affiliation", "Unknown")
                is_internal = mention.get("is_internal", False)
                tracker_name = mention.get("tracker_name", "Unknown Tracker")
                
                # Create a more specific metric name
                metric_name = f"Tracker Mention: {tracker_name}"
                
                # Add additional speaker info to metadata
                mention_metadata = metadata.copy()
                mention_metadata.update({
                    "speaker_name": speaker_name,
                    "speaker_affiliation": speaker_affiliation,
                    "is_internal": is_internal
                })
                
                metrics.append((
                    metric_name,
                    source,
                    "tracker_mention",
                    source_type,
                    1,  # Each mention counts as 1
                    "count",
                    source_id,
                    json.dumps(mention_metadata),
                    call_timestamp,
                    "daily"
                ))
        
        return metrics
    
    def _insert_metrics(self, metrics: List[Tuple]) -> None:
        """
        Insert metrics into the PostgreSQL metrics table.
        
        Args:
            metrics: List of metrics to insert
        """
        # Create a connection and execute in a transaction
        with self.engine.begin() as conn:
            # Insert metrics in batches
            batch_size = 50
            for i in range(0, len(metrics), batch_size):
                batch = metrics[i:i+batch_size]
                
                # Prepare the values part of the SQL statement
                values_list = []
                for metric in batch:
                    # Format the values for this metric
                    values_list.append(f"('{metric[0]}', '{metric[1]}', '{metric[2]}', '{metric[3]}', {metric[4]}, '{metric[5]}', '{metric[6]}', '{metric[7]}', '{metric[8]}', '{metric[9]}')")
                
                # Join the values into a single string
                values_str = ", ".join(values_list)
                
                # Create the SQL statement
                sql = f"""
                INSERT INTO metrics (
                    metric_name, source, category, source_type, value, measure, source_id, metadata, timestamp, aggregation_period
                ) VALUES {values_str}
                """
                
                # Execute the SQL statement
                conn.execute(text(sql))
                
            # Transaction is automatically committed when the context manager exits
        
        self._log_info(f"Inserted {len(metrics)} metrics into the database")
    
    def _log_info(self, message: str) -> None:
        """Log info messages only when debug is enabled."""
        if self.debug:
            logger.info(message) 