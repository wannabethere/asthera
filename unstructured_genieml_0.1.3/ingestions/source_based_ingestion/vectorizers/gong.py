"""
Gong vectorizer implementation.

This module provides the vectorizer for Gong call data.
"""
import json
import asyncio
import logging
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

import openai
from pydantic import BaseModel, Field

from .base import IVectorizer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenAI pricing (as of 2024) - prices per 1K tokens
OPENAI_PRICING = {
    "gpt-4o": {
        "input": 0.005,    # $0.005 per 1K input tokens
        "output": 0.015    # $0.015 per 1K output tokens
    }
}

def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate the cost of an LLM call in USD."""
    if model not in OPENAI_PRICING:
        logger.warning(f"Unknown model {model}, using gpt-4o pricing")
        model = "gpt-4o"
    
    pricing = OPENAI_PRICING[model]
    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    return input_cost + output_cost

# Define structured schema for insights
class SalesInsights(BaseModel):
    pain_points: List[str] = Field(default_factory=list, description="Customer pain points and challenges mentioned")
    product_features: List[str] = Field(default_factory=list, description="Product capabilities, functionalities, or technical characteristics discussed")
    objections: List[str] = Field(default_factory=list, description="Customer objections or concerns raised")
    action_items: List[str] = Field(default_factory=list, description="Next steps, demos, POCs, follow-up activities, or to-do items")
    competitors: List[str] = Field(default_factory=list, description="Competitors or alternative solutions mentioned")
    decision_criteria: List[str] = Field(default_factory=list, description="Factors influencing the buying decision")
    use_cases: List[str] = Field(default_factory=list, description="Specific use cases or applications mentioned")
    deal_stage: List[str] = Field(default_factory=list, description="Stage of the deal (prospecting, qualification, demo, proposal, negotiation, closing)")
    buyer_roles: List[str] = Field(default_factory=list, description="Roles represented in the call (decision maker, influencer, end user, etc.)")

class StrategicAnalysis(BaseModel):
    key_themes: List[str] = Field(default_factory=list, description="Most significant themes discussed during the call")
    engagement_level: List[str] = Field(default_factory=list, description="Assessment of customer engagement and interest level")
    next_steps: List[str] = Field(default_factory=list, description="Clear action items and follow-up required")
    risks_opportunities: List[str] = Field(default_factory=list, description="Potential risks to deal progression and opportunities to advance")

class SummaryInsights(BaseModel):
    key_takeaways: List[str] = Field(default_factory=list, description="Key takeaways from the call")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for follow-up")

class CallInsightsSchema(BaseModel):
    sales_insights: SalesInsights = Field(..., description="Detailed sales insights extracted from the call")
    strategic_analysis: StrategicAnalysis = Field(..., description="Strategic analysis of the call")
    summary_insights: SummaryInsights = Field(..., description="Summary insights from the call")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sales_insights": {
                        "pain_points": ["Data Integration Challenges: Customer is facing difficulties in marrying internal and external data sources"],
                        "product_features": ["Natural Language Search: Platform offers a search interface that allows users to ask questions in natural language"],
                        "objections": ["Data Quality Concerns: Customer raised concerns about data quality and integration"],
                        "action_items": ["Formal Review Process: Customer to review use cases with the Executive team"],
                        "competitors": ["No specific competitors were mentioned"],
                        "decision_criteria": ["Integration Capabilities: Ability to integrate with existing systems"],
                        "use_cases": ["Predictive Analytics: Interest in using predictive analytics to uncover hidden opportunities"],
                        "deal_stage": ["Demo Stage: The call was primarily a demo and discussion of capabilities"],
                        "buyer_roles": ["Decision Maker: John Smith, Business Intelligence Manager"]
                    },
                    "strategic_analysis": {
                        "key_themes": ["Digital Transformation: Focus on digital transformation to leverage AI"],
                        "engagement_level": ["High Engagement: The customer showed significant interest in the capabilities"],
                        "next_steps": ["Formal Review and Feedback: Customer to conduct a formal review"],
                        "risks_opportunities": ["Risk: Concerns about data quality could delay decision-making"]
                    },
                    "summary_insights": {
                        "key_takeaways": ["Customer is actively seeking solutions to integrate and analyze data more effectively"],
                        "recommendations": ["Address Data Quality Concerns: Provide detailed information on handling data quality issues"]
                    }
                }
            ]
        }
    }

class EntityExtractionSchema(BaseModel):
    entities: List[str] = Field(..., description="Named entities from the call (people, organizations, products, technologies)")
    keywords: List[str] = Field(..., description="Significant keywords representing core themes and concepts")
    topics: List[str] = Field(..., description="Main discussion topics from the call")
    categories: List[str] = Field(..., description="Business categories for classifying the call")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "entities": ["John Smith", "Acme Corp", "TelliusAI", "SAP HANA", "Eric Johnson"],
                    "keywords": ["integration", "predictive analytics", "data quality", "visualization", "AI"],
                    "topics": ["Data Integration", "Predictive Analytics", "Digital Transformation"],
                    "categories": ["Sales Demo", "Technical Discussion", "Discovery Phase"]
                }
            ]
        }
    }

class GongVectorizer(IVectorizer):
    """Vectorizer for Gong call data."""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize the Gong vectorizer.
        
        Args:
            openai_api_key: Optional OpenAI API key for insights generation
        """
        self.openai_api_key = openai_api_key
        self.debug_mode = False
    
    def vectorize(self, documents: List[Any]) -> List[Any]:
        """
        Convert Gong call documents into vector chunks.
        
        Args:
            documents: List of Gong call documents to vectorize
            
        Returns:
            List of vector chunks and insights
        """
        # Check if debug mode is enabled in any of the documents' metadata
        self.debug_mode = False
        for doc in documents:
            metadata = doc.get("metadata", {})
            if metadata.get("debug", False):
                self.debug_mode = True
                break
        
        logger.info(f"Starting vectorization for {len(documents)} documents")
        if self.debug_mode:
            logger.debug(f"Vectorizer has OpenAI API key: {bool(self.openai_api_key)}")
        
        calls = []
        insights = []
        
        # Process each call from the documents
        for doc in documents:
            call_id = doc.get("call_id") or doc.get("document_id")
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            
            # Extract metadata fields
            title = metadata.get("title", "")
            url = metadata.get("url", "")
            date = metadata.get("date", "")
            date_timestamp = metadata.get("date_timestamp", 0)
            
            if self.debug_mode:
                logger.debug(f"Vectorizing call {call_id}: {title}")
            
            # Create a simplified call data structure for the unstructured_calls output
            call_data = {
                "id": call_id,
                "url": url,
                "title": title,
                "date": date,
                "date_timestamp": date_timestamp,
                "content": content
            }
            
            # Add to calls list
            calls.append(call_data)
            
            if self.debug_mode:
                logger.debug(f"Created call chunk for {call_id}")
                logger.debug(f"GONG VECTORIZER CALL OUTPUT: {json.dumps(call_data, indent=2, default=str)}")
            
            # Generate insights - always enabled by default
            if self.openai_api_key:
                try:
                    # Run the async function in a synchronous context
                    loop = asyncio.get_event_loop()
                    structured_insights, formatted_content, usage_stats = loop.run_until_complete(
                        self.generate_call_insights(call_data)
                    )
                    
                    # Extract entities and keywords using LLM
                    extracted_nlp, nlp_usage_stats = loop.run_until_complete(
                        self.extract_entities_keywords_llm(formatted_content, title)
                    )
                    
                    # Update usage stats to include entity extraction costs
                    usage_stats["input_tokens"] += nlp_usage_stats["input_tokens"]
                    usage_stats["output_tokens"] += nlp_usage_stats["output_tokens"]
                    usage_stats["cost_usd"] += nlp_usage_stats["cost_usd"]
                    
                    # Flatten the structured insights for easier access
                    flattened_insights = {}
                    
                    # Add sales insights
                    if "sales_insights" in structured_insights:
                        for key, value in structured_insights["sales_insights"].items():
                            flattened_insights[key] = value
                    
                    # Add strategic analysis
                    if "strategic_analysis" in structured_insights:
                        for key, value in structured_insights["strategic_analysis"].items():
                            flattened_insights[key] = value
                    
                    # Add summary insights
                    if "summary_insights" in structured_insights:
                        for key, value in structured_insights["summary_insights"].items():
                            flattened_insights[key] = value
                    
                    # Create the insight object
                    insight = {
                        "id": call_id,
                        "call_id": call_id,
                        "url": url,
                        "title": title,
                        "date": date,
                        "date_timestamp": date_timestamp,
                        "content": formatted_content,  # Human-readable markdown
                        "insights": flattened_insights,  # Structured data
                        "entities": extracted_nlp["entities"],
                        "keywords": extracted_nlp["keywords"],
                        "topics": extracted_nlp["topics"],
                        "categories": extracted_nlp["categories"],
                        "usage_stats": usage_stats
                    }
                    
                    insights.append(insight)
                    logger.info(f"Generated insights for call {call_id}: {title}")
                    
                    if self.debug_mode:
                        logger.debug(f"Generated insights for call {call_id}")
                        logger.debug(f"GONG VECTORIZER INSIGHT OUTPUT: {json.dumps(insight, indent=2, default=str)}")
                        logger.debug(f"Usage stats: {json.dumps(usage_stats, indent=2)}")
                        
                except Exception as e:
                    logger.error(f"Error generating insights for call {call_id}: {e}")
                    if self.debug_mode:
                        logger.exception(f"Detailed error when generating insights for call {call_id}")
            else:
                logger.warning(f"OpenAI API key not provided - insights generation skipped for call {call_id}")
        
        # Return both calls and insights as a list to match the expected return type
        result = []
        result.extend(calls)
        result.extend(insights)
        
        logger.info(f"Vectorization completed. Generated {len(calls)} call chunks and {len(insights)} insights.")
        return result
    
    async def generate_call_insights(self, call_data: Dict[str, Any]) -> Tuple[Dict[str, Any], str, Dict[str, Any]]:
        """
        Generate comprehensive insights from Gong call data using GPT-4o with structured output.
        
        Args:
            call_data: Dictionary containing the call data
            
        Returns:
            Tuple of (structured insights dict, formatted markdown content, usage statistics)
        """
        # Configure the client
        client = openai.OpenAI(api_key=self.openai_api_key)
        
        model = "gpt-4o"
        usage_stats = {
            "model": model,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0
        }
        
        # Extract key information from call data
        title = call_data.get("title", "")
        content = call_data.get("content", "")
        
        # Combine all content for analysis
        combined_content = f"""
    CALL TITLE: {title}

    CALL CONTENT:
    {content}
    """
        
        # Create the schema definition for function calling
        schema_definition = CallInsightsSchema.model_json_schema()
        
        prompt = f"""
        As a senior sales analyst, analyze this Gong call transcript data and extract comprehensive sales insights.
        
        CALL DETAILS:
        Title: {title}
        
        CALL CONTENT:
        {combined_content}
        
        Analyze this call data and extract insights according to the provided schema. Be specific and data-driven where possible.
        Focus on actionable insights that can help improve future sales processes and outcomes.
        
        IMPORTANT: Extract complete phrases and sentences, not individual words. Provide concrete, specific insights based on the actual content provided.
        If there is no relevant information for a particular field, provide an empty list.
        """
        
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert sales analyst specializing in analyzing sales call transcripts. Provide comprehensive, actionable insights based on the call data provided."},
                    {"role": "user", "content": prompt}
                ],
                tools=[{
                    "type": "function",
                    "function": {
                        "name": "extract_call_insights",
                        "description": "Extract structured insights from sales call transcript",
                        "parameters": schema_definition
                    }
                }],
                tool_choice={"type": "function", "function": {"name": "extract_call_insights"}},
                temperature=0.0
            )
            
            # Extract usage information
            if response and response.usage:
                usage_stats["input_tokens"] = response.usage.prompt_tokens
                usage_stats["output_tokens"] = response.usage.completion_tokens
                usage_stats["cost_usd"] = calculate_cost(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    model
                )
            
            # Extract the structured insights
            if (response and response.choices and len(response.choices) > 0 and 
                response.choices[0].message and response.choices[0].message.tool_calls):
                
                tool_call = response.choices[0].message.tool_calls[0]
                if tool_call.function.name == "extract_call_insights":
                    try:
                        structured_insights = json.loads(tool_call.function.arguments)
                        
                        # Format the structured insights into a human-readable report
                        formatted_content = self.format_insights_to_markdown(structured_insights)
                        
                        # Return both the structured insights and usage stats
                        return structured_insights, formatted_content, usage_stats
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing JSON from LLM response: {e}")
            
            logger.error("Received empty or invalid response from LLM")
            return {}, "## Failed to analyze call\n\nPlease review the call data manually.", usage_stats
        
        except Exception as e:
            logger.error(f"Error analyzing call with LLM: {e}")
        
        # Return empty insights and a basic fallback summary if LLM fails
        return {}, "## Failed to analyze call\n\nPlease review the call data manually.", usage_stats
    
    def format_insights_to_markdown(self, insights: Dict[str, Any]) -> str:
        """Convert structured insights into a formatted markdown report."""
        md_content = "# Comprehensive Sales Call Analysis Report\n\n"
        
        # 1. Sales Insights
        md_content += "## 1. SALES INSIGHTS EXTRACTION\n\n"
        
        sales_insights = insights.get("sales_insights", {})
        if sales_insights.get("pain_points"):
            md_content += "### Customer Pain Points\n"
            for item in sales_insights["pain_points"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        if sales_insights.get("product_features"):
            md_content += "### Product Features\n"
            for item in sales_insights["product_features"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        if sales_insights.get("objections"):
            md_content += "### Objections\n"
            for item in sales_insights["objections"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        if sales_insights.get("action_items"):
            md_content += "### Action Items\n"
            for item in sales_insights["action_items"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        if sales_insights.get("competitors"):
            md_content += "### Competitors\n"
            for item in sales_insights["competitors"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        if sales_insights.get("decision_criteria"):
            md_content += "### Decision Criteria\n"
            for item in sales_insights["decision_criteria"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        if sales_insights.get("use_cases"):
            md_content += "### Use Cases\n"
            for item in sales_insights["use_cases"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        if sales_insights.get("deal_stage"):
            md_content += "### Deal Stage\n"
            for item in sales_insights["deal_stage"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        if sales_insights.get("buyer_roles"):
            md_content += "### Buyer Roles\n"
            for item in sales_insights["buyer_roles"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        # 2. Strategic Analysis
        md_content += "## 2. STRATEGIC ANALYSIS\n\n"
        
        strategic = insights.get("strategic_analysis", {})
        if strategic.get("key_themes"):
            md_content += "### Key Themes\n"
            for item in strategic["key_themes"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        if strategic.get("engagement_level"):
            md_content += "### Engagement Level\n"
            for item in strategic["engagement_level"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        if strategic.get("next_steps"):
            md_content += "### Next Steps\n"
            for item in strategic["next_steps"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        if strategic.get("risks_opportunities"):
            md_content += "### Risks & Opportunities\n"
            for item in strategic["risks_opportunities"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        # 3. Summary Insights
        md_content += "## 3. SUMMARY INSIGHTS\n\n"
        
        summary = insights.get("summary_insights", {})
        if summary.get("key_takeaways"):
            md_content += "### Key Takeaways\n"
            for item in summary["key_takeaways"]:
                md_content += f"- {item}\n"
            md_content += "\n"
        
        if summary.get("recommendations"):
            md_content += "### Recommendations for Follow-Up\n"
            for item in summary["recommendations"]:
                md_content += f"- **{item}**\n"
            md_content += "\n"
        
        return md_content.strip()
    
    async def extract_entities_keywords_llm(self, content: str, title: str) -> Tuple[Dict[str, List[str]], Dict[str, Any]]:
        """
        Extract entities, keywords, topics, and categories using LLM.
        
        Args:
            content: The content to extract from
            title: The title of the call
            
        Returns:
            Tuple of (extracted data dict, usage statistics)
        """
        client = openai.OpenAI(api_key=self.openai_api_key)
        
        model = "gpt-4o"
        usage_stats = {
            "model": model,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0
        }
        
        # Create the schema definition for function calling
        schema_definition = EntityExtractionSchema.model_json_schema()
        
        # Prepare the combined content
        combined_content = f"""
    CALL TITLE: {title}

    CALL CONTENT:
    {content}
    """
        
        prompt = """
    You are an expert NLP analyst specializing in information extraction from sales call transcripts.
    Extract structured information from the following sales call data.

    CALL CONTENT: {content}

    Please extract the following elements directly from this call data:

    1. ENTITIES:
       - Extract all named entities including:
         - People (both internal and external participants)
         - Organizations (customer company, vendor company, competitors)
         - Products (both mentioned products and competitor products)
         - Technical terms and technologies discussed
       - Include the full entity name with proper capitalization
       - Do not include general nouns or concepts

    2. KEYWORDS:
       - Extract 15-20 significant keywords that represent the core themes and concepts
       - Focus on terms that appear frequently or have high relevance to the sales context
       - Prioritize terms related to pain points, requirements, and decision criteria
       - Exclude common stopwords and general terms
       - Return only single words or compound terms (2-3 words maximum)

    3. TOPICS:
       - Identify 5-10 main discussion topics from the call
       - These should represent the key conversation areas and business concerns
       - Examples: "Data Integration", "Predictive Analytics", "User Experience"
       - Each topic should be 1-3 words

    4. CATEGORIES:
       - Classify the call into 3-5 business categories
       - Examples: "Sales Demo", "Technical Discussion", "Needs Assessment", "Solution Presentation"
       - Include the apparent deal stage (e.g., "Discovery", "Demo", "Negotiation")
       - Categories should help with organizing and filtering calls in a database
    """
        
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert NLP analyst specializing in information extraction from sales call transcripts."},
                    {"role": "user", "content": prompt.format(content=combined_content)}
                ],
                tools=[{
                    "type": "function",
                    "function": {
                        "name": "extract_call_entities",
                        "description": "Extract entities, keywords, topics, and categories from sales call transcript",
                        "parameters": schema_definition
                    }
                }],
                tool_choice={"type": "function", "function": {"name": "extract_call_entities"}},
                temperature=0.0
            )
            
            # Extract usage information
            if response and response.usage:
                usage_stats["input_tokens"] = response.usage.prompt_tokens
                usage_stats["output_tokens"] = response.usage.completion_tokens
                usage_stats["cost_usd"] = calculate_cost(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    model
                )
            
            # Extract the structured entities
            if (response and response.choices and len(response.choices) > 0 and 
                response.choices[0].message and response.choices[0].message.tool_calls):
                
                tool_call = response.choices[0].message.tool_calls[0]
                if tool_call.function.name == "extract_call_entities":
                    try:
                        extracted_data = json.loads(tool_call.function.arguments)
                        return extracted_data, usage_stats
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing JSON from LLM response: {e}")
            
            logger.error("Received empty or invalid response from entity extraction LLM")
            return {
                "entities": [],
                "keywords": [],
                "topics": [],
                "categories": []
            }, usage_stats
        
        except Exception as e:
            logger.error(f"Error extracting entities with LLM: {e}")
        
        # Return empty data if LLM fails
        return {
            "entities": [],
            "keywords": [],
            "topics": [],
            "categories": []
        }, usage_stats 