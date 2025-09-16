import uuid
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Union
from enum import Enum
import pandas as pd
from decimal import Decimal

# External libraries
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# Internal imports (extending previous services)
from app.models.dbmodels import Document, DocumentInsight
from app.services.vectorstore.documentstore import DocumentChromaStore
from structured_extraction_service import (
    StructuredEntity, StructuredField, EntityType, 
    StructuredExtractionService, ExtractionWorkflow
)

logger = logging.getLogger(__name__)


class InvoiceStatus(Enum):
    """Invoice processing status"""
    RECEIVED = "received"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    OVERDUE = "overdue"


class PaymentTerms(Enum):
    """Payment terms enumeration"""
    NET_15 = "net_15"
    NET_30 = "net_30"
    NET_45 = "net_45"
    NET_60 = "net_60"
    DUE_ON_RECEIPT = "due_on_receipt"
    CASH_ON_DELIVERY = "cash_on_delivery"


@dataclass
class VendorInfo:
    """Structured vendor information"""
    vendor_id: str
    vendor_name: str
    vendor_address: str
    tax_id: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    vendor_category: Optional[str] = None  # e.g., "office_supplies", "software", "consulting"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor_name,
            "vendor_address": self.vendor_address,
            "tax_id": self.tax_id,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "vendor_category": self.vendor_category
        }


@dataclass
class InvoiceLineItem:
    """Individual line item on an invoice"""
    line_number: int
    description: str
    quantity: float
    unit_price: Decimal
    total_amount: Decimal
    product_code: Optional[str] = None
    category: Optional[str] = None
    tax_amount: Optional[Decimal] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_number": self.line_number,
            "description": self.description,
            "quantity": float(self.quantity),
            "unit_price": float(self.unit_price),
            "total_amount": float(self.total_amount),
            "product_code": self.product_code,
            "category": self.category,
            "tax_amount": float(self.tax_amount) if self.tax_amount else None
        }


@dataclass
class InvoiceHeader:
    """Main invoice header information"""
    invoice_number: str
    invoice_date: date
    due_date: date
    po_number: Optional[str] = None
    payment_terms: Optional[PaymentTerms] = None
    currency: str = "USD"
    total_amount: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date.isoformat(),
            "due_date": self.due_date.isoformat(),
            "po_number": self.po_number,
            "payment_terms": self.payment_terms.value if self.payment_terms else None,
            "currency": self.currency,
            "total_amount": float(self.total_amount) if self.total_amount else None,
            "tax_amount": float(self.tax_amount) if self.tax_amount else None,
            "subtotal": float(self.subtotal) if self.subtotal else None
        }


@dataclass
class ProcessedInvoice:
    """Complete processed invoice with all extracted data"""
    invoice_id: str
    document_id: str
    vendor_info: VendorInfo
    invoice_header: InvoiceHeader
    line_items: List[InvoiceLineItem]
    status: InvoiceStatus
    extraction_confidence: float
    processing_timestamp: str
    extracted_insights: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "invoice_id": self.invoice_id,
            "document_id": self.document_id,
            "vendor_info": self.vendor_info.to_dict(),
            "invoice_header": self.invoice_header.to_dict(),
            "line_items": [item.to_dict() for item in self.line_items],
            "status": self.status.value,
            "extraction_confidence": self.extraction_confidence,
            "processing_timestamp": self.processing_timestamp,
            "extracted_insights": self.extracted_insights
        }


# Data Models for Analytics and Predictions

@dataclass
class VendorPerformanceMetrics:
    """Metrics for vendor analysis and flux prediction"""
    vendor_id: str
    vendor_name: str
    total_invoices: int
    total_spend: Decimal
    average_invoice_amount: Decimal
    payment_accuracy_rate: float  # % of invoices paid on time
    invoice_accuracy_rate: float  # % of invoices without discrepancies
    average_processing_time_days: float
    last_invoice_date: date
    spending_trend: str  # "increasing", "decreasing", "stable"
    risk_score: float  # 0.0 to 1.0, higher = riskier
    
    # Time series data for flux analysis
    monthly_spend_history: List[Dict[str, Any]] = field(default_factory=list)
    invoice_frequency_pattern: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CategorySpendAnalysis:
    """Spend analysis by category for PO predictions"""
    category: str
    total_spend: Decimal
    invoice_count: int
    unique_vendors: int
    average_invoice_amount: Decimal
    seasonal_patterns: Dict[str, float]  # month -> spend multiplier
    growth_rate: float  # year-over-year growth
    volatility_score: float  # spending predictability
    top_vendors: List[Dict[str, Any]]


