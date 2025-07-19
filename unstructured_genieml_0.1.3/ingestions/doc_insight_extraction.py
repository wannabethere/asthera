import os
import uuid
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.models.extraction_models import (
    DocumentChunk, BusinessEntity, ExtractedPhrase, ChunkAnalysisResult,
    AnalysisResult, AnalysisDocument
)
from app.utils.chromadb import ChromaDB
from app.config.settings import get_settings

settings = get_settings()
llm = ChatOpenAI(model="gpt-4o", temperature=0.0)

class BusinessEntityExtractor:
    """
    Extracts business entities from document chunks based on questions
    """
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0.0):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.setup_extraction_chain()
    
    def setup_extraction_chain(self):
        """Set up the LangChain for entity extraction"""
        entity_prompt_template = """
        Extract business entities from this document chunk that are relevant to the question.
        
        Question: {question}
        
        Document chunk:
        {content}
        
        For each entity, provide:
        1. Name of the entity
        2. Type of entity (e.g., company, product, person, metric, etc.)
        3. Attributes (properties or characteristics)
        4. Mentions (contexts where mentioned)
        5. Relevance score from 0.0 to 1.0 (how relevant to question)
        
        FORMAT INSTRUCTIONS:
        - Return a JSON array of entity objects
        - Each object must have: "name", "entity_type", "attributes", "mentions", "relevance_score"
        - Attributes should be a dictionary of properties
        - If no entities are found, return an empty array
        - NEVER include explanations outside the JSON array
        
        Focus only on entities that are relevant to answering the question.
        """
        
        print(f"[BusinessEntityExtractor] Setting up entity extraction chain")
        
        entity_prompt = ChatPromptTemplate.from_template(entity_prompt_template)
        
        entity_parser = JsonOutputParser()
        
        self.entity_chain = entity_prompt | self.llm | entity_parser
        print(f"[BusinessEntityExtractor] Entity extraction chain set up with model: {self.llm.model_name}")
    
    def extract_entities(self, chunk: DocumentChunk, question: str) -> List[BusinessEntity]:
        """Extract business entities from a document chunk based on a question"""
        try:
            print(f"[BusinessEntityExtractor] Extracting entities for question: {question}")
            print(f"[BusinessEntityExtractor] Content length: {len(chunk.content)} characters")
            
            result = self.entity_chain.invoke({
                "question": question,
                "content": chunk.content
            })
            
            # Convert the JSON result to BusinessEntity objects
            entities = []
            for entity_data in result:
                entity = BusinessEntity(
                    name=entity_data["name"],
                    entity_type=entity_data["entity_type"],
                    attributes=entity_data["attributes"],
                    mentions=entity_data["mentions"],
                    relevance_score=entity_data["relevance_score"]
                )
                entities.append(entity)
            
            # Sort by relevance score
            entities.sort(key=lambda e: e.relevance_score, reverse=True)
            
            print(f"[BusinessEntityExtractor] Extracted {len(entities)} entities")
            if entities:
                top_entities = entities[:3]  # Show top 3 entities
                print(f"[BusinessEntityExtractor] Top entities: {', '.join([f'{e.name} ({e.entity_type})' for e in top_entities])}")
            
            return entities
        except Exception as e:
            print(f"Error extracting entities: {e}")
            # Provide fallback entities when extraction fails
            fallback_entity = BusinessEntity(
                name="Document Content",
                entity_type="document",
                attributes={"type": "business document", "description": "Contains business terminology"},
                mentions=["document content"],
                relevance_score=0.5
            )
            print(f"[BusinessEntityExtractor] Using fallback entity due to error")
            return [fallback_entity]


