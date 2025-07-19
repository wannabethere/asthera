"""
Gong extractor implementation.

This module provides the extractor for Gong call data.
"""
import json
import sys
import logging
from datetime import datetime
from typing import Dict, List, Any, Tuple
from pathlib import Path

from .base import IExtractor

# Configure logging
logger = logging.getLogger(__name__)

class GongExtractor(IExtractor):
    """Extractor for Gong call data."""
    
    def extract(self, config: Dict[str, Any]) -> List[Any]:
        """
        Extract Gong call documents from the provided configuration.
        
        Args:
            config: Configuration for extraction, including:
                - input_path: Path to the JSONL file with Gong call data
                - test_mode: Whether to run in test mode
                - test_line_indices: Indices of lines to process in test mode
                
        Returns:
            List of extracted Gong call documents
        """
        debug_mode = config.get("debug", False)
        input_path = config.get("input_path")
        if not input_path:
            raise ValueError("input_path must be provided in the configuration")
        
        test_mode = config.get("test_mode", False)
        test_line_indices = config.get("test_line_indices", [])
        
        logger.info(f"Starting Gong extraction from {input_path}")
        if debug_mode:
            logger.debug(f"Extraction config: {json.dumps(config, default=str)}")
        
        # Process the input file
        calls = []
        
        with open(input_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                
                # In test mode, only process specified lines
                if test_mode and test_line_indices and i not in test_line_indices:
                    continue
                
                if debug_mode:
                    logger.debug(f"Processing line {i} from input file")
                
                record = json.loads(line)
                
                # Extract fields and get the full data
                extracted_fields, full_data = self.extract_gong_fields(record)
                
                # Create speaker-keyword mapping
                speaker_keywords, keyword_speakers = self.create_speaker_keyword_mapping(record)
                
                # Format the extracted fields as a structured content block
                formatted_content = []
                
                # Add title and high-level metadata first
                if extracted_fields.get("title"):
                    formatted_content.append(f"Title: {extracted_fields['title']}")
                
                if extracted_fields.get("date"):
                    formatted_content.append(f"Date: {extracted_fields['date']}")
                
                # Add URL if available
                if extracted_fields.get("url"):
                    formatted_content.append(f"URL: {extracted_fields['url']}")
                
                # Add brief summary if available
                if extracted_fields.get("brief"):
                    formatted_content.append(f"Brief summary: {extracted_fields['brief']}")
                
                # Add key points in a more readable format
                if extracted_fields.get("keyPoints"):
                    key_points_text = "Key points:\n"
                    for i, point in enumerate(extracted_fields["keyPoints"], 1):
                        key_points_text += f"  {i}. {point}\n"
                    formatted_content.append(key_points_text)
                
                # Add action items in a readable format
                if extracted_fields.get("actionItems"):
                    action_items_text = "Action items:\n"
                    for i, item in enumerate(extracted_fields["actionItems"], 1):
                        action_items_text += f"  {i}. {item}\n"
                    formatted_content.append(action_items_text)
                
                # Add comprehensive keyword tracking with speaker breakdown
                if keyword_speakers:
                    keywords_text = "Keywords tracked:\n"
                    
                    # Sort keywords by those with mentions first, then alphabetically
                    sorted_keywords = sorted(
                        keyword_speakers.keys(),
                        key=lambda k: (sum(keyword_speakers[k].values()) == 0, k.lower())
                    )
                    
                    for i, keyword_name in enumerate(sorted_keywords, 1):
                        speakers_for_keyword = keyword_speakers[keyword_name]
                        total_count = sum(speakers_for_keyword.values())
                        
                        keywords_text += f"  {i}. {keyword_name} (mentioned {total_count} times total)\n"
                        
                        # Add speaker breakdown for this keyword
                        if speakers_for_keyword:
                            for speaker_name, count in speakers_for_keyword.items():
                                keywords_text += f"    - {speaker_name}: {count} times\n"
                        else:
                            keywords_text += f"    - No mentions\n"
                    
                    formatted_content.append(keywords_text)
                
                # Get question counts for metadata
                interaction_data = full_data.get("interaction", {})
                company_questions = interaction_data.get("questions", {}).get("companyCount", 0)
                non_company_questions = interaction_data.get("questions", {}).get("nonCompanyCount", 0)
                
                # Get speaker data and interaction stats for metadata
                interaction_speakers = interaction_data.get("speakers", [])
                interaction_stats = interaction_data.get("interactionStats", [])
                
                # Add highlights in a cleaner format
                if extracted_fields.get("highlights"):
                    for highlight in extracted_fields["highlights"]:
                        title = highlight.get("title", "Highlights")
                        items = highlight.get("items", [])
                        if items:
                            highlights_text = f"{title}:\n"
                            for i, item in enumerate(items, 1):
                                highlights_text += f"  {i}. {item}\n"
                            formatted_content.append(highlights_text)
                
                # Add topics if available
                if extracted_fields.get("topics"):
                    topics_text = "Topics discussed: " + ", ".join(f"{topic['name']} ({topic['duration']})" for topic in extracted_fields["topics"])
                    formatted_content.append(topics_text)
                
                # Add outline in a more readable format
                if extracted_fields.get("outline"):
                    outline_text = "Call outline:\n"
                    for section in extracted_fields["outline"]:
                        section_name = section.get("section", "")
                        start_time = section.get("startTime", "")
                        duration = section.get("duration", "")
                        time_info = ""
                        if start_time and duration:
                            time_info = f" (starts at {start_time}, duration: {duration})"
                        
                        items = section.get("items", [])
                        if section_name and items:
                            outline_text += f"  • {section_name}{time_info}:\n"
                            for item in items:
                                outline_text += f"    - {item}\n"
                    formatted_content.append(outline_text)
                
                # Format parties data specially with more details
                if extracted_fields.get("parties"):
                    parties_text = "Participants:\n"
                    for party in extracted_fields.get("parties", []):
                        name = party.get("name", "Unknown")
                        role = party.get("role", "")
                        email = party.get("email", "")
                        affiliation = party.get("affiliation", "")
                        title = party.get("title", "")
                        
                        # Format with clear delimiters for better parsing
                        speaker_id = party.get("id", "")
                        detail_parts = []
                        
                        # Add title if available
                        if title:
                            detail_parts.append(f"title:{title}")
                            
                        # Add role if available and different from title
                        if role and role != title:
                            detail_parts.append(f"role:{role}")
                            
                        # Add affiliation
                        if affiliation:
                            detail_parts.append(f"affiliation:{affiliation}")
                        
                        # Join with semicolons for easier parsing
                        detail_text = f" ({'; '.join(detail_parts)})" if detail_parts else ""
                        email_text = f" - {email}" if email else ""
                        
                        parties_text += f"  - {name} [id:{speaker_id}]{detail_text}{email_text}\n"
                    formatted_content.append(parties_text)
                
                # Add participant grouping if available
                if extracted_fields.get("participants"):
                    participants = extracted_fields["participants"]
                    if participants.get("tellius"):
                        text = ["Internal participants:"]
                        for p in participants["tellius"]:
                            text.append(f"  - {p['name']} [id:{p['id']}]")
                        formatted_content.append("\n".join(text))
                    if participants.get("nonTellius"):
                        text = ["External participants:"]
                        for p in participants["nonTellius"]:
                            text.append(f"  - {p['name']} [id:{p['id']}]")
                        formatted_content.append("\n".join(text))
                
                # Join everything into a content string
                content_text = "\n\n".join(formatted_content)
                
                if not content_text:
                    continue
                
                # Create document structure
                metadata = full_data.get("metaData", {})
                doc_id = metadata.get("id", "")
                
                call = {
                    "call_id": doc_id,
                    "document_id": doc_id,  # Add document_id for consistency
                    "content": content_text,
                    "metadata": {
                        "call_id": doc_id,
                        "document_id": doc_id,  # Add document_id for consistency
                        "document_type": "gong_transcript",
                        "title": extracted_fields.get("title", "Untitled Call"),
                        "url": extracted_fields.get("url", ""),
                        "date": extracted_fields.get("date", ""),
                        "date_timestamp": extracted_fields.get("date_timestamp", 0),
                        "source_type": "gong",
                        "event_type": "import",
                        "question_count": company_questions + non_company_questions,
                        "internal_question_count": company_questions,
                        "external_question_count": non_company_questions,
                        "interaction_speakers": interaction_speakers,
                        "interaction_stats": interaction_stats
                    }
                }
                
                # Ensure all null values are removed from metadata
                call["metadata"] = self.remove_nulls(call["metadata"])
                
                calls.append(call)
                
                if debug_mode:
                    logger.debug(f"Extracted call {doc_id}: {extracted_fields.get('title', 'Untitled Call')}")
                    logger.debug(f"GONG EXTRACTOR OUTPUT: {json.dumps(call, indent=2, default=str)}")
        
        logger.info(f"Gong extraction completed. Extracted {len(calls)} calls.")
        return calls
    
    def remove_nulls(self, obj: Any) -> Any:
        """Recursively remove null values from dictionaries and lists."""
        if isinstance(obj, dict):
            return {k: self.remove_nulls(v) for k, v in obj.items() if v is not None}
        elif isinstance(obj, list):
            return [self.remove_nulls(item) for item in obj if item is not None]
        else:
            return obj
    
    def extract_gong_fields(self, record: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Extract specific fields from a Gong call record.
        
        Args:
            record: The record to extract fields from
            
        Returns:
            A tuple containing (extracted_fields_dict, full_data_dict)
        """
        # Get the _airbyte_data if present
        if "_airbyte_data" in record:
            data = record["_airbyte_data"]
        else:
            data = record  # Assume we already have the data
        
        # Ensure data is a dictionary
        if not isinstance(data, dict):
            data = {}
        
        # Extract the required fields
        result: Dict[str, Any] = {}
        
        # Get metadata and content
        metadata = data.get("metaData", {})
        content = data.get("content", {})
        
        # Extract basic metadata
        result["title"] = metadata.get("title")
        result["url"] = metadata.get("url")
        result["purpose"] = metadata.get("purpose")
        
        # Process date from the started timestamp
        if 'started' in metadata:
            started_datetime = datetime.fromisoformat(metadata['started'])
            month = started_datetime.strftime('%B')  # Full month name
            day = str(started_datetime.day)
            year = str(started_datetime.year)
            result["date"] = f"{month} {day}, {year}"
            # Add timestamp for filtering
            result["date_timestamp"] = started_datetime.timestamp()
        
        # Extract brief
        result["brief"] = content.get("brief")
        
        # Extract trackers with speaker-specific data
        trackers = []
        for tracker in content.get("trackers", []):
            if isinstance(tracker, dict):
                tracker_data = {
                    "id": tracker.get("id"),
                    "name": tracker.get("name"),
                    "count": tracker.get("count"),
                    "type": tracker.get("type"),
                    "occurrences": []
                }
                
                # Add speaker-specific occurrences
                for occurrence in tracker.get("occurrences", []):
                    if isinstance(occurrence, dict):
                        tracker_data["occurrences"].append({
                            "startTime": occurrence.get("startTime"),
                            "speakerId": occurrence.get("speakerId")
                        })
                
                if tracker_data["name"]:  # Only add if there's a name
                    trackers.append(tracker_data)
        result["trackers"] = trackers
        
        # Process outline with additional fields
        outline = []
        if content.get("outline"):
            for section in content.get("outline", []):
                if isinstance(section, dict):
                    section_text = section.get("section", "")
                    start_time = section.get("startTime", "")
                    duration = section.get("duration", "")
                    items = section.get("items", [])
                    item_texts = [item.get("text", "") for item in items]
                    if section_text and item_texts:
                        outline.append({
                            "section": section_text,
                            "startTime": start_time,
                            "duration": duration,
                            "items": item_texts
                        })
        result["outline"] = outline
        
        # Process highlights
        highlights = []
        if content.get("highlights"):
            for highlight in content.get("highlights", []):
                if isinstance(highlight, dict):
                    title = highlight.get("title", "")
                    items = highlight.get("items", [])
                    item_texts = [item.get("text", "") for item in items]
                    if title and item_texts:
                        highlights.append({
                            "title": title,
                            "items": item_texts
                        })
        result["highlights"] = highlights
        
        # Process key points
        key_points = []
        if content.get("keyPoints"):
            for point in content.get("keyPoints", []):
                if isinstance(point, dict) and "text" in point:
                    key_points.append(point.get("text"))
        result["keyPoints"] = key_points
        
        # Process topics
        topics = []
        if content.get("topics"):
            for topic in content.get("topics", []):
                if isinstance(topic, dict):
                    # Extract both name and duration if available
                    topic_data = {
                        "name": topic.get("name", ""),
                        "duration": topic.get("duration", "")
                    }
                    if topic_data["name"]:  # Only add if there's a name
                        topics.append(topic_data)
        result["topics"] = topics
        
        # Process questions
        questions = []
        if content.get("questions"):
            for question in content.get("questions", []):
                if isinstance(question, dict):
                    question_data = {
                        "text": question.get("text", ""),
                        "speaker": question.get("speaker", ""),
                        "timestamp": question.get("timestamp", "")
                    }
                    if question_data["text"]:  # Only add if there's question text
                        questions.append(question_data)
        result["questions"] = questions
        
        # Process action items
        action_items = []
        # First check pointsOfInterest
        points_of_interest = content.get("pointsOfInterest", {})
        if points_of_interest.get("actionItems"):
            for item in points_of_interest.get("actionItems", []):
                if isinstance(item, dict) and "text" in item:
                    action_items.append(item.get("text"))
        
        # Also check for "Next steps" in highlights if no action items found
        if not action_items:
            for highlight in content.get("highlights", []):
                if highlight.get("title", "").lower() == "next steps":
                    for item in highlight.get("items", []):
                        if isinstance(item, dict) and "text" in item:
                            action_items.append(item.get("text"))
                    break
        
        result["actionItems"] = action_items
        
        # Process parties with more details
        parties = []
        for party in data.get("parties", []):
            if party.get("name"):
                parties.append({
                    "name": party.get("name"),
                    "role": party.get("role"),
                    "email": party.get("emailAddress"),
                    "affiliation": party.get("affiliation"),
                    "title": party.get("title"),
                    "id": party.get("id")  # Make sure we're extracting the ID
                })
        result["parties"] = parties
        
        # Add participant grouping
        tellius = []
        non_tellius = []
        for party in parties:
            participant = {
                "name": party["name"],
                "id": party["id"],
            }
            if party.get("affiliation") == "Internal":
                tellius.append(participant)
            else:
                non_tellius.append(participant)

        result["participants"] = {
            "tellius": tellius,
            "nonTellius": non_tellius
        }
        
        # Remove any null values from the result
        cleaned_result = self.remove_nulls(result)
        
        return cleaned_result, data
    
    def create_speaker_keyword_mapping(self, record: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, int]]]:
        """Create mappings of speakers to their keyword usage and keywords to their speaker usage.
        
        Args:
            record: The Gong call record
            
        Returns:
            Tuple of (speaker_to_keywords, keyword_to_speakers) dictionaries
        """
        # Get the data
        if "_airbyte_data" in record:
            data = record["_airbyte_data"]
        else:
            data = record
        
        # Create speaker ID to name mapping
        speaker_map = {}
        for party in data.get("parties", []):
            if party.get("speakerId") and party.get("name"):
                speaker_map[party["speakerId"]] = party["name"]
        
        # Initialize mappings
        speaker_keywords = {}
        keyword_speakers = {}
        
        # Process trackers
        content = data.get("content", {})
        for tracker in content.get("trackers", []):
            if isinstance(tracker, dict):
                keyword_name = tracker.get("name", "")
                if not keyword_name:
                    continue
                    
                # Initialize keyword in keyword_speakers mapping
                if keyword_name not in keyword_speakers:
                    keyword_speakers[keyword_name] = {}
                    
                # Process each occurrence
                for occurrence in tracker.get("occurrences", []):
                    if isinstance(occurrence, dict):
                        speaker_id = occurrence.get("speakerId")
                        if speaker_id and speaker_id in speaker_map:
                            speaker_name = speaker_map[speaker_id]
                            
                            # Update speaker_keywords mapping
                            if speaker_name not in speaker_keywords:
                                speaker_keywords[speaker_name] = {}
                            
                            if keyword_name not in speaker_keywords[speaker_name]:
                                speaker_keywords[speaker_name][keyword_name] = 0
                            speaker_keywords[speaker_name][keyword_name] += 1
                            
                            # Update keyword_speakers mapping
                            if speaker_name not in keyword_speakers[keyword_name]:
                                keyword_speakers[keyword_name][speaker_name] = 0
                            keyword_speakers[keyword_name][speaker_name] += 1
        
        return speaker_keywords, keyword_speakers 