@dataclass
class POPredictionFeatures:
    """Features extracted for PO prediction models"""
    historical_spend_by_month: List[float]
    vendor_concentration_ratio: float  # top 3 vendors / total spend
    invoice_frequency_patterns: Dict[str, float]  # day_of_week -> frequency
    seasonal_adjustment_factors: Dict[str, float]  # month -> multiplier
    category_correlations: Dict[str, float]  # category -> correlation coefficient
    payment_term_preferences: Dict[str, float]  # payment_term -> frequency
    average_order_values: List[float]  # by month
    vendor_reliability_scores: Dict[str, float]  # vendor_id -> reliability


# Pydantic schemas for LLM extraction

class InvoiceExtractionSchema(BaseModel):
    """Schema for extracting structured invoice data"""
    vendor_name: str = Field(description="Name of the vendor/supplier")
    vendor_address: str = Field(description="Vendor address")
    vendor_tax_id: Optional[str] = Field(description="Vendor tax ID or registration number")
    invoice_number: str = Field(description="Invoice number")
    invoice_date: str = Field(description="Invoice date in YYYY-MM-DD format")
    due_date: str = Field(description="Payment due date in YYYY-MM-DD format")
    po_number: Optional[str] = Field(description="Purchase order number if referenced")
    payment_terms: Optional[str] = Field(description="Payment terms (e.g., Net 30)")
    currency: str = Field(description="Currency code (e.g., USD, EUR)")
    line_items: List[Dict[str, Any]] = Field(description="List of invoice line items")
    subtotal: Optional[float] = Field(description="Subtotal amount before tax")
    tax_amount: Optional[float] = Field(description="Total tax amount")
    total_amount: float = Field(description="Total invoice amount")
    confidence_scores: Dict[str, float] = Field(description="Confidence scores for each extracted field")


class InvoiceInsightsSchema(BaseModel):
    """Schema for extracting business insights from invoices"""
    vendor_category: str = Field(description="Category of vendor (e.g., office supplies, software)")
    spend_category: str = Field(description="Category of spending")
    payment_urgency: str = Field(description="Payment urgency level: high, medium, low")
    anomaly_flags: List[str] = Field(description="Any unusual patterns or potential issues")
    seasonal_indicators: List[str] = Field(description="Indicators of seasonal spending patterns")
    cost_optimization_opportunities: List[str] = Field(description="Potential cost saving opportunities")
    vendor_risk_factors: List[str] = Field(description="Risk factors related to this vendor")
    compliance_flags: List[str] = Field(description="Any compliance or regulatory flags")


