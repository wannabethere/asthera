from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import List, Optional
from uuid import uuid4
import traceback
import logging
from app.models.thread import Audit, Trace,ThreadMessage,Thread
from app.schemas.thread import (
    AuditCreate, AuditUpdate, AuditResponse,
    TraceCreate, TraceUpdate, TraceResponse, AuditWithTracesCreate, AuditFilters, PaginatedAuditResponse
)

# NLTK setup with error handling
try:
    import nltk
    from rake_nltk import Rake
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords', quiet=True)
except ImportError:
    logging.warning("NLTK or rake_nltk not available. Thread name generation will use fallback method.")
    nltk = None
    Rake = None

logger = logging.getLogger(__name__)

class AuditServiceError(Exception):
    """Custom exception for audit service errors"""
    pass

class AuditService:
    def __init__(self, db: Session):
        self.db = db
    
    
    async def create_audit(self, question: str, audit_data: AuditCreate) -> AuditResponse:
        """Create a new audit"""
        try:
            # Generate audit name if not provided
            audit_name = audit_data.get("auditName")
            if not audit_name:
                audit_name = await self.generate_audit_name(question)
            print(f"Creating audit with name: {audit_name}")
            
            # Generate unique audit ID
            audit_id = f"audit_{uuid4().hex[:8]}"
            
            # Create audit
            audit = Audit(
                auditName=audit_name,
                messageid=audit_data.get("message_id"),
                user_id=audit_data.get("user_id"),
                steps=audit_data.get("steps",0)
            )
            
            self.db.add(audit)
            self.db.commit()
            self.db.refresh(audit)
            
            logger.info(f"Created audit {audit_id} for user {audit_data.get('user_id')}")
            return AuditResponse.from_orm(audit)
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating audit: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Failed to create audit due to data integrity issue: {str(e)}")
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error creating audit: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Database error creating audit: {str(e)}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error creating audit: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Unexpected error creating audit: {str(e)}")
    
    async def get_audit_by_id(self, audit_id: str) -> Optional[AuditResponse]:
        """Get audit by ID"""
        try:
            audit = self.db.query(Audit).filter(Audit.auditid == audit_id).first()
            if audit:
                # Update total time
                audit.total_time = audit.calculate_total_time()
                self.db.commit()
                return AuditResponse.from_orm(audit)
            return None
        except SQLAlchemyError as e:
            logger.error(f"Database error getting audit {audit_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Database error retrieving audit: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting audit {audit_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Unexpected error retrieving audit: {str(e)}")
    
    async def get_audits(self, filters: AuditFilters) -> PaginatedAuditResponse:
        """Get audits with all filter options and cursor pagination"""
        try:
            print("Entered get _audits method")
            # Build query with all filters
            query = self._build_query(filters)
            results = query.all()
            # Process results
            audits = []
            for audit in results:
                # Get thread name safely
                thread_name = None
                thread_id = None
                if (hasattr(audit, 'thread_message') and audit.thread_message and 
                    hasattr(audit.thread_message, 'thread') and audit.thread_message.thread):
                    thread_name = audit.thread_message.thread.title
                    thread_id = audit.thread_message.thread.id
                # Calculate total time
                if hasattr(audit, 'calculate_total_time'):
                    audit.total_time = audit.calculate_total_time()
                audit_data = AuditResponse(
                    auditid=audit.auditid,
                    auditName=audit.auditName,
                    messageid=audit.messageid,
                    timestamp=audit.timestamp,
                    total_time=audit.total_time,
                    threadid=thread_id,
                    threadName=thread_name,
                    steps=audit.steps,
                    user_id=audit.user_id,
                    traces=[{
                        'trace_id': t.trace_id,
                        'sequence': t.sequence,
                        'timestamp':t.timestamp,
                        'component': t.component,
                        'input_data':t.input_data,
                        'output_data':t.output_data,
                        'status': t.status,
                        'time_taken': t.time_taken
                    } for t in audit.traces]
                )
                audits.append(audit_data)
            # Create response
            has_more = len(audits) == filters.limit
            next_cursor = audits[-1].timestamp.isoformat().replace('+00:00', 'Z') if has_more and audits else None
            return PaginatedAuditResponse(
                audits=audits,
                next_cursor=next_cursor,
                has_more=has_more,
                count=len(audits)
            )
        except SQLAlchemyError as e:
            traceback.print_exc()
            logger.error(f"Database error: {e}")
            raise Exception(f"Database error: {e}")
    
    def _build_query(self, filters: AuditFilters):
        """Build query with all filters"""
        query = (self.db.query(Audit)
                .options(
                    joinedload(Audit.traces),
                    joinedload(Audit.thread_message),
                    joinedload(Audit.thread_message, ThreadMessage.thread)
                )
                .filter(Audit.user_id == filters.user_id))
        # Thread filter
        if filters.thread_id:
            query = query.join(ThreadMessage).filter(ThreadMessage.thread_id == filters.thread_id)
        # Date range filter
        if filters.start_date:
            query = query.filter(Audit.timestamp >= filters.start_date)
        if filters.end_date:
            query = query.filter(Audit.timestamp <= filters.end_date)
        # Cursor filter (for pagination)
        cursor_datetime = filters.get_cursor_datetime()
        if cursor_datetime:
            query = query.filter(Audit.timestamp < cursor_datetime)
        # Order and limit
        return query.order_by(Audit.timestamp.desc()).limit(filters.limit)
    
    async def get_audit_records(self, user_id: str, **kwargs) -> PaginatedAuditResponse:
        """Simple method with keyword arguments"""
        try:

            filters = AuditFilters(user_id=user_id, **kwargs)
            return await self.get_audits(filters)
        except Exception as e:
            print(f"Errorr Started here==========================")
            traceback.print_exc()
            print(f"Error ended here =========== {e}")

    async def update_audit(self, audit_id: str, audit_data: AuditUpdate) -> Optional[AuditResponse]:
        """Update audit"""
        try:
            audit = self.db.query(Audit).filter(Audit.auditid == audit_id).first()
            if not audit:
                return None
            
            # Update fields
            if audit_data.auditName is not None:
                audit.auditName = audit_data.auditName
            if audit_data.steps is not None:
                audit.steps = audit_data.steps
            
            # Recalculate total time
            audit.total_time = audit.calculate_total_time()
            
            self.db.commit()
            self.db.refresh(audit)
            
            logger.info(f"Updated audit {audit_id}")
            return AuditResponse.from_orm(audit)
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error updating audit {audit_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Database error updating audit: {str(e)}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error updating audit {audit_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Unexpected error updating audit: {str(e)}")
    
    async def delete_audit(self, audit_id: str) -> bool:
        """Delete audit and all associated traces"""
        try:
            audit = self.db.query(Audit).filter(Audit.auditid == audit_id).first()
            if audit:
                self.db.delete(audit)
                self.db.commit()
                logger.info(f"Deleted audit {audit_id}")
                return True
            return False
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error deleting audit {audit_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Database error deleting audit: {str(e)}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error deleting audit {audit_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Unexpected error deleting audit: {str(e)}")
    
    async def recalculate_audit_time(self, audit_id: str) -> Optional[AuditResponse]:
        """Manually recalculate audit total time from traces"""
        try:
            audit = self.db.query(Audit).filter(Audit.auditid == audit_id).first()
            if audit:
                audit.total_time = audit.calculate_total_time()
                self.db.commit()
                self.db.refresh(audit)
                logger.info(f"Recalculated total time for audit {audit_id}: {audit.total_time}s")
                return AuditResponse.from_orm(audit)
            return None
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error recalculating audit time {audit_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Database error recalculating audit time: {str(e)}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error recalculating audit time {audit_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Unexpected error recalculating audit time: {str(e)}")
    

    async def create_trace(self, trace_data: TraceCreate) -> TraceResponse:
        """Create a new trace"""
        try:
            # Generate unique trace ID
            trace_id = f"trace_{uuid4().hex[:8]}"
            
            trace = Trace(
                auditid=trace_data.auditid,
                sequence=trace_data.sequence,
                component=trace_data.component,
                status=trace_data.status,
                input_data=trace_data.input_data,
                output_data=trace_data.output_data,
                time_taken=trace_data.time_taken
            )
            
            self.db.add(trace)
            self.db.commit()
            self.db.refresh(trace)
            
            # Update parent audit's total time
            await self._update_audit_total_time(trace_data.auditid)
            
            logger.info(f"Created trace {trace_id} for audit {trace_data.auditid}")
            return TraceResponse.from_orm(trace)
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating trace: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Failed to create trace due to data integrity issue: {str(e)}")
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error creating trace: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Database error creating trace: {str(e)}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error creating trace: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Unexpected error creating trace: {str(e)}")
    
    async def get_trace_by_id(self, trace_id: str) -> Optional[TraceResponse]:
        """Get trace by ID"""
        try:
            trace = self.db.query(Trace).filter(Trace.trace_id == trace_id).first()
            return TraceResponse.from_orm(trace) if trace else None
        except SQLAlchemyError as e:
            logger.error(f"Database error getting trace {trace_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Database error retrieving trace: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting trace {trace_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Unexpected error retrieving trace: {str(e)}")
    
    async def update_trace(self, trace_id: str, trace_data: TraceUpdate) -> Optional[TraceResponse]:
        """Update trace"""
        try:
            trace = self.db.query(Trace).filter(Trace.trace_id == trace_id).first()
            if not trace:
                return None
            
            # Update fields
            if trace_data.component is not None:
                trace.component = trace_data.component
            if trace_data.status is not None:
                trace.status = trace_data.status
            if trace_data.input_data is not None:
                trace.input_data = trace_data.input_data
            if trace_data.output_data is not None:
                trace.output_data = trace_data.output_data
            if trace_data.time_taken is not None:
                trace.time_taken = trace_data.time_taken
            
            self.db.commit()
            self.db.refresh(trace)
            
            # Update parent audit's total time
            await self._update_audit_total_time(trace.auditid)
            
            logger.info(f"Updated trace {trace_id}")
            return TraceResponse.from_orm(trace)
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error updating trace {trace_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Database error updating trace: {str(e)}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error updating trace {trace_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Unexpected error updating trace: {str(e)}")
    
    async def get_traces_by_audit(self, audit_id: str) -> List[TraceResponse]:
        """Get all traces for an audit"""
        try:
            traces = (self.db.query(Trace)
                     .filter(Trace.auditid == audit_id)
                     .order_by(Trace.sequence)
                     .all())
            
            return [TraceResponse.from_orm(trace) for trace in traces]
        except SQLAlchemyError as e:
            logger.error(f"Database error getting traces for audit {audit_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Database error retrieving traces: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error getting traces for audit {audit_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Unexpected error retrieving traces: {str(e)}")
    
    async def delete_trace(self, trace_id: str) -> bool:
        """Delete a trace"""
        try:
            trace = self.db.query(Trace).filter(Trace.trace_id == trace_id).first()
            if trace:
                audit_id = trace.auditid
                self.db.delete(trace)
                self.db.commit()
                
                # Update parent audit's total time
                await self._update_audit_total_time(audit_id)
                
                logger.info(f"Deleted trace {trace_id}")
                return True
            return False
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error deleting trace {trace_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Database error deleting trace: {str(e)}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Unexpected error deleting trace {trace_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Unexpected error deleting trace: {str(e)}")
    
    async def create_traces_bulk(self, audit_id: str, components: List[str]) -> List[TraceResponse]:
        """Create multiple traces for an audit (bulk operation)"""
        try:
            traces = []
            for i, component in enumerate(components, 1):
                trace_create = TraceCreate(
                    auditid=audit_id,
                    sequence=i,
                    component=component,
                    status='pending'
                )
                trace_response = await self.create_trace(trace_create)
                traces.append(trace_response)
            
            logger.info(f"Created {len(traces)} traces for audit {audit_id}")
            return traces
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating bulk traces for audit {audit_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Failed to create bulk traces: {str(e)}")
    
    async def update_trace_status(self, trace_id: str, status: str, 
                                 output_data: Optional[dict] = None,
                                 time_taken: Optional[float] = None) -> Optional[TraceResponse]:
        """Convenience method to update trace status with optional output and time"""
        try:
            trace_update = TraceUpdate(
                status=status,
                output_data=output_data,
                time_taken=time_taken
            )
            return await self.update_trace(trace_id, trace_update)
        except Exception as e:
            logger.error(f"Error updating trace status {trace_id}: {str(e)}\n{traceback.format_exc()}")
            raise AuditServiceError(f"Failed to update trace status: {str(e)}")
    
    async def _update_audit_total_time(self, audit_id: str):
        """Internal method to update audit total time"""
        try:
            audit = self.db.query(Audit).options(joinedload(Audit.traces)).filter(Audit.auditid == audit_id).first()
            if audit:
                audit.total_time = audit.calculate_total_time()
                audit.steps = len(audit.traces)
                
                self.db.commit()
        except Exception as e:
            logger.error(f"Error updating audit total time for {audit_id}: {str(e)}")
    
    async def generate_audit_name(self, question: str, max_words: int = 5) -> str:
        """Generate audit name from question using keywords extraction"""
        try:
            if not question or not question.strip():
                return "general-audit"
            
            # Use NLTK/Rake if available
            if Rake is not None:
                try:
                    r = Rake()
                    r.extract_keywords_from_text(question)
                    phrases = r.get_ranked_phrases()
                    
                    if phrases:
                        # Take top phrase, limit number of words, slugify style
                        top_keywords = phrases[0].lower().split()[:max_words]
                        audit_name = "-".join(word for word in top_keywords if word.isalnum())
                        return audit_name if audit_name else "general-audit"
                except Exception as e:
                    logger.warning(f"Error using RAKE for keyword extraction: {str(e)}")
            
            # Fallback method: simple word extraction
            words = question.lower().split()
            # Remove common stop words manually
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'}
            filtered_words = [word for word in words if word not in stop_words and word.isalnum()]
            
            if filtered_words:
                audit_name = "-".join(filtered_words[:max_words])
                return audit_name
            
            return "general-audit"
            
        except Exception as e:
            logger.error(f"Error generating audit name: {str(e)}\n{traceback.format_exc()}")
            return "general-audit"