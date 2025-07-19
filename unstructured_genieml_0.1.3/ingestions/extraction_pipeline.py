"""
Document Feature Extraction Pipeline
Handles all document preprocessing, feature extraction, and chunking operations
"""

import re
import spacy
from typing import List, Dict, Any, Tuple, Optional, cast
from spacy.tokens import Doc, Token
from spacy.language import Language
from dataclasses import dataclass, asdict
from collections import Counter, defaultdict
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib

# Uncomment if you have spacy installed
nlp = spacy.load("en_core_web_sm")

@dataclass
class ExtractionResult:
    """Structured extraction result from documents"""
    entities: List[str]
    keywords: List[str]
    topics: List[str]
    categories: List[str]
    summary: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)

@dataclass
class ChunkResult:
    """Individual chunk with extracted features"""
    chunk_id: str
    text: str
    extraction: ExtractionResult
    parent_doc_id: str
    chunk_index: int
    start_position: int
    end_position: int
    overlap_info: Dict[str, Any]

class DocumentExtractor:
    """Main document extraction pipeline"""
    
    def __init__(self, use_advanced_nlp: bool = False):
        self.use_advanced_nlp = use_advanced_nlp
        self.nlp = None
        
        # Initialize NLP pipeline if advanced features are enabled
        if use_advanced_nlp:
            try:
                # self.nlp = spacy.load("en_core_web_sm")
                pass
            except OSError:
                print("SpaCy model not found. Using simple extraction methods.")
                self.use_advanced_nlp = False
        
        # Topic detection patterns - Sales-focused for Gong calls
        self.topic_patterns = {
            'customer_pain_point': [
                'problem', 'challenge', 'issue', 'pain point', 'struggle', 'difficulty',
                'frustration', 'bottleneck', 'inefficiency', 'manual process', 'time consuming',
                'error prone', 'lack of', 'missing', 'unable to', 'cant do', 'limitation'
            ],
            'product_feature': [
                'feature', 'functionality', 'capability', 'solution', 'platform',
                'integration', 'api', 'dashboard', 'reporting', 'analytics', 'automation',
                'workflow', 'interface', 'tool', 'module', 'component'
            ],
            'objection': [
                'price', 'cost', 'expensive', 'budget', 'competition', 'competitor',
                'timing', 'timeline', 'not ready', 'too early', 'concerns', 'worried',
                'risk', 'doubt', 'hesitant', 'alternative', 'comparison'
            ],
            'next_step': [
                'next step', 'follow up', 'schedule', 'meeting', 'demo', 'trial',
                'pilot', 'proposal', 'quote', 'contract', 'agreement', 'timeline',
                'action item', 'commitment', 'deliverable'
            ],
            'competitor': [
                'salesforce', 'hubspot', 'microsoft', 'oracle', 'sap', 'workday',
                'competitor', 'alternative', 'current solution', 'existing tool',
                'other vendor', 'comparison', 'versus', 'vs', 'competitive'
            ],
            'decision_criteria': [
                'requirement', 'criteria', 'need to see', 'must have', 'deal breaker',
                'evaluation', 'checklist', 'approve', 'decision maker', 'sign off',
                'budget approval', 'technical review', 'security review'
            ],
            'buyer_role': [
                'ceo', 'cto', 'cfo', 'vp', 'director', 'manager', 'analyst',
                'decision maker', 'influencer', 'end user', 'stakeholder',
                'procurement', 'it', 'finance', 'operations', 'marketing', 'sales'
            ],
            'deal_stage': [
                'interested', 'qualified', 'ready to move', 'close', 'purchase',
                'budget approved', 'timeline', 'urgency', 'priority', 'momentum',
                'commitment', 'verbal agreement', 'handshake', 'moving forward'
            ],
            'use_case': [
                'use case', 'scenario', 'workflow', 'process', 'goal', 'objective',
                'outcome', 'result', 'benefit', 'value', 'roi', 'efficiency',
                'automation', 'integration', 'reporting', 'analytics'
            ],
            # Keep some general business categories
            'technology': [
                'software', 'computer', 'algorithm', 'programming', 'data', 
                'api', 'database', 'machine learning', 'artificial intelligence',
                'cloud computing', 'blockchain', 'cybersecurity', 'mobile app'
            ],
            'business': [
                'revenue', 'profit', 'customer', 'market', 'sales', 'strategy',
                'company', 'investment', 'finance', 'marketing', 'product management'
            ]
        }
        
        # Common stop words for keyword extraction
        self.stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 
            'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 
            'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 
            'two', 'who', 'boy', 'did', 'she', 'use', 'way', 'men', 'too',
            'any', 'say', 'let', 'put', 'try', 'why', 'ask', 'run', 'own',
            'few', 'lot', 'big', 'end', 'far', 'off', 'got', 'yet', 'set',
            'with', 'this', 'that', 'from', 'they', 'know', 'want', 'been',
            'good', 'much', 'some', 'time', 'very', 'when', 'come', 'here',
            'just', 'like', 'long', 'make', 'many', 'over', 'such', 'take',
            'than', 'them', 'well', 'were', 'will', 'work', 'about', 'after',
            'first', 'would', 'there', 'think', 'where', 'being', 'every',
            'great', 'might', 'shall', 'still', 'those', 'under', 'while'
        }
    
    def extract_features(self, text: str, categories: List[str] = [], 
                        doc_metadata: Dict[str, Any] = {}) -> ExtractionResult:
        """
        Extract comprehensive features from text
        
        Args:
            text: Input text to analyze
            categories: Predefined categories for the document
            doc_metadata: Additional document metadata
            
        Returns:
            ExtractionResult with all extracted features
        """
        if self.use_advanced_nlp and self.nlp:
            return self._extract_features_advanced(text, categories, doc_metadata)
        else:
            return self._extract_features_simple(text, categories, doc_metadata)
    
    def _extract_features_advanced(self, text: str, categories: List[str] = [],
                                 doc_metadata: Dict[str, Any] = {}) -> ExtractionResult:
        """Advanced feature extraction using spaCy NLP pipeline"""
        if not self.nlp:
            return self._extract_features_simple(text, categories, doc_metadata)
        
        doc = cast(Doc, self.nlp(text))
        
        # Extract named entities with type checking
        entities: List[str] = []
        if doc.has_annotation("ENT"):
            entities = [ent.text.lower() for ent in doc.ents 
                       if ent.label_ in ['PERSON', 'ORG', 'GPE', 'PRODUCT', 'EVENT']]
        
        # Extract keywords using noun phrases and important words
        keywords: List[str] = []
        if doc.has_annotation("DEP"):
            for chunk in doc.noun_chunks:
                if len(chunk.text.split()) <= 3 and chunk.root.pos_ in ['NOUN', 'PROPN']:
                    keywords.append(chunk.text.lower())
        
        # Add important adjectives and verbs
        for token in doc:
            if (token.pos_ in ['ADJ', 'VERB'] and 
                len(token.text) > 3 and 
                token.text.lower() not in self.stop_words):
                keywords.append(token.text.lower())
        
        # Remove duplicates and get top keywords
        keyword_freq = Counter(keywords)
        top_keywords = [word for word, _ in keyword_freq.most_common(15)]
        
        # Extract topics
        topics = self._extract_topics(text)
        
        # Generate summary
        summary = self._generate_summary(text)
        
        # Extract metadata
        metadata = self._extract_metadata(text, doc_metadata)
        
        return ExtractionResult(
            entities=list(set(entities)),
            keywords=top_keywords,
            topics=topics,
            categories=categories or [],
            summary=summary,
            metadata=metadata
        )
    
    def _extract_features_simple(self, text: str, categories: List[str] = [],
                               doc_metadata: Dict[str, Any] = {}) -> ExtractionResult:
        """Simple feature extraction using regex and pattern matching"""
        
        # Extract entities using patterns
        entities = self._extract_entities_patterns(text)
        
        # Extract keywords using frequency analysis
        keywords = self._extract_keywords_frequency(text)
        
        # Extract topics using keyword matching
        topics = self._extract_topics(text)
        
        # Generate summary
        summary = self._generate_summary(text)
        
        # Extract metadata
        metadata = self._extract_metadata(text, doc_metadata)
        
        return ExtractionResult(
            entities=entities,
            keywords=keywords,
            topics=topics,
            categories=categories or [],
            summary=summary,
            metadata=metadata
        )
    
    def _extract_entities_patterns(self, text: str) -> List[str]:
        """Extract entities using regex patterns"""
        entities = []
        
        # Email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        entities.extend(re.findall(email_pattern, text))
        
        # Phone numbers
        phone_patterns = [
            r'\b\d{3}-\d{3}-\d{4}\b',
            r'\b\(\d{3}\)\s*\d{3}-\d{4}\b',
            r'\b\d{3}\.\d{3}\.\d{4}\b'
        ]
        for pattern in phone_patterns:
            entities.extend(re.findall(pattern, text))
        
        # URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`[\]]+[^\s<>"{}|\\^`[\].,;:!?]'
        entities.extend(re.findall(url_pattern, text))
        
        # Dates
        date_patterns = [
            r'\b\d{4}-\d{2}-\d{2}\b',
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',
            r'\b\d{1,2}-\d{1,2}-\d{4}\b'
        ]
        for pattern in date_patterns:
            entities.extend(re.findall(pattern, text))
        
        # Capitalized words (potential proper nouns)
        proper_nouns = re.findall(r'\b[A-Z][a-z]{2,}\b', text)
        # Filter out common words
        proper_nouns = [word for word in proper_nouns 
                       if word.lower() not in self.stop_words and len(word) > 2]
        entities.extend(proper_nouns[:10])  # Limit to top 10
        
        return list(set(entities))
    
    def _extract_keywords_frequency(self, text: str) -> List[str]:
        """Extract keywords using frequency analysis"""
        # Clean and tokenize text
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Remove stop words
        meaningful_words = [word for word in words 
                           if word not in self.stop_words and len(word) > 2]
        
        # Count frequencies
        word_freq = Counter(meaningful_words)
        
        # Get top keywords
        top_keywords = [word for word, _ in word_freq.most_common(12)]
        
        return top_keywords
    
    def _extract_topics(self, text: str) -> List[str]:
        """Extract topics using keyword matching"""
        text_lower = text.lower()
        detected_topics = []
        
        for topic, keywords in self.topic_patterns.items():
            # Count matches for each topic
            matches = sum(1 for keyword in keywords if keyword in text_lower)
            
            # If enough matches, consider it a relevant topic
            if matches >= 2:  # Threshold can be adjusted
                detected_topics.append(topic)
        
        return detected_topics
    
    def _generate_summary(self, text: str) -> str:
        """Generate meaningful insights summary from text"""
        if len(text.strip()) < 50:
            return text.strip()
        
        # Clean text and split into sentences
        clean_text = re.sub(r'\s+', ' ', text.strip())
        
        # Skip metadata-like content
        if clean_text.startswith(('Title:', 'Date:', 'Brief summary:')):
            return ""
        
        # Clean up formatting artifacts
        clean_text = re.sub(r'^[\s\-•]+', '', clean_text)  # Remove leading bullets/dashes
        clean_text = re.sub(r'\n[\s\-•]+', '\n', clean_text)  # Remove bullets in middle
        clean_text = re.sub(r'\s+', ' ', clean_text)  # Normalize whitespace
            
        sentences = re.split(r'[.!?]+', clean_text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 15]  # Increased minimum length
        
        insights = []
        
        # Look for complete action items and decisions in full sentences
        for sentence in sentences:
            sentence_lower = sentence.lower()
            
            # Skip incomplete sentences (likely from chunking boundaries)
            if self._is_incomplete_sentence(sentence):
                continue
            
            # Clean up sentence formatting
            clean_sentence = self._clean_sentence(sentence)
            if len(clean_sentence) < 20 or len(clean_sentence) > 300:
                continue
            
            # Customer Pain Points - look for problems and challenges
            pain_indicators = [
                'problem', 'challenge', 'issue', 'pain point', 'struggle', 'difficulty',
                'frustration', 'bottleneck', 'inefficiency', 'manual', 'time consuming',
                'error prone', 'lack of', 'missing', 'unable to', 'cant do'
            ]
            
            if any(indicator in sentence_lower for indicator in pain_indicators):
                if len(clean_sentence) > 25:
                    insights.append(f"Pain Point: {clean_sentence}")
            
            # Product Features - look for feature discussions
            feature_indicators = [
                'feature', 'functionality', 'capability', 'dashboard', 'reporting',
                'analytics', 'automation', 'workflow', 'interface', 'integration'
            ]
            
            if any(indicator in sentence_lower for indicator in feature_indicators):
                if len(clean_sentence) > 25:
                    insights.append(f"Product Feature: {clean_sentence}")
            
            # Objections - look for concerns and hesitations
            objection_indicators = [
                'price', 'cost', 'expensive', 'budget', 'concerns', 'worried',
                'risk', 'doubt', 'hesitant', 'not ready', 'too early', 'competition'
            ]
            
            if any(indicator in sentence_lower for indicator in objection_indicators):
                if len(clean_sentence) > 25:
                    insights.append(f"Objection: {clean_sentence}")
            
            # Competitors - look for competitive mentions
            competitor_indicators = [
                'salesforce', 'hubspot', 'microsoft', 'competitor', 'alternative',
                'current solution', 'existing tool', 'other vendor', 'versus', 'vs'
            ]
            
            if any(indicator in sentence_lower for indicator in competitor_indicators):
                if len(clean_sentence) > 25:
                    insights.append(f"Competitor: {clean_sentence}")
            
            # Decision Criteria - look for requirements and evaluation criteria
            criteria_indicators = [
                'requirement', 'criteria', 'need to see', 'must have', 'deal breaker',
                'evaluation', 'approve', 'decision maker', 'sign off', 'budget approval'
            ]
            
            if any(indicator in sentence_lower for indicator in criteria_indicators):
                if len(clean_sentence) > 25:
                    insights.append(f"Decision Criteria: {clean_sentence}")
            
            # Buyer Role - look for role and persona mentions
            role_indicators = [
                'ceo', 'cto', 'cfo', 'vp', 'director', 'manager', 'decision maker',
                'influencer', 'stakeholder', 'procurement', 'finance team'
            ]
            
            if any(indicator in sentence_lower for indicator in role_indicators):
                if len(clean_sentence) > 25:
                    insights.append(f"Buyer Role: {clean_sentence}")
            
            # Deal Stage - look for buying signals and momentum
            stage_indicators = [
                'interested', 'qualified', 'ready to move', 'close', 'purchase',
                'budget approved', 'urgency', 'priority', 'momentum', 'moving forward'
            ]
            
            if any(indicator in sentence_lower for indicator in stage_indicators):
                if len(clean_sentence) > 25:
                    insights.append(f"Deal Stage: {clean_sentence}")
            
            # Use Case - look for specific use case mentions
            usecase_indicators = [
                'use case', 'scenario', 'workflow', 'process', 'goal', 'objective',
                'outcome', 'result', 'benefit', 'value', 'roi', 'want to use'
            ]
            
            if any(indicator in sentence_lower for indicator in usecase_indicators):
                if len(clean_sentence) > 25:
                    insights.append(f"Use Case: {clean_sentence}")
            
            # Action items - look for complete sentences with action indicators
            action_indicators = [
                ' will ', ' should ', ' must ', ' need to ', ' plan to ', ' going to ', 
                ' decided to ', 'action item', 'todo', 'task', 'next step', 'follow up'
            ]
            
            if any(indicator in sentence_lower for indicator in action_indicators):
                # Ensure it's a complete thought
                if self._is_complete_action(sentence_lower):
                    insights.append(f"Action: {clean_sentence}")
            
            # Decisions - look for complete sentences with decision indicators
            decision_indicators = [
                ' decided ', ' agreed ', ' concluded ', ' determined ', ' resolved ',
                'decision', 'outcome', 'result', 'conclusion'
            ]
            
            if any(indicator in sentence_lower for indicator in decision_indicators):
                if self._is_complete_decision(sentence_lower):
                    insights.append(f"Decision: {clean_sentence}")
            
            # Issues and challenges - look for complete sentences
            issue_indicators = [
                'problem', 'issue', 'challenge', 'concern', 'risk',
                'blocking', 'stuck', 'difficult', 'struggling'
            ]
            
            if any(indicator in sentence_lower for indicator in issue_indicators):
                if self._is_complete_issue(sentence_lower):
                    insights.append(f"Issue: {clean_sentence}")
            
            # Key points - look for sentences with importance indicators
            importance_indicators = [
                'key point', 'important', 'critical', 'significant', 'main point',
                'primary', 'essential', 'crucial', 'vital'
            ]
            
            if any(indicator in sentence_lower for indicator in importance_indicators):
                insights.append(f"Key point: {clean_sentence}")
        
        # Look for metrics and numbers in complete sentences
        for sentence in sentences:
            clean_sentence = self._clean_sentence(sentence)
            if (re.search(r'\$[\d,]+|\d+%|\d+\s*(million|billion|thousand|k)', sentence, re.IGNORECASE) and
                len(clean_sentence) > 20 and len(clean_sentence) < 300 and
                not self._is_incomplete_sentence(sentence)):
                insights.append(f"Metric: {clean_sentence}")
        
        # Remove duplicates more aggressively
        unique_insights = self._deduplicate_insights(insights)
        
        # If we found specific insights, use them
        if unique_insights:
            # Limit to top 3 insights to avoid overwhelming
            final_insights = unique_insights[:3]
            summary = " | ".join(final_insights)
            return summary
        
        # If no specific insights found, create a meaningful summary from the content
        if sentences:
            # Score sentences by importance
            important_keywords = [
                'discussion', 'demo', 'platform', 'analytics', 'data', 'business',
                'functionality', 'capabilities', 'solution', 'integration',
                'features', 'benefits', 'implementation', 'timeline', 'pricing'
            ]
            
            scored_sentences = []
            for sentence in sentences:
                clean_sentence = self._clean_sentence(sentence)
                
                # Skip metadata-like sentences and incomplete ones
                if (any(sentence.startswith(prefix) for prefix in ['Title:', 'Date:', 'Brief summary:', 'Participants:']) or
                    self._is_incomplete_sentence(sentence)):
                    continue
                    
                # Score based on length and keyword presence
                length_score = min(len(clean_sentence) / 100, 1.0)  # Prefer medium-length sentences
                keyword_score = sum(1 for keyword in important_keywords 
                                  if keyword.lower() in sentence.lower()) / len(important_keywords)
                total_score = length_score + keyword_score
                
                if len(clean_sentence) > 30 and len(clean_sentence) < 300:  # Filter reasonable sentence lengths
                    scored_sentences.append((clean_sentence, total_score))
            
            # Sort by score and take top sentences
            scored_sentences.sort(key=lambda x: x[1], reverse=True)
            
            if scored_sentences:
                # Take top sentence for summary
                top_sentence = scored_sentences[0][0]
                return f"Key point: {top_sentence}"  # Format as insight
        
        # Final fallback - return empty summary rather than original content
        return ""
    
    def _is_incomplete_sentence(self, sentence: str) -> bool:
        """Check if a sentence appears to be incomplete (from chunking boundaries)"""
        sentence = sentence.strip()
        
        # Check for incomplete starts (lowercase start, missing subject)
        if sentence and sentence[0].islower():
            return True
        
        # Check for sentence fragments (too short or missing key components)
        if len(sentence) < 20:
            return True
        
        # Check for incomplete endings (ends mid-word or with connecting words)
        incomplete_endings = ['and', 'or', 'but', 'with', 'for', 'to', 'of', 'in', 'on', 'at', 'by']
        words = sentence.lower().split()
        if words and words[-1] in incomplete_endings:
            return True
        
        # Check for incomplete starts (starts with connecting words)
        incomplete_starts = ['and', 'or', 'but', 'with', 'for', 'to', 'of', 'in', 'on', 'at', 'by', 'that', 'which']
        if words and words[0] in incomplete_starts:
            return True
        
        return False
    
    def _clean_sentence(self, sentence: str) -> str:
        """Clean up sentence formatting and artifacts"""
        # Remove leading/trailing punctuation and formatting
        sentence = re.sub(r'^[\s\-•\.\,\:]+', '', sentence)
        sentence = re.sub(r'[\s\-\.\,\:]+$', '', sentence)
        
        # Remove excessive whitespace
        sentence = re.sub(r'\s+', ' ', sentence)
        
        # Remove bullet point artifacts
        sentence = re.sub(r'^[\-•]\s*', '', sentence)
        
        return sentence.strip()
    
    def _is_complete_action(self, sentence_lower: str) -> bool:
        """Check if an action sentence is complete and meaningful"""
        # Must have a subject and clear action
        action_verbs = ['will', 'should', 'must', 'need', 'plan', 'going', 'decided']
        has_subject = any(subj in sentence_lower for subj in ['they', 'we', 'he', 'she', 'it', 'company', 'team'])
        has_action = any(verb in sentence_lower for verb in action_verbs)
        return has_subject and has_action and len(sentence_lower) > 30
    
    def _is_complete_decision(self, sentence_lower: str) -> bool:
        """Check if a decision sentence is complete and meaningful"""
        decision_markers = ['decided', 'agreed', 'concluded', 'determined', 'resolved']
        has_decision = any(marker in sentence_lower for marker in decision_markers)
        has_subject = any(subj in sentence_lower for subj in ['they', 'we', 'he', 'she', 'it', 'company', 'team'])
        return has_decision and has_subject and len(sentence_lower) > 25
    
    def _is_complete_issue(self, sentence_lower: str) -> bool:
        """Check if an issue sentence is complete and meaningful"""
        issue_markers = ['problem', 'issue', 'challenge', 'concern', 'risk', 'difficult']
        has_issue = any(marker in sentence_lower for marker in issue_markers)
        return has_issue and len(sentence_lower) > 25
    
    def _deduplicate_insights(self, insights: List[str]) -> List[str]:
        """More aggressive deduplication of insights"""
        seen_content = set()
        unique_insights = []
        
        for insight in insights:
            # Get the content without the prefix for comparison
            content = insight.split(': ', 1)[1] if ': ' in insight else insight
            
            # Normalize content for comparison
            normalized = re.sub(r'\s+', ' ', content.lower().strip())
            normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
            
            # Check for substantial overlap with existing insights
            is_duplicate = False
            for seen in seen_content:
                # Check if 80% of words overlap
                seen_words = set(seen.split())
                new_words = set(normalized.split())
                if len(seen_words & new_words) / max(len(seen_words), len(new_words)) > 0.8:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                seen_content.add(normalized)
                unique_insights.append(insight)
        
        return unique_insights
    
    def _extract_metadata(self, text: str, doc_metadata: Dict[str, Any] = {}) -> Dict[str, Any]:
        """Extract document metadata"""
        metadata = doc_metadata.copy() if doc_metadata else {}
        
        # Text statistics
        metadata.update({
            'char_count': len(text),
            'word_count': len(text.split()),
            'sentence_count': len(re.split(r'[.!?]+', text)),
            'paragraph_count': len([p for p in text.split('\n\n') if p.strip()]),
            'has_numbers': bool(re.search(r'\d+', text)),
            'has_dates': bool(re.search(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}', text)),
            'has_emails': bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)),
            'has_urls': bool(re.search(r'https?://', text)),
            'avg_word_length': sum(len(word) for word in text.split()) / len(text.split()) if text.split() else 0
        })
        
        return metadata
    
    def calculate_optimal_chunk_parameters(self, text: str) -> Tuple[int, int, int]:
        """
        Calculate optimal chunk size, overlap, and min_chunk_size based on document characteristics
        
        Args:
            text: Input text to analyze
            
        Returns:
            Tuple of (chunk_size, overlap, min_chunk_size)
        """
        text_length = len(text)
        word_count = len(text.split())
        
        # Count paragraphs and sentences for structure analysis
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        paragraph_count = len(paragraphs)
        sentences = re.split(r'[.!?]+', text)
        sentence_count = len([s for s in sentences if s.strip()])
        
        # Calculate average paragraph and sentence lengths
        avg_paragraph_length = text_length / paragraph_count if paragraph_count > 0 else text_length
        avg_sentence_length = text_length / sentence_count if sentence_count > 0 else text_length
        
        # Dynamic chunking strategy based on document size
        if text_length <= 1000:  # Very small documents (< 1KB)
            # Don't chunk at all, return entire document
            return text_length + 100, 0, text_length
            
        elif text_length <= 5000:  # Small documents (1-5KB)
            # Use smaller chunks to maintain granularity
            chunk_size = 300
            overlap = 30
            min_chunk_size = 50
            
        elif text_length <= 15000:  # Medium documents (5-15KB)
            # Standard chunking
            chunk_size = 512
            overlap = 50
            min_chunk_size = 100
            
        elif text_length <= 50000:  # Large documents (15-50KB)
            # Larger chunks to maintain context
            chunk_size = 800
            overlap = 80
            min_chunk_size = 150
            
        else:  # Very large documents (>50KB)
            # Much larger chunks for very long documents
            chunk_size = 1200
            overlap = 120
            min_chunk_size = 200
        
        # Adjust based on document structure
        if paragraph_count > 0:
            # If paragraphs are naturally small, use smaller chunks
            if avg_paragraph_length < 200:
                chunk_size = min(chunk_size, 400)
            # If paragraphs are very large, increase chunk size
            elif avg_paragraph_length > 1000:
                chunk_size = max(chunk_size, 800)
        
        # Adjust based on sentence structure
        if sentence_count > 0:
            # If sentences are very short, reduce overlap
            if avg_sentence_length < 50:
                overlap = min(overlap, chunk_size // 15)
            # If sentences are very long, increase overlap
            elif avg_sentence_length > 200:
                overlap = max(overlap, chunk_size // 8)
        
        # Ensure overlap is reasonable
        overlap = min(overlap, chunk_size // 3)  # Max 1/3 of chunk size
        overlap = max(overlap, 20)  # Minimum 20 characters
        
        # Ensure min_chunk_size is reasonable
        min_chunk_size = min(min_chunk_size, chunk_size // 2)
        min_chunk_size = max(min_chunk_size, 30)
        
        return chunk_size, overlap, min_chunk_size

    def create_chunks(self, text: str, chunk_size: Optional[int] = None, 
                     overlap: Optional[int] = None, min_chunk_size: Optional[int] = None) -> List[Tuple[str, Dict[str, Any]]]:
        """
        Create overlapping chunks with position information using dynamic sizing
        
        Args:
            text: Input text to chunk
            chunk_size: Target size for each chunk (auto-calculated if None)
            overlap: Number of characters to overlap between chunks (auto-calculated if None)
            min_chunk_size: Minimum size for a chunk to be valid (auto-calculated if None)
            
        Returns:
            List of (chunk_text, chunk_info) tuples
        """
        # Calculate optimal parameters if not provided
        if chunk_size is None or overlap is None or min_chunk_size is None:
            optimal_chunk_size, optimal_overlap, optimal_min_chunk_size = self.calculate_optimal_chunk_parameters(text)
            chunk_size = chunk_size if chunk_size is not None else optimal_chunk_size
            overlap = overlap if overlap is not None else optimal_overlap
            min_chunk_size = min_chunk_size if min_chunk_size is not None else optimal_min_chunk_size
        
        chunks = []
        
        # If text is smaller than chunk_size, return as single chunk
        if len(text) <= chunk_size:
            chunk_info = {
                'start_pos': 0,
                'end_pos': len(text),
                'overlap_start': 0,
                'overlap_end': 0,
                'is_complete': True,
                'chunk_strategy': 'single_chunk',
                'original_text_length': len(text),
                'calculated_chunk_size': chunk_size,
                'calculated_overlap': overlap
            }
            return [(text, chunk_info)]
        
        # Always try paragraph-aware chunking first for PDFs and structured content
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if len(paragraphs) > 1:
            # Always use paragraph-aware chunking if there are multiple paragraphs
            # This ensures PDF documents are chunked by paragraphs regardless of length
            return self._create_paragraph_aware_chunks(text, paragraphs, chunk_size, overlap, min_chunk_size)
        
        # Fall back to sentence-aware chunking only if no paragraphs are found
        return self._create_sentence_aware_chunks(text, chunk_size, overlap, min_chunk_size)
    
    def _create_paragraph_aware_chunks(self, text: str, paragraphs: List[str], 
                                     chunk_size: int, overlap: int, min_chunk_size: int) -> List[Tuple[str, Dict[str, Any]]]:
        """Create chunks that respect paragraph boundaries, with special handling for large paragraphs"""
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_index = 0
        
        # Adjust chunk size for very large paragraphs
        max_paragraph_size = chunk_size * 3  # Consider any paragraph larger than 3x chunk_size as "very large"
        
        for paragraph in paragraphs:
            # Find the position of this paragraph in the original text
            para_start = text.find(paragraph, current_start)
            
            # Special handling for very large paragraphs
            if len(paragraph) > max_paragraph_size:
                # If we have accumulated content in the current chunk, finalize it first
                if current_chunk:
                    chunk_info = {
                        'start_pos': current_start,
                        'end_pos': para_start,
                        'overlap_start': max(0, current_start - overlap) if chunk_index > 0 else 0,
                        'overlap_end': min(len(text), para_start + overlap),
                        'is_complete': False,
                        'chunk_strategy': 'paragraph_aware',
                        'chunk_index': chunk_index
                    }
                    chunks.append((current_chunk.strip(), chunk_info))
                    chunk_index += 1
                    current_chunk = ""
                
                # Split the large paragraph into multiple chunks
                # Try to split at sentence boundaries for better coherence
                sentences = [s.strip() + "." for s in paragraph.split(".") if s.strip()]
                
                if not sentences:  # Fallback if no sentence boundaries
                    sentences = [paragraph]
                
                sentence_chunk = ""
                sentence_start = para_start
                
                for sentence in sentences:
                    if len(sentence_chunk) + len(sentence) + 1 > chunk_size:
                        # Create a chunk from accumulated sentences
                        if sentence_chunk:
                            sentence_end = sentence_start + len(sentence_chunk)
                            chunk_info = {
                                'start_pos': sentence_start,
                                'end_pos': sentence_end,
                                'overlap_start': max(0, sentence_start - overlap) if chunk_index > 0 else 0,
                                'overlap_end': min(len(text), sentence_end + overlap),
                                'is_complete': False,
                                'chunk_strategy': 'paragraph_aware_sentence_split',
                                'chunk_index': chunk_index
                            }
                            chunks.append((sentence_chunk.strip(), chunk_info))
                            chunk_index += 1
                            
                            # Start new chunk with overlap
                            sentence_start = sentence_start + len(sentence_chunk) - overlap
                            sentence_chunk = ""
                    
                    # Add sentence to chunk
                    if sentence_chunk:
                        sentence_chunk += " " + sentence
                    else:
                        sentence_chunk = sentence
                
                # Add final sentence chunk if not empty
                if sentence_chunk:
                    sentence_end = sentence_start + len(sentence_chunk)
                    chunk_info = {
                        'start_pos': sentence_start,
                        'end_pos': sentence_end,
                        'overlap_start': max(0, sentence_start - overlap) if chunk_index > 0 else 0,
                        'overlap_end': min(len(text), sentence_end + overlap),
                        'is_complete': False,
                        'chunk_strategy': 'paragraph_aware_sentence_split',
                        'chunk_index': chunk_index
                    }
                    chunks.append((sentence_chunk.strip(), chunk_info))
                    chunk_index += 1
                
                # Update the current start position for the next paragraph
                current_start = para_start + len(paragraph)
                
            # Normal paragraph handling (when not too large)
            else:
                # If adding this paragraph would exceed chunk size, finalize current chunk
                if current_chunk and len(current_chunk) + len(paragraph) + 2 > chunk_size:
                    # Finalize current chunk
                    para_end = para_start
                    chunk_info = {
                        'start_pos': current_start,
                        'end_pos': para_end,
                        'overlap_start': max(0, current_start - overlap) if chunk_index > 0 else 0,
                        'overlap_end': min(len(text), para_end + overlap),
                        'is_complete': False,
                        'chunk_strategy': 'paragraph_aware',
                        'chunk_index': chunk_index
                    }
                    chunks.append((current_chunk.strip(), chunk_info))
                    
                    # Start new chunk with overlap
                    overlap_start = max(0, para_end - overlap)
                    current_chunk = text[overlap_start:para_start] + paragraph
                    current_start = overlap_start
                    chunk_index += 1
                else:
                    # Add paragraph to current chunk
                    if current_chunk:
                        current_chunk += "\n\n" + paragraph
                    else:
                        current_chunk = paragraph
                        current_start = para_start
        
        # Add final chunk
        if current_chunk and len(current_chunk.strip()) >= min_chunk_size:
            chunk_info = {
                'start_pos': current_start,
                'end_pos': len(text),
                'overlap_start': max(0, current_start - overlap) if chunk_index > 0 else 0,
                'overlap_end': len(text),
                'is_complete': True,
                'chunk_strategy': 'paragraph_aware',
                'chunk_index': chunk_index
            }
            chunks.append((current_chunk.strip(), chunk_info))
        
        return chunks
    
    def _create_sentence_aware_chunks(self, text: str, chunk_size: int, 
                                    overlap: int, min_chunk_size: int) -> List[Tuple[str, Dict[str, Any]]]:
        """Create chunks that respect sentence boundaries"""
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            # Calculate end position
            end = min(start + chunk_size, len(text))
            
            # Try to break at sentence boundaries
            if end < len(text):
                # Look for sentence endings near the target end
                sentence_end = text.rfind('.', start, end + 50)
                if sentence_end > start + min_chunk_size:
                    end = sentence_end + 1
                else:
                    # Fallback to word boundaries
                    word_end = text.rfind(' ', start, end + 20)
                    if word_end > start + min_chunk_size:
                        end = word_end
            
            chunk_text = text[start:end].strip()
            
            # Skip if chunk is too small
            if len(chunk_text) < min_chunk_size and start > 0:
                break
            
            chunk_info = {
                'start_pos': start,
                'end_pos': end,
                'overlap_start': max(0, start - overlap) if chunk_index > 0 else 0,
                'overlap_end': min(len(text), end + overlap) if end < len(text) else len(text),
                'is_complete': end >= len(text),
                'chunk_strategy': 'sentence_aware',
                'chunk_index': chunk_index
            }
            
            chunks.append((chunk_text, chunk_info))
            
            # Move to next chunk with overlap
            start = end - overlap
            chunk_index += 1
            
            # Prevent infinite loop
            if start >= end:
                break
        
        return chunks
    
    async def process_document_async(self, doc_id: str, content: str, 
                                   categories: List[str] = [],
                                   metadata: Dict[str, Any] = {},
                                   chunk_size: Optional[int] = None, overlap: Optional[int] = None) -> List[ChunkResult]:
        """
        Asynchronously process a single document into chunks with extractions
        
        Args:
            doc_id: Unique document identifier
            content: Document text content
            categories: Document categories
            metadata: Additional document metadata
            chunk_size: Target chunk size (auto-calculated if None)
            overlap: Overlap between chunks (auto-calculated if None)
            
        Returns:
            List of ChunkResult objects
        """
        # Extract features from full document
        doc_extraction = self.extract_features(content, categories, metadata)
        
        # Add any existing insights from metadata
        existing_insights = metadata.get("existing_insights", [])
        if existing_insights:
            # Combine existing insights with extracted ones
            if doc_extraction.summary:
                combined_insights = existing_insights + [doc_extraction.summary]
                doc_extraction.summary = " | ".join(combined_insights)
        
        # Create chunks using dynamic sizing
        chunks = self.create_chunks(content, chunk_size, overlap)
        
        # Log dynamic chunking information
        if chunks and len(chunks) > 0:
            chunk_info = chunks[0][1]  # Get info from first chunk
            print(f"Dynamic chunking for {doc_id}: strategy={chunk_info.get('chunk_strategy', 'unknown')}, "
                  f"chunks={len(chunks)}, "
                  f"chunk_size={chunk_info.get('calculated_chunk_size', 'N/A')}, "
                  f"overlap={chunk_info.get('calculated_overlap', 'N/A')}")
        
        # Process each chunk
        chunk_results = []
        for chunk_index, (chunk_text, chunk_info) in enumerate(chunks):
            chunk_id = f"{doc_id}_{chunk_index}"
            
            # Extract features from chunk
            chunk_extraction = self.extract_features(chunk_text, categories)
            
            # Add relevant existing insights to this chunk if they appear in its text
            relevant_insights = []
            for insight in existing_insights:
                # Check if any keywords from the insight appear in this chunk
                insight_words = set(insight.lower().split())
                chunk_words = set(chunk_text.lower().split())
                if len(insight_words & chunk_words) >= 2:  # At least 2 words match
                    relevant_insights.append(insight)
            
            if relevant_insights:
                # Combine chunk's extracted insights with relevant existing insights
                if chunk_extraction.summary:
                    combined_insights = relevant_insights + [chunk_extraction.summary]
                    chunk_extraction.summary = " | ".join(combined_insights)
            
            # Combine document and chunk features
            combined_extraction = self._combine_extractions(doc_extraction, chunk_extraction)
            
            # Add any Gong-specific metadata
            if "gong_call_id" in metadata:
                combined_extraction.metadata.update({
                    "gong_specific": {
                        "call_type": metadata.get("call_type", ""),
                        "participants": metadata.get("participants", []),
                        "topics_discussed": metadata.get("topics_discussed", []),
                        "key_points": metadata.get("key_points", []),
                        "action_items": metadata.get("action_items", []),
                        "highlights": metadata.get("highlights", [])
                    }
                })
            
            chunk_result = ChunkResult(
                chunk_id=chunk_id,
                text=chunk_text,
                extraction=combined_extraction,
                parent_doc_id=doc_id,
                chunk_index=chunk_index,
                start_position=chunk_info['start_pos'],
                end_position=chunk_info['end_pos'],
                overlap_info=chunk_info
            )
            
            chunk_results.append(chunk_result)
        
        return chunk_results
    
    def _combine_extractions(self, doc_extraction: ExtractionResult, 
                           chunk_extraction: ExtractionResult) -> ExtractionResult:
        """Combine document-level and chunk-level extractions"""
        
        # Merge entities (prioritize chunk entities)
        combined_entities = list(set(chunk_extraction.entities + doc_extraction.entities))
        
        # Merge keywords (prioritize chunk keywords)
        combined_keywords = chunk_extraction.keywords + [
            kw for kw in doc_extraction.keywords 
            if kw not in chunk_extraction.keywords
        ]
        combined_keywords = combined_keywords[:15]  # Limit total keywords
        
        # Merge topics
        combined_topics = list(set(chunk_extraction.topics + doc_extraction.topics))
        
        # Combine and deduplicate insights
        all_insights = []
        
        # Add chunk insights first (they're more specific)
        if chunk_extraction.summary:
            all_insights.extend(chunk_extraction.summary.split(" | "))
            
        # Add document insights if they provide new information
        if doc_extraction.summary:
            doc_insights = doc_extraction.summary.split(" | ")
            for doc_insight in doc_insights:
                # Get content without prefix for comparison
                doc_content = doc_insight.split(": ", 1)[1] if ": " in doc_insight else doc_insight
                doc_content_lower = doc_content.lower()
                
                # Check if this insight is unique
                is_unique = True
                for existing_insight in all_insights:
                    existing_content = existing_insight.split(": ", 1)[1] if ": " in existing_insight else existing_insight
                    if doc_content_lower == existing_content.lower():
                        is_unique = False
                        break
                
                if is_unique:
                    all_insights.append(doc_insight)
        
        # Take top 3 most relevant insights
        final_insights = all_insights[:3]
        combined_summary = " | ".join(final_insights) if final_insights else ""
        
        # Merge metadata
        combined_metadata = {**doc_extraction.metadata, **chunk_extraction.metadata}
        combined_metadata['has_parent_context'] = True
        
        return ExtractionResult(
            entities=combined_entities,
            keywords=combined_keywords,
            topics=combined_topics,
            categories=chunk_extraction.categories,
            summary=combined_summary,
            metadata=combined_metadata
        )
    
    async def process_documents_batch(self, documents: List[Dict[str, Any]], 
                                    chunk_size: Optional[int] = None, overlap: Optional[int] = None,
                                    max_workers: int = 4) -> List[ChunkResult]:
        """
        Process multiple documents in parallel using dynamic chunking
        
        Args:
            documents: List of document dictionaries with 'id', 'content', 'categories', 'metadata'
            chunk_size: Target chunk size (auto-calculated per document if None)
            overlap: Overlap between chunks (auto-calculated per document if None)
            max_workers: Maximum number of concurrent workers
            
        Returns:
            List of all ChunkResult objects from all documents
        """
        
        async def process_single_doc(doc: Dict[str, Any]) -> List[ChunkResult]:
            return await self.process_document_async(
                doc_id=doc.get('id', ''),
                content=doc.get('content', ''),
                categories=doc.get('categories', []),
                metadata=doc.get('metadata', {}),
                chunk_size=chunk_size,
                overlap=overlap
            )
        
        # Process documents in batches to avoid overwhelming the system
        all_results = []
        semaphore = asyncio.Semaphore(max_workers)
        
        async def process_with_semaphore(doc):
            async with semaphore:
                return await process_single_doc(doc)
        
        # Create tasks for all documents
        tasks = [process_with_semaphore(doc) for doc in documents]
        
        # Execute tasks and collect results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                print(f"Error processing document: {result}")
                continue
            if isinstance(result, list):  # Add type check
                all_results.extend(result)
        
        return all_results
    
    def get_extraction_hash(self, text: str) -> str:
        """Generate hash for extraction caching"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()

# Utility functions for external use
def extract_document_features(text: str, categories: List[str] = [], 
                            use_advanced_nlp: bool = False) -> ExtractionResult:
    """Convenience function for single document extraction"""
    extractor = DocumentExtractor(use_advanced_nlp=use_advanced_nlp)
    return extractor.extract_features(text, categories)

def create_document_chunks(text: str, chunk_size: Optional[int] = None, 
                         overlap: Optional[int] = None) -> List[Tuple[str, Dict[str, Any]]]:
    """Convenience function for document chunking with dynamic sizing"""
    extractor = DocumentExtractor()
    return extractor.create_chunks(text, chunk_size, overlap)

if __name__ == "__main__":
    # Example usage
    extractor = DocumentExtractor(use_advanced_nlp=False)
    
    sample_text = """
    Machine learning is a subset of artificial intelligence that enables computers to learn 
    and make decisions from data without explicit programming. We decided to implement 
    neural networks for our recommendation system. The team agreed that we need to 
    increase our model accuracy by 15% over the next quarter. Action item: John will 
    research TensorFlow integration by Friday. The main challenge is data quality - 
    we're struggling with inconsistent user behavior data. Our revenue target is $2M 
    this quarter, and we've achieved 60% growth in user engagement. Key point: the new 
    algorithm performs significantly better than our baseline model.
    """
    
    # Extract features
    result = extractor.extract_features(sample_text, categories=['technology', 'ai'])
    print("Extracted Features:")
    print(f"Entities: {result.entities}")
    print(f"Keywords: {result.keywords}")
    print(f"Topics: {result.topics}")
    print(f"Summary/Insights: {result.summary}")
    
    # Create chunks
    chunks = extractor.create_chunks(sample_text, chunk_size=200, overlap=50)
    print(f"\nCreated {len(chunks)} chunks")
    for i, (chunk_text, chunk_info) in enumerate(chunks):
        print(f"Chunk {i}: {len(chunk_text)} characters, pos {chunk_info['start_pos']}-{chunk_info['end_pos']}")
        # Test summary for each chunk
        chunk_extraction = extractor.extract_features(chunk_text)
        print(f"  Chunk insights: {chunk_extraction.summary}")