class DocumentAnalyzer:
    """
    Complete document analysis that extracts entities, phrases, and sentiment
    """
    def __init__(self, model_name: str = "gpt-4o", temperature: float = 0):
        self.llm = ChatOpenAI(model=model_name, temperature=temperature)
        self.entity_extractor = BusinessEntityExtractor(model_name, temperature)
        self.setup_chains()
    
    def setup_chains(self):
        """Set up extraction chains for phrases and sentiment"""
        # Phrase extraction chain
        phrase_prompt_template = """
        Based on the question, extract important phrases from this document chunk.
        
        Question: {question}
        
        Document chunk:
        {content}
        
        For each key phrase that helps answer the question, provide:
        1. The exact text of the phrase
        2. An importance score from 0.0 to 1.0 (how relevant to the question)
        3. The surrounding context
        4. A category for the phrase (optional)
        
        FORMAT INSTRUCTIONS:
        - Return the result as a JSON array of objects
        - Each object must have these fields: "text", "importance_score", "source_context"
        - The "category" field is optional
        - If no relevant phrases are found, return an empty array: []
        - NEVER include explanations outside the JSON array
        
        Focus only on phrases that are directly relevant to the question.
        """
        
        print(f"[DocumentAnalyzer] Setting up phrase extraction chain")
        
        phrase_prompt = ChatPromptTemplate.from_template(phrase_prompt_template)
        
        # Sentiment analysis chain
        sentiment_prompt_template = """
        Analyze sentiment in this document chunk related to the question.
        
        Question: {question}
        
        Document chunk:
        {content}
        
        Identify phrases that express sentiment relevant to the question.
        For each sentiment-bearing phrase:
        1. Extract the exact text
        2. Determine the sentiment (positive, negative, or neutral)
        3. Assign a sentiment strength score from 0.0 to 1.0
        4. Note the surrounding context
        
        Also provide an overall sentiment assessment for content related to the question.
        
        FORMAT INSTRUCTIONS:
        - Return the result as a JSON object with these fields:
        - "sentiment_phrases": array of objects with "text", "sentiment", "importance_score", "source_context"
        - "overall_sentiment": string with overall sentiment (positive, negative, neutral, or mixed)
        - If no sentiment phrases are found, return empty array but still provide overall_sentiment as "neutral"
        - NEVER include explanations outside the JSON object
        """
        
        print(f"[DocumentAnalyzer] Setting up sentiment analysis chain")
        
        sentiment_prompt = ChatPromptTemplate.from_template(sentiment_prompt_template)
        
        parser = JsonOutputParser()
        
        self.phrase_chain = phrase_prompt | self.llm | parser
        self.sentiment_chain = sentiment_prompt | self.llm | parser
        
        print(f"[DocumentAnalyzer] Extraction chains set up with model: {self.llm.model_name}")
    
    def analyze_chunk(self, chunk: DocumentChunk, question: str) -> ChunkAnalysisResult:
        """Analyze a document chunk based on a specific question"""
        print(f"[DocumentAnalyzer] Starting analysis for chunk {chunk.chunk_id}")
        print(f"[DocumentAnalyzer] Question: {question}")
        print(f"[DocumentAnalyzer] Content length: {len(chunk.content)} characters")
        
        # Extract business entities first
        print(f"[DocumentAnalyzer] Extracting business entities")
        
        # Log the prompt for entity extraction
        entity_prompt = f"""
Extract business entities from this document chunk that are relevant to the question.

Question: {question}

Document chunk: [Content length {len(chunk.content)} chars - first 200 chars: {chunk.content[:200]}...]

For each entity, provide:
1. Name of the entity
2. Type of entity (e.g., company, product, person, metric, etc.)
3. Attributes (properties or characteristics)
4. Mentions (contexts where mentioned)
5. Relevance score from 0.0 to 1.0 (how relevant to question)
"""
        print(f"[LLM_PROMPT] Entity extraction prompt:\n{entity_prompt[:500]}...\n")
        
        # Use the actual extraction process
        entities = self.entity_extractor.extract_entities(chunk, question)
        
        print(f"[DocumentAnalyzer] Extracted {len(entities)} business entities")
        
        # Print sample of extracted entities for debugging
        if entities:
            sample_entities = entities[:3]  # Show top 3 entities
            for i, entity in enumerate(sample_entities):
                print(f"[LLM_RESPONSE] Entity {i+1}: {entity.name} ({entity.entity_type}), relevance: {entity.relevance_score:.4f}")
        
        # Extract key phrases
        try:
            print(f"[DocumentAnalyzer] Extracting key phrases with LLM")
            
            # Log the prompt for phrase extraction
            phrase_prompt = f"""
Based on the question, extract important phrases from this document chunk.

Question: {question}

Document chunk: [Content length {len(chunk.content)} chars - first 200 chars: {chunk.content[:200]}...]

For each key phrase that helps answer the question, provide:
1. The exact text of the phrase
2. An importance score from 0.0 to 1.0 (how relevant to the question)
3. The surrounding context
4. A category for the phrase (optional)
"""
            print(f"[LLM_PROMPT] Phrase extraction prompt:\n{phrase_prompt[:500]}...\n")
            
            phrases_result = self.phrase_chain.invoke({
                "question": question,
                "content": chunk.content
            })
            
            # Log sample of the response
            print(f"[LLM_RESPONSE] Phrase extraction result sample: {str(phrases_result)[:300]}...")
            
            key_phrases = [
                ExtractedPhrase(
                    text=phrase["text"],
                    sentiment="neutral",  # Default, will be updated
                    importance_score=phrase["importance_score"],
                    source_context=phrase["source_context"],
                    category=phrase.get("category")
                )
                for phrase in phrases_result
            ]
            print(f"[DocumentAnalyzer] Processed {len(key_phrases)} key phrases")
            
            # Log sample of extracted phrases
            if key_phrases:
                sample_phrases = sorted(key_phrases, key=lambda p: p.importance_score, reverse=True)[:3]
                for i, phrase in enumerate(sample_phrases):
                    print(f"[LLM_RESPONSE] Phrase {i+1}: '{phrase.text}', importance: {phrase.importance_score:.4f}")
            
        except Exception as e:
            print(f"Error extracting phrases: {e}")
            # Provide fallback phrases
            key_phrases = [
                ExtractedPhrase(
                    text="Document content",
                    sentiment="neutral",
                    importance_score=0.5,
                    source_context="Full document",
                    category="general"
                )
            ]
            print(f"[DocumentAnalyzer] Using fallback key phrases due to error")
        
        # Extract sentiment
        try:
            print(f"[DocumentAnalyzer] Extracting sentiment with LLM")
            
            # Log the prompt for sentiment extraction
            sentiment_prompt = f"""
Analyze sentiment in this document chunk related to the question.

Question: {question}

Document chunk: [Content length {len(chunk.content)} chars - first 200 chars: {chunk.content[:200]}...]

Identify phrases that express sentiment relevant to the question.
For each sentiment-bearing phrase:
1. Extract the exact text
2. Determine the sentiment (positive, negative, or neutral)
3. Assign a sentiment strength score from 0.0 to 1.0
4. Note the surrounding context

Also provide an overall sentiment assessment for content related to the question.
"""
            print(f"[LLM_PROMPT] Sentiment analysis prompt:\n{sentiment_prompt[:500]}...\n")
            
            sentiment_result = self.sentiment_chain.invoke({
                "question": question,
                "content": chunk.content
            })
            
            # Log sample of the sentiment response
            print(f"[LLM_RESPONSE] Sentiment analysis result sample: {str(sentiment_result)[:300]}...")
            
            sentiment_phrases = [
                ExtractedPhrase(
                    text=phrase["text"],
                    sentiment=phrase["sentiment"],
                    importance_score=phrase["importance_score"],
                    source_context=phrase["source_context"]
                )
                for phrase in sentiment_result.get("sentiment_phrases", [])
            ]
            
            overall_sentiment = sentiment_result.get("overall_sentiment", "neutral")
            print(f"[DocumentAnalyzer] Extracted {len(sentiment_phrases)} sentiment phrases")
            print(f"[DocumentAnalyzer] Overall sentiment: {overall_sentiment}")
            
            # Log sample of sentiment phrases
            if sentiment_phrases:
                sample_sentiment = sorted(sentiment_phrases, key=lambda p: p.importance_score, reverse=True)[:3]
                for i, phrase in enumerate(sample_sentiment):
                    print(f"[LLM_RESPONSE] Sentiment phrase {i+1}: '{phrase.text}', sentiment: {phrase.sentiment}")
                    
        except Exception as e:
            print(f"Error extracting sentiment: {e}")
            # Provide fallback sentiment
            sentiment_phrases = []
            overall_sentiment = "neutral"
            print(f"[DocumentAnalyzer] Using fallback sentiment due to error")
        
        # Update sentiment for key phrases if they match sentiment phrases
        sentiment_dict = {phrase.text: phrase.sentiment for phrase in sentiment_phrases}
        for phrase in key_phrases:
            if phrase.text in sentiment_dict:
                phrase.sentiment = sentiment_dict[phrase.text]
        
        print(f"[DocumentAnalyzer] Analysis complete for chunk {chunk.chunk_id}")
        
        # Create and return the result
        result = ChunkAnalysisResult(
            chunk_id=chunk.chunk_id,
            business_entities=entities,
            key_phrases=key_phrases,
            sentiment_phrases=sentiment_phrases,
            overall_sentiment=overall_sentiment,
            analysis_timestamp=datetime.now().isoformat()
        )
        
        # Log performance metrics
        print(f"[METRICS] Analysis produced {len(entities)} entities, {len(key_phrases)} key phrases, {len(sentiment_phrases)} sentiment phrases")
        
        return result

    def analyze_chunk_batch(self, chunk: DocumentChunk, questions: List[str]) -> Dict[str, ChunkAnalysisResult]:
        """Analyze a document chunk against multiple questions with a single LLM call"""
        # Combine questions into a single query string to analyze in one go
        combined_question = ", ".join(questions)
        
        print(f"[DocumentAnalyzer] Analyzing chunk {chunk.chunk_id} with combined questions")
        print(f"[DocumentAnalyzer] Number of questions combined: {len(questions)}")
        print(f"[DocumentAnalyzer] Content length: {len(chunk.content)} characters")
        
        # Get the combined analysis results
        try:
            print(f"[DocumentAnalyzer] Making a single LLM call to analyze all questions")
            start_time = datetime.now()
            combined_result = self.analyze_chunk(chunk, combined_question)
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            print(f"[DocumentAnalyzer] Analysis complete in {processing_time:.2f} seconds")
            print(f"[DocumentAnalyzer] Found {len(combined_result.business_entities)} entities, {len(combined_result.key_phrases)} key phrases")
            
            # Log the top entities and phrases for visibility
            if combined_result.business_entities:
                top_entities = sorted(combined_result.business_entities, key=lambda e: e.relevance_score, reverse=True)[:3]
                print(f"[DocumentAnalyzer] Top entities: {', '.join([f'{e.name} ({e.entity_type})' for e in top_entities])}")
            
            if combined_result.key_phrases:
                top_phrases = sorted(combined_result.key_phrases, key=lambda p: p.importance_score, reverse=True)[:3]
                phrase_texts = [f'"{p.text}"' for p in top_phrases]
                print(f"[DocumentAnalyzer] Top phrases: {', '.join(phrase_texts)}")
            
            print(f"[DocumentAnalyzer] Overall sentiment: {combined_result.overall_sentiment}")
            
        except Exception as e:
            print(f"[DocumentAnalyzer] Error in combined analysis: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Create a result for each individual question using the combined results
        print(f"[DocumentAnalyzer] Distributing combined results to {len(questions)} individual questions")
        results = {}
        for question in questions:
            print(f"[DocumentAnalyzer] Creating result for question: '{question}'")
            results[question] = ChunkAnalysisResult(
                chunk_id=combined_result.chunk_id,
                business_entities=combined_result.business_entities,
                key_phrases=combined_result.key_phrases,
                sentiment_phrases=combined_result.sentiment_phrases,
                overall_sentiment=combined_result.overall_sentiment,
                analysis_timestamp=combined_result.analysis_timestamp
            )
        
        print(f"[DocumentAnalyzer] Batch analysis complete - results distributed to {len(results)} questions")
        return results


class QuestionBasedProcessor:
    """
    Process document chunks based on specific questions
    """
    def __init__(self, model_name: str = "gpt-4o", questions_collection: str = "extraction_questions"):
        self.analyzer = DocumentAnalyzer(model_name=model_name)
        self.chroma_db = ChromaDB()
        self.questions_collection = questions_collection
    
    def process_chunks_for_questions(self, 
                                   chunks: List[DocumentChunk],
                                   questions: List[str]) -> List[ChunkAnalysisResult]:
        """Process multiple chunks for a list of questions combined into a single query"""
        # Combine questions into a single query string
        combined_question = ", ".join(questions)
        
        results = []
        for chunk in chunks:
            result = self.analyzer.analyze_chunk(chunk, combined_question)
            results.append(result)
        return results
    
    def process_chunks_for_question(self, 
                                  chunks: List[DocumentChunk],
                                  question: str) -> List[ChunkAnalysisResult]:
        """Process multiple chunks for a specific question"""
        results = []
        for chunk in chunks:
            try:
                result = self.analyzer.analyze_chunk(chunk, question)
                results.append(result)
            except Exception as e:
                print(f"Error processing chunk {chunk.chunk_id} for question '{question}': {e}")
                # Create a minimal result to avoid breaking the pipeline
                fallback_result = ChunkAnalysisResult(
                    chunk_id=chunk.chunk_id,
                    business_entities=[],
                    key_phrases=[],
                    sentiment_phrases=[],
                    overall_sentiment="neutral",
                    analysis_timestamp=datetime.now().isoformat()
                )
                results.append(fallback_result)
        return results
    
    def summarize_results(self, results: List[ChunkAnalysisResult]) -> Dict[str, Any]:
        """Combine and summarize results from multiple chunks"""
        if not results:
            return {
                "business_entities": [],
                "key_phrases": [],
                "sentiment": {
                    "overall": "unknown",
                    "distribution": {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0},
                    "key_sentiment_phrases": []
                },
                "total_chunks_analyzed": 0,
                "analysis_timestamp": datetime.now().isoformat()
            }
        
        # Merge entities across chunks
        entity_map = {}  # Map entity names to their merged versions
        
        for result in results:
            for entity in result.business_entities:
                if entity.name in entity_map:
                    # Merge with existing entity
                    existing = entity_map[entity.name]
                    # Combine mentions without duplicates
                    existing.mentions.extend([m for m in entity.mentions if m not in existing.mentions])
                    # Update attributes (simple overwrite for now)
                    existing.attributes.update(entity.attributes)
                    # Update relevance score (take max)
                    existing.relevance_score = max(existing.relevance_score, entity.relevance_score)
                else:
                    # Add new entity
                    entity_map[entity.name] = entity
        
        # Convert to list and sort by relevance
        merged_entities = list(entity_map.values())
        merged_entities.sort(key=lambda e: e.relevance_score, reverse=True)
        
        # Collect all phrases
        all_key_phrases = []
        all_sentiment_phrases = []
        
        # Track sentiment distribution
        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
        
        for result in results:
            # Collect phrases
            all_key_phrases.extend(result.key_phrases)
            all_sentiment_phrases.extend(result.sentiment_phrases)
            
            # Track sentiment
            overall = result.overall_sentiment.lower()
            if overall in sentiment_counts:
                sentiment_counts[overall] += 1
            else:
                sentiment_counts["mixed"] += 1
        
        # Determine overall sentiment
        total_chunks = len(results)
        if total_chunks > 0:
            max_sentiment = max(sentiment_counts.items(), key=lambda x: x[1])
            if max_sentiment[1] > total_chunks * 0.5:
                overall_sentiment = max_sentiment[0]
            else:
                overall_sentiment = "mixed"
        else:
            overall_sentiment = "unknown"
        
        # Sort phrases by importance
        sorted_key_phrases = sorted(
            all_key_phrases, 
            key=lambda p: p.importance_score, 
            reverse=True
        )
        
        sorted_sentiment_phrases = sorted(
            all_sentiment_phrases, 
            key=lambda p: p.importance_score, 
            reverse=True
        )
        
        # Convert to serializable format
        return {
            "business_entities": [
                {
                    "name": e.name,
                    "entity_type": e.entity_type,
                    "attributes": e.attributes,
                    "mentions": e.mentions[:3],  # Limit to 3 example mentions
                    "relevance_score": e.relevance_score
                }
                for e in merged_entities[:20]  # Top 20 entities
            ],
            "key_phrases": [
                {
                    "text": p.text,
                    "sentiment": p.sentiment,
                    "importance_score": p.importance_score,
                    "source_context": p.source_context,
                    "category": p.category
                }
                for p in sorted_key_phrases[:15]  # Top 15 phrases
            ],
            "sentiment": {
                "overall": overall_sentiment,
                "distribution": sentiment_counts,
                "key_sentiment_phrases": [
                    {
                        "text": p.text,
                        "sentiment": p.sentiment,
                        "importance_score": p.importance_score
                    }
                    for p in sorted_sentiment_phrases[:10]  # Top 10 sentiment phrases
                ]
            },
            "total_chunks_analyzed": total_chunks,
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    def get_relevant_questions_from_chromadb(self, chunk_content: str, document_type: str, n_results: int = 5) -> List[str]:
        """
        Query ChromaDB to get relevant questions based on document content
        
        Args:
            chunk_content: The document chunk content to match against
            document_type: The type of document (for fallback questions)
            n_results: Number of questions to retrieve
            
        Returns:
            List of relevant questions
        """
        try:
            print(f"[QuestionBasedProcessor] Querying ChromaDB collection '{self.questions_collection}' for relevant questions")
            print(f"[QuestionBasedProcessor] Using raw document content to find relevant questions")
            print(f"[QuestionBasedProcessor] Content length for embedding: {len(chunk_content)} characters")
            collection_name = self.questions_collection
            
            # Query ChromaDB with the raw document content
            # Use the whole content if possible, or at least a significant chunk
            max_query_length = 8000  # Most embedding models can handle this size
            query_text = chunk_content[:max_query_length]
            
            # Query ChromaDB for similar questions
            results = self.chroma_db.query_collection(
                collection_name=collection_name,
                query_texts=[query_text],
                n_results=n_results
            )
            
            # Extract the questions from results
            if 'documents' in results and results['documents'] and len(results['documents'][0]) > 0:
                questions = results['documents'][0]
                print(f"[QuestionBasedProcessor] Retrieved {len(questions)} questions from ChromaDB")
                
                # Log each question for better visibility
                for i, question in enumerate(questions):
                    print(f"[QuestionBasedProcessor] Question {i+1}: {question}")
                
                # Also log the distances and convert to proper relevance scores
                if 'distances' in results and results['distances'] and len(results['distances'][0]) > 0:
                    distances = results['distances'][0]
                    
                    # ChromaDB distances are typically cosine distances (smaller is better)
                    # We need to convert them to similarity scores (1.0 = perfect match, 0.0 = no match)
                    for i, (question, distance) in enumerate(zip(questions, distances)):
                        # Apply proper conversion from distance to similarity (relevance) score
                        # For cosine distance: similarity = 1 - distance
                        # But make sure to handle very large distances properly
                        if distance > 2.0:  # Distance too large, likely not relevant
                            relevance_score = 0.0
                        else:
                            # Normalize distances between 0-2 to relevance scores between 0-1
                            # Distance of 0 means perfect match (1.0 relevance)
                            # Distance of 2 means completely unrelated (0.0 relevance)
                            relevance_score = max(0.0, 1.0 - (distance / 2.0))
                        
                        print(f"[QuestionBasedProcessor] Question {i+1} relevance score: {relevance_score:.4f} (distance: {distance:.4f})")
                
                return questions
            else:
                # Fallback to default questions if none found
                print("[QuestionBasedProcessor] No questions found in ChromaDB, using defaults")
                from app.config.extraction_config import get_questions_for_document_type
                default_questions = get_questions_for_document_type(document_type)
                print(f"[QuestionBasedProcessor] Using {len(default_questions)} default questions for document type: {document_type}")
                for i, question in enumerate(default_questions):
                    print(f"[QuestionBasedProcessor] Default question {i+1}: {question}")
                return default_questions
                
        except Exception as e:
            print(f"[QuestionBasedProcessor] Error querying ChromaDB: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to default questions if error occurs
            from app.config.extraction_config import get_questions_for_document_type
            default_questions = get_questions_for_document_type(document_type)
            print(f"[QuestionBasedProcessor] Using {len(default_questions)} fallback questions due to error")
            for i, question in enumerate(default_questions):
                print(f"[QuestionBasedProcessor] Fallback question {i+1}: {question}")
            return default_questions
    
    def process_multiple_questions_efficiently(self, 
                                            chunks: List[DocumentChunk],
                                            document_type: str = "documentation") -> Dict[str, Dict[str, Any]]:
        """Process document chunks with questions from ChromaDB using a single LLM call"""
        results = {}
        total_start_time = datetime.now()
        total_questions = 0
        
        for chunk in chunks:
            try:
                chunk_start_time = datetime.now()
                print(f"[QuestionBasedProcessor] Processing chunk {chunk.chunk_id} efficiently")
                print(f"[METRICS] Starting processing for chunk {chunk.chunk_id}")
                
                # Get relevant questions from ChromaDB
                question_start_time = datetime.now()
                questions = self.get_relevant_questions_from_chromadb(
                    chunk_content=chunk.content, 
                    document_type=document_type
                )
                question_end_time = datetime.now()
                question_retrieval_time = (question_end_time - question_start_time).total_seconds()
                print(f"[METRICS] ChromaDB question retrieval time: {question_retrieval_time:.2f} seconds")
                
                if not questions:
                    print("[QuestionBasedProcessor] No questions available, skipping chunk")
                    continue
                
                # Track total questions processed
                total_questions += len(questions)
                
                print(f"[QuestionBasedProcessor] Starting batch processing of {len(questions)} questions with a single LLM call")
                llm_call_start = datetime.now()
                
                # Process the chunk with all questions at once
                chunk_results = self.analyzer.analyze_chunk_batch(chunk, questions)
                
                llm_call_end = datetime.now()
                llm_processing_time = (llm_call_end - llm_call_start).total_seconds()
                print(f"[QuestionBasedProcessor] Batch processing completed in {llm_processing_time:.2f} seconds")
                print(f"[QuestionBasedProcessor] Average time per question: {llm_processing_time/len(questions):.2f} seconds")
                print(f"[METRICS] LLM batch processing time: {llm_processing_time:.2f} seconds")
                print(f"[METRICS] LLM average time per question: {llm_processing_time/len(questions):.2f} seconds")
                
                # For each question, create a summary and add it to the results
                summary_start_time = datetime.now()
                print(f"[QuestionBasedProcessor] Generating summaries for each question")
                for question, result in chunk_results.items():
                    print(f"[QuestionBasedProcessor] Summarizing results for question: '{question}'")
                    summary = self.summarize_results([result])
                    
                    # Log some key details from the summary
                    print(f"[QuestionBasedProcessor] Summary contains {len(summary['business_entities'])} entities, {len(summary['key_phrases'])} key phrases")
                    print(f"[QuestionBasedProcessor] Overall sentiment: {summary['sentiment']['overall']}")
                    
                    # Create AnalysisResult for each question's results
                    insight_version = AnalysisResult(
                        result_id=str(uuid.uuid4()),
                        document_id=str(uuid.uuid4()),  # Generate new document ID
                        source_type="",  # Empty as per original implementation
                        doc_type="",  # Empty as per original implementation
                        entities=summary["business_entities"],
                        key_phrases=summary["key_phrases"],
                        sentiment=summary["sentiment"],
                        total_chunks_analyzed=summary["total_chunks_analyzed"],
                        analysis_timestamp=summary["analysis_timestamp"]
                    )
                    
                    # Create corresponding AnalysisDocument
                    document = AnalysisDocument(
                        document_id=insight_version.document_id,
                        content="",  # Empty as we're working with chunks
                        metadata={},  # Empty metadata
                        source_type="",  # Empty as per original implementation
                        doc_type=""  # Empty as per original implementation
                    )
                    
                    # Add to results
                    results[question] = {
                        "insight_version": insight_version,
                        "document": document
                    }
                
                summary_end_time = datetime.now()
                summary_time = (summary_end_time - summary_start_time).total_seconds()
                print(f"[METRICS] Summary generation time: {summary_time:.2f} seconds")
                print(f"[METRICS] Average time per summary: {summary_time/len(questions):.2f} seconds")
                
                print(f"[QuestionBasedProcessor] Successfully generated insights for all {len(questions)} questions")
                
                # Log chunk processing metrics
                chunk_end_time = datetime.now()
                chunk_processing_time = (chunk_end_time - chunk_start_time).total_seconds()
                print(f"[METRICS] Total chunk processing time: {chunk_processing_time:.2f} seconds")
                
            except Exception as e:
                print(f"[QuestionBasedProcessor] Error processing chunk: {e}")
                import traceback
                traceback.print_exc()
        
        # Log total processing metrics
        total_end_time = datetime.now()
        total_processing_time = (total_end_time - total_start_time).total_seconds()
        print(f"[METRICS] Total processing time for all chunks: {total_processing_time:.2f} seconds")
        print(f"[METRICS] Total questions processed: {total_questions}")
        if total_questions > 0:
            print(f"[METRICS] Average processing time per question: {total_processing_time/total_questions:.2f} seconds")
        
        print(f"[QuestionBasedProcessor] Completed efficient processing with {len(results)} question insights")
        return results
    
    def process_multiple_questions(self, 
                                 chunks: List[DocumentChunk],
                                 questions: Optional[List[str]] = None,
                                 document_type: str = "documentation",
                                 use_chromadb: bool = True) -> Dict[str, Dict[str, Any]]:
        """
        Process multiple questions across document chunks.
        Can use either provided questions or retrieve from ChromaDB.
        """
        # If use_chromadb flag is set and no questions provided, use the efficient method
        if use_chromadb and not questions:
            return self.process_multiple_questions_efficiently(chunks, document_type)
            
        # Otherwise, use the original implementation with provided questions
        # Ensure questions is not None to avoid iteration error
        if questions is None:
            from app.config.extraction_config import get_questions_for_document_type
            questions = get_questions_for_document_type(document_type)
            
        results = {}
        
        for question in questions:
            try:
                chunk_results = self.process_chunks_for_question(chunks, question)
                summary = self.summarize_results(chunk_results)
                
                # Create AnalysisResult for each question's results
                insight_version = AnalysisResult(
                    result_id=str(uuid.uuid4()),
                    document_id=str(uuid.uuid4()),  # Generate new document ID
                    source_type="",  # Empty as per original implementation
                    doc_type="",  # Empty as per original implementation
                    entities=summary["business_entities"],
                    key_phrases=summary["key_phrases"],
                    sentiment=summary["sentiment"],
                    total_chunks_analyzed=summary["total_chunks_analyzed"],
                    analysis_timestamp=summary["analysis_timestamp"]
                )
                
                # Create corresponding AnalysisDocument
                document = AnalysisDocument(
                    document_id=insight_version.document_id,
                    content="",  # Empty as we're working with chunks
                    metadata={},  # Empty metadata
                    source_type="",  # Empty as per original implementation
                    doc_type=""  # Empty as per original implementation
                )
                
                # Update results with the created objects
                results[question] = {
                    "insight_version": insight_version,
                    "document": document
                }
            except Exception as e:
                print(f"Error processing question '{question}': {e}")
                import traceback
                traceback.print_exc()
                
                # Create minimal objects as fallback
                fallback_insight = AnalysisResult(
                    result_id=str(uuid.uuid4()),
                    document_id=str(uuid.uuid4()),
                    source_type="",
                    doc_type="",
                    entities=[{"name": "Error", "entity_type": "error", "attributes": {"error": str(e)}, "mentions": ["error"], "relevance_score": 0.0}],
                    key_phrases=[],
                    sentiment={"overall": "neutral", "distribution": {"positive": 0, "negative": 0, "neutral": 1, "mixed": 0}, "key_sentiment_phrases": []},
                    total_chunks_analyzed=len(chunks),
                    analysis_timestamp=datetime.now().isoformat()
                )
                
                fallback_document = AnalysisDocument(
                    document_id=fallback_insight.document_id,
                    content="",
                    metadata={"error": str(e)},
                    source_type="",
                    doc_type=""
                )
                
                results[question] = {
                    "insight_version": fallback_insight,
                    "document": fallback_document
                }
                
        return results


# Example usage
if __name__ == "__main__":
    # Create sample document chunks
    chunks = [
        DocumentChunk(
            chunk_id="chunk1",
            content="""
            In Q1 2025, Tesla reported $18.3 billion in revenue, a 15% increase year-over-year.
            Electric vehicle deliveries rose to 422,000 units, exceeding analyst expectations.
            CEO Elon Musk announced expansion plans in Europe and Asia, with new Gigafactories
            planned for Berlin and Shanghai. The company's energy storage business grew 40%,
            with Powerwall residential installations doubling compared to Q1 2024.
            """,
            metadata={"source": "earnings_call", "page": 1}
        ),
        DocumentChunk(
            chunk_id="chunk2",
            content="""
            Despite supply chain challenges affecting semiconductor availability, Tesla maintained
            a 22% gross margin on vehicle sales. The company reduced prices on Model 3 and Model Y
            vehicles in North America by an average of 3.5%, which contributed to increased demand.
            Competitors like Rivian and Lucid continue to struggle with production scale, while
            traditional automakers GM and Ford are accelerating their EV programs.
            """,
            metadata={"source": "earnings_call", "page": 2}
        )
    ]
    
    # Define business questions
    questions = [
        "How did Tesla perform financially in the latest quarter?",
        "What are Tesla's expansion plans?",
        "How is Tesla handling competition in the EV market?"
    ]
    
    # Process the document chunks for each question
    processor = QuestionBasedProcessor()
    question_results = processor.process_multiple_questions(chunks, questions)
    
    # Print results for each question
    for question, result in question_results.items():
        print(f"\n=== Analysis for: {question} ===")
        
        print("\nTop Business Entities:")
        for entity in result["insight_version"].entities[:5]:
            print(f"- {entity['name']} ({entity['entity_type']}): relevance {entity['relevance_score']:.2f}")
            
        print("\nTop Key Phrases:")
        for phrase in result["insight_version"].key_phrases[:3]:
            print(f"- {phrase['text']} [{phrase['sentiment']}]")
            
        print(f"\nOverall Sentiment: {result['insight_version'].sentiment['overall']}")