class InvoiceAnalysisExtractor:
    """Specialized extractor for invoice analysis"""
    
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.1):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.setup_extraction_chains()
    
    def setup_extraction_chains(self):
        """Set up specialized invoice extraction chains"""
        
        # Invoice data extraction chain
        invoice_template = """
        You are an expert at extracting structured data from invoices and receipts.
        
        Invoice Content:
        {content}
        
        Extract the following information with high accuracy:
        
        1. VENDOR INFORMATION:
           - Vendor name, address, tax ID
           - Contact information if available
        
        2. INVOICE DETAILS:
           - Invoice number, date, due date
           - PO number if referenced
           - Payment terms (Net 15, Net 30, etc.)
           - Currency
        
        3. LINE ITEMS:
           - Description, quantity, unit price, total
           - Product codes if available
           - Tax information per item
        
        4. TOTALS:
           - Subtotal, tax amount, total amount
           - Any discounts applied
        
        5. CONFIDENCE SCORES:
           - Assign confidence scores (0.0-1.0) for each extracted field
           - Lower confidence for unclear or ambiguous data
        
        Be very careful with:
        - Date formats (convert to YYYY-MM-DD)
        - Currency amounts (preserve precision)
        - Line item calculations (verify they add up)
        - Tax calculations
        
        {format_instructions}
        """
        
        invoice_prompt = ChatPromptTemplate.from_template(invoice_template)
        invoice_parser = PydanticOutputParser(pydantic_object=InvoiceExtractionSchema)
        self.invoice_chain = invoice_prompt | self.llm | invoice_parser
        
        # Business insights extraction chain
        insights_template = """
        You are a business analyst specializing in accounts payable and vendor management.
        
        Invoice Content:
        {content}
        
        Extracted Invoice Data:
        {invoice_data}
        
        Analyze this invoice and provide business insights:
        
        1. CATEGORIZATION:
           - What category of vendor is this? (software, office supplies, consulting, etc.)
           - What type of spending does this represent?
        
        2. RISK ASSESSMENT:
           - Payment urgency based on terms and amount
           - Any red flags or unusual patterns
           - Vendor risk factors
        
        3. BUSINESS INTELLIGENCE:
           - Seasonal spending indicators
           - Cost optimization opportunities
           - Compliance or regulatory considerations
        
        4. ANOMALY DETECTION:
           - Unusual amounts, frequencies, or patterns
           - Potential duplicate charges
           - Missing information that could cause issues
        
        Focus on insights that would be valuable for:
        - Cash flow management
        - Vendor relationship optimization
        - Spend analysis and forecasting
        - Risk mitigation
        
        {format_instructions}
        """
        
        insights_prompt = ChatPromptTemplate.from_template(insights_template)
        insights_parser = PydanticOutputParser(pydantic_object=InvoiceInsightsSchema)
        self.insights_chain = insights_prompt | self.llm | insights_parser
    
    def extract_invoice_data(self, content: str) -> InvoiceExtractionSchema:
        """Extract structured invoice data"""
        try:
            logger.info("Extracting structured invoice data")
            
            result = self.invoice_chain.invoke({
                "content": content[:12000],  # Invoices can be detailed
                "format_instructions": PydanticOutputParser(pydantic_object=InvoiceExtractionSchema).get_format_instructions()
            })
            
            logger.info(f"Extracted invoice data with confidence scores: {result.confidence_scores}")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting invoice data: {e}")
            raise
    
    def extract_business_insights(self, content: str, invoice_data: InvoiceExtractionSchema) -> InvoiceInsightsSchema:
        """Extract business insights from invoice"""
        try:
            logger.info("Extracting business insights from invoice")
            
            result = self.insights_chain.invoke({
                "content": content[:8000],
                "invoice_data": json.dumps(invoice_data.dict(), indent=2),
                "format_instructions": PydanticOutputParser(pydantic_object=InvoiceInsightsSchema).get_format_instructions()
            })
            
            logger.info(f"Extracted insights: {len(result.anomaly_flags)} anomalies, {len(result.cost_optimization_opportunities)} optimization opportunities")
            return result
            
        except Exception as e:
            logger.error(f"Error extracting business insights: {e}")
            raise


