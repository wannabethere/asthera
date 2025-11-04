"""
Conversational Insights Agent
Enables natural language queries and insights generation for dashboards
"""

from typing import List, Dict, Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from datetime import datetime


class Insight(BaseModel):
    """Structured insight from data analysis"""
    insight_type: str  # anomaly, trend, correlation, recommendation
    severity: str  # high, medium, low
    title: str
    description: str
    data_points: List[Dict] = []
    actionable_items: List[str] = []
    confidence: float = 0.0


class ConversationalQuery(BaseModel):
    """Parsed user question"""
    intent: str  # question, comparison, trend, anomaly, drill_down
    entities: List[str]
    time_range: Optional[str] = None
    metrics: List[str] = []
    dimensions: List[str] = []
    filters: Dict[str, str] = {}


class ConversationalInsightsAgent:
    """Agent for conversational dashboard interactions and insights"""
    
    def __init__(self, llm: ChatAnthropic = None):
        self.llm = llm or ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            temperature=0.3
        )
        self.context = {}  # Conversation context
    
    def generate_insights(
        self,
        dashboard_data: Dict,
        components: List[Dict]
    ) -> List[Insight]:
        """
        Generate proactive insights from dashboard data
        
        Args:
            dashboard_data: Full dashboard data structure
            components: List of dashboard components with data
            
        Returns:
            List of insights
        """
        insights = []
        
        # Analyze each component
        for component in components:
            # Detect anomalies
            anomalies = self._detect_anomalies(component)
            insights.extend(anomalies)
            
            # Identify trends
            trends = self._identify_trends(component)
            insights.extend(trends)
            
            # Find correlations
            correlations = self._find_correlations(component, components)
            insights.extend(correlations)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(component)
            insights.extend(recommendations)
        
        # Rank insights by importance
        insights = self._rank_insights(insights)
        
        return insights
    
    def answer_question(
        self,
        question: str,
        dashboard_data: Dict,
        context: Dict = None
    ) -> Dict:
        """
        Answer natural language question about dashboard
        
        Args:
            question: User's natural language question
            dashboard_data: Dashboard data and metadata
            context: Previous conversation context
            
        Returns:
            Answer with data and visualizations
        """
        # Update context
        if context:
            self.context.update(context)
        
        # Parse question
        parsed_query = self._parse_question(question)
        
        # Find relevant data
        relevant_data = self._find_relevant_data(parsed_query, dashboard_data)
        
        # Generate answer
        answer = self._generate_answer(
            question,
            parsed_query,
            relevant_data,
            dashboard_data
        )
        
        # Store in context for follow-ups
        self.context["last_question"] = question
        self.context["last_answer"] = answer
        
        return answer
    
    def _detect_anomalies(self, component: Dict) -> List[Insight]:
        """Detect anomalies in component data"""
        insights = []
        
        sample_data = component.get("sample_data", {}).get("data", [])
        if not sample_data:
            return insights
        
        # Use LLM to analyze data for anomalies
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a data analyst expert at detecting anomalies.
            
            Analyze the data and identify:
            1. Outliers (values far from the norm)
            2. Unexpected patterns
            3. Missing data issues
            4. Data quality problems
            
            Return insights as JSON array with:
            - insight_type: "anomaly"
            - severity: "high", "medium", or "low"
            - title: Brief title
            - description: Detailed explanation
            - confidence: 0.0 to 1.0
            """),
            ("user", """Question: {question}
            
            Data: {data}
            
            Detect anomalies:""")
        ])
        
        response = self.llm.invoke(
            prompt.format_messages(
                question=component.get("question", ""),
                data=str(sample_data[:10])  # Limit for token efficiency
            )
        )
        
        # Parse response
        anomalies = self._parse_insights_response(response.content, "anomaly")
        insights.extend(anomalies)
        
        return insights
    
    def _identify_trends(self, component: Dict) -> List[Insight]:
        """Identify trends in time-series data"""
        insights = []
        
        sample_data = component.get("sample_data", {}).get("data", [])
        if not sample_data or len(sample_data) < 3:
            return insights
        
        # Check if data has time dimension
        has_time = any(
            k for k in sample_data[0].keys()
            if any(t in k.lower() for t in ["date", "time", "month", "year"])
        )
        
        if not has_time:
            return insights
        
        # Use LLM to identify trends
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a data analyst expert at identifying trends.
            
            Analyze the time-series data and identify:
            1. Upward or downward trends
            2. Seasonality patterns
            3. Growth rates
            4. Acceleration/deceleration
            
            Return insights as JSON.
            """),
            ("user", """Data: {data}
            
            Identify trends:""")
        ])
        
        response = self.llm.invoke(
            prompt.format_messages(data=str(sample_data))
        )
        
        trends = self._parse_insights_response(response.content, "trend")
        insights.extend(trends)
        
        return insights
    
    def _find_correlations(
        self,
        component: Dict,
        all_components: List[Dict]
    ) -> List[Insight]:
        """Find correlations between metrics"""
        insights = []
        
        # Use LLM to find potential correlations
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Analyze relationships between different metrics.
            
            Look for:
            1. Strong positive/negative correlations
            2. Causal relationships
            3. Leading indicators
            
            Return insights as JSON.
            """),
            ("user", """Current metric: {current}
            
            Other metrics: {others}
            
            Find correlations:""")
        ])
        
        response = self.llm.invoke(
            prompt.format_messages(
                current=component.get("question", ""),
                others=str([c.get("question") for c in all_components[:3]])
            )
        )
        
        correlations = self._parse_insights_response(response.content, "correlation")
        insights.extend(correlations)
        
        return insights
    
    def _generate_recommendations(self, component: Dict) -> List[Insight]:
        """Generate actionable recommendations"""
        insights = []
        
        # Use LLM to generate recommendations
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a business consultant generating actionable recommendations.
            
            Based on the data and insights:
            1. Suggest specific actions
            2. Prioritize by impact
            3. Provide implementation steps
            
            Return as JSON.
            """),
            ("user", """Question: {question}
            
            Data: {data}
            
            Executive Summary: {summary}
            
            Generate recommendations:""")
        ])
        
        response = self.llm.invoke(
            prompt.format_messages(
                question=component.get("question", ""),
                data=str(component.get("sample_data", {}).get("data", [])[:5]),
                summary=component.get("executive_summary", "")[:500]
            )
        )
        
        recommendations = self._parse_insights_response(
            response.content,
            "recommendation"
        )
        insights.extend(recommendations)
        
        return insights
    
    def _parse_question(self, question: str) -> ConversationalQuery:
        """Parse natural language question into structured query"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at parsing natural language queries about data.
            
            Parse the question and extract:
            - intent: question, comparison, trend, anomaly, drill_down
            - entities: Named entities (products, people, departments, etc.)
            - time_range: Any time reference (yesterday, last month, Q1, etc.)
            - metrics: Measures being asked about (revenue, count, rate, etc.)
            - dimensions: Grouping dimensions (by department, by region, etc.)
            - filters: Any filtering conditions
            
            Return as JSON with these exact keys.
            """),
            ("user", """Question: {question}
            
            Parse into structured query:""")
        ])
        
        response = self.llm.invoke(
            prompt.format_messages(question=question)
        )
        
        # Parse JSON response
        parser = JsonOutputParser(pydantic_object=ConversationalQuery)
        try:
            parsed = parser.parse(response.content)
            return ConversationalQuery(**parsed)
        except:
            # Fallback
            return ConversationalQuery(
                intent="question",
                entities=[],
                metrics=[],
                dimensions=[]
            )
    
    def _find_relevant_data(
        self,
        parsed_query: ConversationalQuery,
        dashboard_data: Dict
    ) -> List[Dict]:
        """Find relevant components and data for query"""
        
        relevant = []
        components = dashboard_data.get("content", {}).get("components", [])
        
        for component in components:
            # Check if component matches query
            question = component.get("question", "").lower()
            
            # Match by entities
            entity_match = any(
                entity.lower() in question
                for entity in parsed_query.entities
            )
            
            # Match by metrics
            metric_match = any(
                metric.lower() in question
                for metric in parsed_query.metrics
            )
            
            if entity_match or metric_match:
                relevant.append(component)
        
        return relevant
    
    def _generate_answer(
        self,
        question: str,
        parsed_query: ConversationalQuery,
        relevant_data: List[Dict],
        dashboard_data: Dict
    ) -> Dict:
        """Generate natural language answer"""
        
        if not relevant_data:
            return {
                "answer": "I couldn't find relevant data to answer that question. Could you rephrase or ask about a different metric?",
                "confidence": 0.0,
                "data": []
            }
        
        # Build context from relevant components
        context_parts = []
        for component in relevant_data:
            context_parts.append(f"""
            Question: {component.get('question')}
            Data: {component.get('sample_data', {}).get('data', [])[:5]}
            Summary: {component.get('executive_summary', '')[:300]}
            """)
        
        context = "\n\n".join(context_parts)
        
        # Generate answer using LLM
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful data analyst assistant.
            
            Answer questions about dashboard data:
            - Be concise and direct
            - Use specific numbers and data points
            - Provide context when helpful
            - Suggest follow-up questions
            - If uncertain, say so
            
            Format:
            1. Direct answer to the question
            2. Supporting data points
            3. Additional context if relevant
            4. Suggested follow-up questions
            """),
            ("user", """User Question: {question}
            
            Parsed Intent: {intent}
            
            Relevant Data:
            {context}
            
            Provide a clear, data-driven answer:""")
        ])
        
        response = self.llm.invoke(
            prompt.format_messages(
                question=question,
                intent=parsed_query.intent,
                context=context
            )
        )
        
        return {
            "answer": response.content,
            "confidence": 0.85,  # Would calculate based on data match
            "data": [c.get("sample_data") for c in relevant_data],
            "sources": [c.get("id") for c in relevant_data],
            "follow_up_questions": self._generate_follow_ups(
                question,
                relevant_data
            )
        }
    
    def _generate_follow_ups(
        self,
        question: str,
        relevant_data: List[Dict]
    ) -> List[str]:
        """Generate suggested follow-up questions"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Generate 3 relevant follow-up questions that would provide deeper insights.
            
            Make them:
            - Specific and actionable
            - Build on the current question
            - Explore different angles
            
            Return as JSON array of strings.
            """),
            ("user", """Original Question: {question}
            
            Available Data Topics: {topics}
            
            Generate follow-up questions:""")
        ])
        
        topics = [c.get("question") for c in relevant_data]
        
        response = self.llm.invoke(
            prompt.format_messages(
                question=question,
                topics=str(topics)
            )
        )
        
        # Parse response
        try:
            import json
            follow_ups = json.loads(response.content)
            if isinstance(follow_ups, list):
                return follow_ups[:3]
        except:
            pass
        
        return [
            "Can you show me the trend over time?",
            "How does this compare to last year?",
            "What are the top contributors?"
        ]
    
    def _parse_insights_response(
        self,
        response: str,
        insight_type: str
    ) -> List[Insight]:
        """Parse LLM response into Insight objects"""
        insights = []
        
        try:
            import json
            # Try to parse as JSON
            data = json.loads(response)
            
            if isinstance(data, list):
                for item in data:
                    insights.append(Insight(
                        insight_type=insight_type,
                        severity=item.get("severity", "medium"),
                        title=item.get("title", ""),
                        description=item.get("description", ""),
                        confidence=item.get("confidence", 0.7)
                    ))
            elif isinstance(data, dict):
                insights.append(Insight(
                    insight_type=insight_type,
                    severity=data.get("severity", "medium"),
                    title=data.get("title", ""),
                    description=data.get("description", ""),
                    confidence=data.get("confidence", 0.7)
                ))
        except:
            # Fallback: parse as text
            if "high" in response.lower() or "critical" in response.lower():
                severity = "high"
            elif "low" in response.lower():
                severity = "low"
            else:
                severity = "medium"
            
            insights.append(Insight(
                insight_type=insight_type,
                severity=severity,
                title=f"{insight_type.title()} Detected",
                description=response[:500],
                confidence=0.6
            ))
        
        return insights
    
    def _rank_insights(self, insights: List[Insight]) -> List[Insight]:
        """Rank insights by importance"""
        
        severity_weight = {"high": 3, "medium": 2, "low": 1}
        
        def insight_score(insight: Insight) -> float:
            return (
                severity_weight.get(insight.severity, 1) * 10 +
                insight.confidence * 5
            )
        
        return sorted(insights, key=insight_score, reverse=True)
    
    def create_alert_rules(
        self,
        component: Dict,
        threshold_type: str = "anomaly"
    ) -> Dict:
        """Create alert rules for dashboard component"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Create alert rules for monitoring this metric.
            
            Define:
            1. Threshold conditions
            2. Notification triggers
            3. Escalation rules
            
            Return as JSON.
            """),
            ("user", """Metric: {question}
            
            Data: {data}
            
            Create alert rules:""")
        ])
        
        response = self.llm.invoke(
            prompt.format_messages(
                question=component.get("question", ""),
                data=str(component.get("sample_data", {}))
            )
        )
        
        return {
            "component_id": component.get("id"),
            "alert_rules": response.content,
            "created_at": datetime.now().isoformat()
        }


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Sample dashboard data
    dashboard_data = {
        "dashboard_id": "test-123",
        "content": {
            "components": [
                {
                    "id": "comp-1",
                    "question": "What is the training drop-off rate?",
                    "sample_data": {
                        "data": [
                            {"training": "Code of Conduct", "drop_off_rate": 100.0},
                            {"training": "Communication", "drop_off_rate": 100.0}
                        ]
                    },
                    "executive_summary": "High drop-off rates of 100% across all training programs..."
                }
            ]
        }
    }
    
    agent = ConversationalInsightsAgent()
    
    # Generate insights
    print("Generating Insights...\n")
    insights = agent.generate_insights(
        dashboard_data,
        dashboard_data["content"]["components"]
    )
    
    print(f"Generated {len(insights)} insights:\n")
    for insight in insights[:3]:
        print(f"• [{insight.severity.upper()}] {insight.title}")
        print(f"  {insight.description[:200]}...")
        print()
    
    # Answer questions
    questions = [
        "What is the current drop-off rate?",
        "Why is the drop-off rate so high?",
        "Which training needs the most attention?"
    ]
    
    print("\nAnswering Questions:\n")
    for q in questions:
        print(f"Q: {q}")
        answer = agent.answer_question(q, dashboard_data)
        print(f"A: {answer['answer'][:300]}...")
        print()