class InvoiceProcessor:
    """Main invoice processing class"""
    
    def __init__(self, extractor: InvoiceAnalysisExtractor = None):
        self.extractor = extractor or InvoiceAnalysisExtractor()
        self.processed_invoices: Dict[str, ProcessedInvoice] = {}
    
    def process_invoice(self, document: Document) -> ProcessedInvoice:
        """Process a complete invoice document"""
        try:
            logger.info(f"Processing invoice document {document.id}")
            
            # Extract structured data
            invoice_data = self.extractor.extract_invoice_data(document.content)
            
            # Extract business insights
            insights = self.extractor.extract_business_insights(document.content, invoice_data)
            
            # Create structured objects
            vendor_info = VendorInfo(
                vendor_id=self._generate_vendor_id(invoice_data.vendor_name),
                vendor_name=invoice_data.vendor_name,
                vendor_address=invoice_data.vendor_address,
                tax_id=invoice_data.vendor_tax_id,
                vendor_category=insights.vendor_category
            )
            
            invoice_header = InvoiceHeader(
                invoice_number=invoice_data.invoice_number,
                invoice_date=datetime.strptime(invoice_data.invoice_date, "%Y-%m-%d").date(),
                due_date=datetime.strptime(invoice_data.due_date, "%Y-%m-%d").date(),
                po_number=invoice_data.po_number,
                payment_terms=self._parse_payment_terms(invoice_data.payment_terms),
                currency=invoice_data.currency,
                total_amount=Decimal(str(invoice_data.total_amount)),
                tax_amount=Decimal(str(invoice_data.tax_amount)) if invoice_data.tax_amount else None,
                subtotal=Decimal(str(invoice_data.subtotal)) if invoice_data.subtotal else None
            )
            
            # Process line items
            line_items = []
            for i, item_data in enumerate(invoice_data.line_items):
                line_item = InvoiceLineItem(
                    line_number=i + 1,
                    description=item_data.get("description", ""),
                    quantity=float(item_data.get("quantity", 0)),
                    unit_price=Decimal(str(item_data.get("unit_price", 0))),
                    total_amount=Decimal(str(item_data.get("total", 0))),
                    product_code=item_data.get("product_code"),
                    category=insights.spend_category
                )
                line_items.append(line_item)
            
            # Calculate overall confidence
            confidence_scores = list(invoice_data.confidence_scores.values())
            overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.8
            
            # Create processed invoice
            processed_invoice = ProcessedInvoice(
                invoice_id=str(uuid.uuid4()),
                document_id=str(document.id),
                vendor_info=vendor_info,
                invoice_header=invoice_header,
                line_items=line_items,
                status=InvoiceStatus.PROCESSING,
                extraction_confidence=overall_confidence,
                processing_timestamp=datetime.now().isoformat(),
                extracted_insights={
                    "vendor_category": insights.vendor_category,
                    "spend_category": insights.spend_category,
                    "payment_urgency": insights.payment_urgency,
                    "anomaly_flags": insights.anomaly_flags,
                    "seasonal_indicators": insights.seasonal_indicators,
                    "cost_optimization_opportunities": insights.cost_optimization_opportunities,
                    "vendor_risk_factors": insights.vendor_risk_factors,
                    "compliance_flags": insights.compliance_flags
                }
            )
            
            # Store processed invoice
            self.processed_invoices[processed_invoice.invoice_id] = processed_invoice
            
            logger.info(f"Successfully processed invoice {processed_invoice.invoice_id}")
            return processed_invoice
            
        except Exception as e:
            logger.error(f"Error processing invoice: {e}")
            raise
    
    def _generate_vendor_id(self, vendor_name: str) -> str:
        """Generate a consistent vendor ID"""
        import hashlib
        normalized_name = vendor_name.lower().strip().replace(" ", "_")
        hash_suffix = hashlib.md5(normalized_name.encode()).hexdigest()[:8]
        return f"vendor_{normalized_name}_{hash_suffix}"
    
    def _parse_payment_terms(self, terms_str: Optional[str]) -> Optional[PaymentTerms]:
        """Parse payment terms string to enum"""
        if not terms_str:
            return None
        
        terms_lower = terms_str.lower()
        if "net 15" in terms_lower or "net15" in terms_lower:
            return PaymentTerms.NET_15
        elif "net 30" in terms_lower or "net30" in terms_lower:
            return PaymentTerms.NET_30
        elif "net 45" in terms_lower or "net45" in terms_lower:
            return PaymentTerms.NET_45
        elif "net 60" in terms_lower or "net60" in terms_lower:
            return PaymentTerms.NET_60
        elif "due on receipt" in terms_lower:
            return PaymentTerms.DUE_ON_RECEIPT
        elif "cash on delivery" in terms_lower or "cod" in terms_lower:
            return PaymentTerms.CASH_ON_DELIVERY
        
        return PaymentTerms.NET_30  # Default fallback


class InvoiceAnalyticsBuilder:
    """Builds analytics data structures for flux analysis and PO predictions"""
    
    def __init__(self):
        self.processed_invoices: List[ProcessedInvoice] = []
    
    def add_invoices(self, invoices: List[ProcessedInvoice]):
        """Add processed invoices to analytics dataset"""
        self.processed_invoices.extend(invoices)
        logger.info(f"Added {len(invoices)} invoices to analytics dataset. Total: {len(self.processed_invoices)}")
    
    def build_vendor_performance_metrics(self) -> List[VendorPerformanceMetrics]:
        """Build vendor performance metrics for analysis"""
        vendor_groups = {}
        
        # Group invoices by vendor
        for invoice in self.processed_invoices:
            vendor_id = invoice.vendor_info.vendor_id
            if vendor_id not in vendor_groups:
                vendor_groups[vendor_id] = []
            vendor_groups[vendor_id].append(invoice)
        
        metrics = []
        for vendor_id, vendor_invoices in vendor_groups.items():
            vendor_name = vendor_invoices[0].vendor_info.vendor_name
            total_spend = sum(invoice.invoice_header.total_amount for invoice in vendor_invoices)
            avg_amount = total_spend / len(vendor_invoices)
            
            # Build monthly spend history
            monthly_spend = {}
            for invoice in vendor_invoices:
                month_key = f"{invoice.invoice_header.invoice_date.year}-{invoice.invoice_header.invoice_date.month:02d}"
                if month_key not in monthly_spend:
                    monthly_spend[month_key] = Decimal('0')
                monthly_spend[month_key] += invoice.invoice_header.total_amount
            
            monthly_history = [
                {"month": month, "spend": float(amount)}
                for month, amount in sorted(monthly_spend.items())
            ]
            
            # Calculate trends and patterns
            spending_trend = self._calculate_spending_trend(monthly_history)
            risk_score = self._calculate_vendor_risk_score(vendor_invoices)
            
            vendor_metrics = VendorPerformanceMetrics(
                vendor_id=vendor_id,
                vendor_name=vendor_name,
                total_invoices=len(vendor_invoices),
                total_spend=total_spend,
                average_invoice_amount=avg_amount,
                payment_accuracy_rate=0.95,  # Would be calculated from payment history
                invoice_accuracy_rate=0.98,  # Would be calculated from discrepancy tracking
                average_processing_time_days=3.5,  # Would be calculated from processing timestamps
                last_invoice_date=max(invoice.invoice_header.invoice_date for invoice in vendor_invoices),
                spending_trend=spending_trend,
                risk_score=risk_score,
                monthly_spend_history=monthly_history,
                invoice_frequency_pattern=[]  # Would be calculated from invoice timing
            )
            
            metrics.append(vendor_metrics)
        
        return metrics
    
    def build_category_spend_analysis(self) -> List[CategorySpendAnalysis]:
        """Build category spend analysis for forecasting"""
        category_groups = {}
        
        # Group by spend category
        for invoice in self.processed_invoices:
            category = invoice.extracted_insights.get("spend_category", "uncategorized")
            if category not in category_groups:
                category_groups[category] = []
            category_groups[category].append(invoice)
        
        analyses = []
        for category, category_invoices in category_groups.items():
            total_spend = sum(invoice.invoice_header.total_amount for invoice in category_invoices)
            unique_vendors = len(set(invoice.vendor_info.vendor_id for invoice in category_invoices))
            avg_amount = total_spend / len(category_invoices)
            
            # Calculate seasonal patterns
            seasonal_patterns = self._calculate_seasonal_patterns(category_invoices)
            
            # Top vendors for this category
            vendor_spend = {}
            for invoice in category_invoices:
                vendor_id = invoice.vendor_info.vendor_id
                vendor_name = invoice.vendor_info.vendor_name
                if vendor_id not in vendor_spend:
                    vendor_spend[vendor_id] = {"name": vendor_name, "spend": Decimal('0')}
                vendor_spend[vendor_id]["spend"] += invoice.invoice_header.total_amount
            
            top_vendors = sorted(
                [{"vendor_id": vid, "vendor_name": data["name"], "spend": float(data["spend"])}
                 for vid, data in vendor_spend.items()],
                key=lambda x: x["spend"],
                reverse=True
            )[:5]
            
            analysis = CategorySpendAnalysis(
                category=category,
                total_spend=total_spend,
                invoice_count=len(category_invoices),
                unique_vendors=unique_vendors,
                average_invoice_amount=avg_amount,
                seasonal_patterns=seasonal_patterns,
                growth_rate=0.15,  # Would be calculated from historical data
                volatility_score=0.3,  # Would be calculated from spend variance
                top_vendors=top_vendors
            )
            
            analyses.append(analysis)
        
        return analyses
    
    def build_po_prediction_features(self) -> POPredictionFeatures:
        """Build feature set for PO prediction models"""
        
        # Historical spend by month
        monthly_totals = {}
        for invoice in self.processed_invoices:
            month_key = f"{invoice.invoice_header.invoice_date.year}-{invoice.invoice_header.invoice_date.month:02d}"
            if month_key not in monthly_totals:
                monthly_totals[month_key] = Decimal('0')
            monthly_totals[month_key] += invoice.invoice_header.total_amount
        
        historical_spend = [float(amount) for amount in monthly_totals.values()]
        
        # Vendor concentration
        vendor_spend = {}
        total_spend = sum(invoice.invoice_header.total_amount for invoice in self.processed_invoices)
        
        for invoice in self.processed_invoices:
            vendor_id = invoice.vendor_info.vendor_id
            if vendor_id not in vendor_spend:
                vendor_spend[vendor_id] = Decimal('0')
            vendor_spend[vendor_id] += invoice.invoice_header.total_amount
        
        top_3_spend = sum(sorted(vendor_spend.values(), reverse=True)[:3])
        concentration_ratio = float(top_3_spend / total_spend) if total_spend > 0 else 0
        
        # Payment term preferences
        payment_terms_count = {}
        for invoice in self.processed_invoices:
            terms = invoice.invoice_header.payment_terms
            if terms:
                if terms.value not in payment_terms_count:
                    payment_terms_count[terms.value] = 0
                payment_terms_count[terms.value] += 1
        
        total_invoices = len(self.processed_invoices)
        payment_term_prefs = {
            term: count / total_invoices
            for term, count in payment_terms_count.items()
        }
        
        features = POPredictionFeatures(
            historical_spend_by_month=historical_spend,
            vendor_concentration_ratio=concentration_ratio,
            invoice_frequency_patterns={},  # Would be calculated from invoice timing
            seasonal_adjustment_factors={},  # Would be calculated from seasonal analysis
            category_correlations={},  # Would be calculated from category relationships
            payment_term_preferences=payment_term_prefs,
            average_order_values=historical_spend,  # Simplified for example
            vendor_reliability_scores={}  # Would be calculated from vendor performance
        )
        
        return features
    
    def _calculate_spending_trend(self, monthly_history: List[Dict[str, Any]]) -> str:
        """Calculate spending trend from monthly history"""
        if len(monthly_history) < 3:
            return "insufficient_data"
        
        recent_avg = sum(item["spend"] for item in monthly_history[-3:]) / 3
        older_avg = sum(item["spend"] for item in monthly_history[-6:-3]) / 3 if len(monthly_history) >= 6 else recent_avg
        
        if recent_avg > older_avg * 1.1:
            return "increasing"
        elif recent_avg < older_avg * 0.9:
            return "decreasing"
        else:
            return "stable"
    
    def _calculate_vendor_risk_score(self, vendor_invoices: List[ProcessedInvoice]) -> float:
        """Calculate vendor risk score based on various factors"""
        risk_factors = 0
        total_factors = 5  # Number of risk factors we're checking
        
        # Check for anomaly flags
        total_anomalies = sum(len(invoice.extracted_insights.get("anomaly_flags", [])) for invoice in vendor_invoices)
        if total_anomalies > len(vendor_invoices) * 0.1:  # More than 10% of invoices have anomalies
            risk_factors += 1
        
        # Check payment urgency
        high_urgency_count = sum(1 for invoice in vendor_invoices 
                               if invoice.extracted_insights.get("payment_urgency") == "high")
        if high_urgency_count > len(vendor_invoices) * 0.3:  # More than 30% high urgency
            risk_factors += 1
        
        # Check vendor risk factors
        total_risk_factors = sum(len(invoice.extracted_insights.get("vendor_risk_factors", [])) 
                               for invoice in vendor_invoices)
        if total_risk_factors > 0:
            risk_factors += 1
        
        # Check compliance flags
        total_compliance_flags = sum(len(invoice.extracted_insights.get("compliance_flags", [])) 
                                   for invoice in vendor_invoices)
        if total_compliance_flags > 0:
            risk_factors += 1
        
        # Check invoice amount variability
        amounts = [float(invoice.invoice_header.total_amount) for invoice in vendor_invoices]
        if len(amounts) > 1:
            avg_amount = sum(amounts) / len(amounts)
            variance = sum((amt - avg_amount) ** 2 for amt in amounts) / len(amounts)
            cv = (variance ** 0.5) / avg_amount if avg_amount > 0 else 0
            if cv > 0.5:  # High coefficient of variation
                risk_factors += 1
        
        return risk_factors / total_factors
    
    def _calculate_seasonal_patterns(self, invoices: List[ProcessedInvoice]) -> Dict[str, float]:
        """Calculate seasonal spending patterns"""
        monthly_spend = {}
        
        for invoice in invoices:
            month = invoice.invoice_header.invoice_date.month
            if month not in monthly_spend:
                monthly_spend[month] = []
            monthly_spend[month].append(float(invoice.invoice_header.total_amount))
        
        # Calculate average spend per month
        monthly_averages = {}
        for month, amounts in monthly_spend.items():
            monthly_averages[month] = sum(amounts) / len(amounts)
        
        # Calculate multipliers relative to overall average
        overall_avg = sum(monthly_averages.values()) / len(monthly_averages)
        seasonal_patterns = {}
        
        for month in range(1, 13):
            if month in monthly_averages:
                multiplier = monthly_averages[month] / overall_avg
            else:
                multiplier = 1.0  # No data, assume average
            seasonal_patterns[f"month_{month:02d}"] = multiplier
        
        return seasonal_patterns


# Example usage and integration
class InvoiceAnalysisService:
    """Complete service for invoice analysis and analytics preparation"""
    
    def __init__(self, structured_extraction_service: StructuredExtractionService = None):
        self.processor = InvoiceProcessor()
        self.analytics_builder = InvoiceAnalyticsBuilder()
        self.structured_service = structured_extraction_service
        
    def process_invoice_document(self, document: Document) -> Tuple[ProcessedInvoice, DocumentInsight]:
        """Process invoice and create analytics-ready data"""
        
        # Process invoice with specialized extractor
        processed_invoice = self.processor.process_invoice(document)
        
        # Create DocumentInsight for integration with existing system
        document_insight = DocumentInsight(
            id=str(uuid.uuid4()),
            document_id=str(document.id),
            phrases=[item.description for item in processed_invoice.line_items],
            insight=processed_invoice.extracted_insights,
            source_type=document.source_type,
            document_type="invoice",
            extracted_entities={
                "vendor_info": processed_invoice.vendor_info.to_dict(),
                "invoice_header": processed_invoice.invoice_header.to_dict(),
                "line_items": [item.to_dict() for item in processed_invoice.line_items]
            },
            ner_text=f"Invoice from {processed_invoice.vendor_info.vendor_name} for ${processed_invoice.invoice_header.total_amount}",
            event_timestamp=datetime.now().isoformat(),
            chromadb_ids=[],
            event_type="invoice_processing",
            created_by="invoice_analysis_system",
            document=document
        )
        
        # Add to analytics dataset
        self.analytics_builder.add_invoices([processed_invoice])
        
        return processed_invoice, document_insight
    
    def generate_analytics_models(self) -> Dict[str, Any]:
        """Generate all analytics models for flux analysis and PO predictions"""
        
        vendor_metrics = self.analytics_builder.build_vendor_performance_metrics()
        category_analysis = self.analytics_builder.build_category_spend_analysis()
        po_features = self.analytics_builder.build_po_prediction_features()
        
        return {
            "vendor_performance_metrics": [asdict(metric) for metric in vendor_metrics],
            "category_spend_analysis": [asdict(analysis) for analysis in category_analysis],
            "po_prediction_features": asdict(po_features),
            "summary_statistics": {
                "total_invoices_processed": len(self.analytics_builder.processed_invoices),
                "unique_vendors": len(set(inv.vendor_info.vendor_id for inv in self.analytics_builder.processed_invoices)),
                "total_spend": float(sum(inv.invoice_header.total_amount for inv in self.analytics_builder.processed_invoices)),
                "average_invoice_amount": float(sum(inv.invoice_header.total_amount for inv in self.analytics_builder.processed_invoices) / 
                                              len(self.analytics_builder.processed_invoices)) if self.analytics_builder.processed_invoices else 0
            }
        }


if __name__ == "__main__":
    # Example usage
    
    # Sample invoice content
    sample_invoice_content = """
    INVOICE
    
    ABC Software Solutions
    123 Tech Street
    San Francisco, CA 94105
    Tax ID: 12-3456789
    
    Invoice #: INV-2024-001234
    Date: March 15, 2024
    Due Date: April 14, 2024
    Payment Terms: Net 30
    PO #: PO-2024-5678
    
    Bill To:
    XYZ Corporation
    456 Business Ave
    Los Angeles, CA 90210
    
    Description                    Qty    Unit Price    Total
    Software License Renewal        12      $250.00    $3,000.00
    Support Services                 1      $500.00      $500.00
    Training Sessions                4      $200.00      $800.00
    
    Subtotal:                                          $4,300.00
    Tax (8.25%):                                         $354.75
    Total:                                             $4,654.75
    """
    
    # Create document
    document = Document(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        version=1,
        content=sample_invoice_content,
        json_metadata={"document_type": "invoice"},
        source_type="upload",
        document_type="invoice",
        created_at=datetime.now()
    )
    
    # Initialize service
    service = InvoiceAnalysisService()
    
    # Process invoice
    processed_invoice, document_insight = service.process_invoice_document(document)
    
    print(f"Processed Invoice ID: {processed_invoice.invoice_id}")
    print(f"Vendor: {processed_invoice.vendor_info.vendor_name}")
    print(f"Total Amount: ${processed_invoice.invoice_header.total_amount}")
    print(f"Line Items: {len(processed_invoice.line_items)}")
    print(f"Extraction Confidence: {processed_invoice.extraction_confidence:.2f}")
    
    # Add more sample invoices for analytics (in real scenario)
    # service.analytics_builder.add_invoices([more_processed_invoices])
    
    # Generate analytics models
    analytics_models = service.generate_analytics_models()
    
    print(f"\nAnalytics Models Generated:")
    print(f"Vendor Metrics: {len(analytics_models['vendor_performance_metrics'])} vendors")
    print(f"Category Analysis: {len(analytics_models['category_spend_analysis'])} categories")
    print(f"Total Spend: ${analytics_models['summary_statistics']['total_spend']:,.2f}")
    
    # Show sample vendor performance metrics
    if analytics_models['vendor_performance_metrics']:
        vendor_metric = analytics_models['vendor_performance_metrics'][0]
        print(f"\nSample Vendor Analysis:")
        print(f"Vendor: {vendor_metric['vendor_name']}")
        print(f"Total Spend: ${vendor_metric['total_spend']}")
        print(f"Spending Trend: {vendor_metric['spending_trend']}")
        print(f"Risk Score: {vendor_metric['risk_score']:.2f}")