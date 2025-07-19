#!/usr/bin/env python3
import json
import re
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from ..stats.base import IStatsGenerator

# Configure logging
logger = logging.getLogger(__name__)

class GongStatsGenerator(IStatsGenerator):
    """
    Generates statistics from Gong call data.
    Adapted from the original stats_extraction.py implementation.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Gong stats generator.
        
        Args:
            config: Optional configuration parameters
        """
        self.config = config or {}
    
    def generate_stats(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate statistics from Gong call documents.
        
        Args:
            documents: List of Gong call documents
            
        Returns:
            List of statistics records
        """
        debug_mode = False
        # Check if debug mode is enabled in any of the documents' metadata
        for doc in documents:
            metadata = doc.get("metadata", {})
            if metadata.get("debug", False):
                debug_mode = True
                break
        
        logger.info(f"Starting stats generation for {len(documents)} documents")
        if debug_mode:
            logger.debug(f"Stats generator config: {self.config}")
        
        stats_records = []
        
        for doc in documents:
            call_id = doc.get("call_id") or doc.get("document_id")
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            
            if debug_mode:
                logger.debug(f"Generating stats for call {call_id}")
            
            # Extract participants
            participants = self._extract_participants(content)
            
            # Extract action items
            action_items = self._extract_action_items(content)
            
            # Extract and count trackers/keywords
            trackers, tracker_mentions = self._extract_trackers(content, participants)
            
            # Get question count from metadata
            question_count = metadata.get("question_count", 0)
            
            # Create stats record
            stats_record = {
                "call_id": call_id,
                "title": metadata.get("title", ""),
                "date": metadata.get("date", ""),
                "date_timestamp": metadata.get("date_timestamp", 0),
                "url": metadata.get("url", ""),
                "participants": participants,
                "action_items": action_items,
                "trackers": trackers,
                "question_count": question_count,
                "action_item_count": len(action_items),
                "participant_count": len(participants),
                "tracker_count": len(trackers),
                "tracker_mentions": tracker_mentions
            }
            
            stats_records.append(stats_record)
            
            if debug_mode:
                logger.debug(f"Generated stats for call {call_id}")
                logger.debug(f"GONG STATS OUTPUT: {json.dumps(stats_record, indent=2, default=str)}")
        
        logger.info(f"Stats generation completed. Generated {len(stats_records)} stats records.")
        return stats_records
    
    def _extract_participants(self, content: str) -> List[Dict[str, Any]]:
        """Extract participants from content."""
        participants = []
        
        # Extract participants section from content
        participants_section = re.search(r"Participants:(.*?)(?:\n\n\n|$)", content, re.DOTALL)
        if participants_section:
            participants_text = participants_section.group(1)
            # Extract each participant line
            for line in participants_text.strip().split('\n'):
                if line.strip().startswith('-'):
                    # Parse the ID first
                    id_match = re.search(r'\[id:(.*?)\]', line)
                    speaker_id = id_match.group(1) if id_match else f"user_{len(participants)}"
                    
                    # Remove the ID part from the line for cleaner parsing of other parts
                    line_without_id = line.replace(f"[id:{speaker_id}]", "") if id_match else line
                    
                    # Parse the participant line
                    parts = line_without_id.strip('- ').split(' - ', 1)
                    name_part = parts[0]
                    email = parts[1] if len(parts) > 1 else ""
                    
                    # Initialize default values
                    title = ""
                    role = ""
                    affiliation = "Unknown"
                    is_internal = False
                    
                    # Check for details in parentheses with the semicolon-separated format
                    role_match = re.search(r'(.*?)\s*\((.*?)\)', name_part)
                    if role_match:
                        name = role_match.group(1).strip()
                        details_str = role_match.group(2).strip()
                        
                        # Parse semicolon-separated details
                        details = [detail.strip() for detail in details_str.split(';')]
                        
                        for detail in details:
                            if detail.startswith('title:'):
                                title = detail[6:].strip()
                            elif detail.startswith('role:'):
                                role = detail[5:].strip()
                            elif detail.startswith('affiliation:'):
                                affiliation = detail[12:].strip()
                                is_internal = affiliation == "Internal"
                            elif "Internal" in detail:
                                affiliation = "Internal"
                                is_internal = True
                            elif "External" in detail:
                                affiliation = "External"
                                is_internal = False
                    else:
                        name = name_part.strip()
                    
                    participant = {
                        "id": speaker_id,
                        "name": name,
                        "affiliation": affiliation,
                        "title": title,
                        "is_internal": is_internal,
                        "email": email
                    }
                    
                    participants.append(participant)
        
        # Also check for "Internal participants" and "External participants" sections
        self._extract_internal_external_participants(content, participants)
        
        return participants
    
    def _extract_internal_external_participants(self, content: str, participants: List[Dict[str, Any]]) -> None:
        """Extract internal and external participants and add them to the participants list."""
        # Internal participants
        internal_section = re.search(r"Internal participants:(.*?)(?:\n\n|$)", content, re.DOTALL)
        if internal_section:
            internal_text = internal_section.group(1).strip()
            for line in internal_text.split('\n'):
                if line.strip().startswith('-'):
                    name_part = line.strip('- ').strip()
                    
                    # Extract ID if present
                    id_match = re.search(r'(.*?)\s*\[id:(.*?)\]', name_part)
                    if id_match:
                        name = id_match.group(1).strip()
                        speaker_id = id_match.group(2)
                    else:
                        # Try the other format [id:XXX]
                        id_match = re.search(r'\[id:(.*?)\]', line)
                        if id_match:
                            speaker_id = id_match.group(1)
                            # Remove the ID part to get the name
                            name = line.strip('- ').replace(f"[id:{speaker_id}]", "").strip()
                        else:
                            name = name_part
                            speaker_id = f"user_{len(participants)}"
                    
                    # Add to participants list if not already there by ID
                    if not any(p["id"] == speaker_id for p in participants):
                        participants.append({
                            "id": speaker_id,
                            "name": name,
                            "affiliation": "Internal",
                            "title": "",
                            "is_internal": True,
                            "email": ""
                        })
        
        # External participants
        external_section = re.search(r"External participants:(.*?)(?:\n\n|$)", content, re.DOTALL)
        if external_section:
            external_text = external_section.group(1).strip()
            for line in external_text.split('\n'):
                if line.strip().startswith('-'):
                    name_part = line.strip('- ').strip()
                    
                    # Extract ID if present
                    id_match = re.search(r'(.*?)\s*\[id:(.*?)\]', name_part)
                    if id_match:
                        name = id_match.group(1).strip()
                        speaker_id = id_match.group(2)
                    else:
                        # Try the other format [id:XXX]
                        id_match = re.search(r'\[id:(.*?)\]', line)
                        if id_match:
                            speaker_id = id_match.group(1)
                            # Remove the ID part to get the name
                            name = line.strip('- ').replace(f"[id:{speaker_id}]", "").strip()
                        else:
                            name = name_part
                            speaker_id = f"user_{len(participants)}"
                    
                    # Add to participants list if not already there by ID
                    if not any(p["id"] == speaker_id for p in participants):
                        participants.append({
                            "id": speaker_id,
                            "name": name,
                            "affiliation": "External",
                            "title": "",
                            "is_internal": False,
                            "email": ""
                        })
    
    def _extract_action_items(self, content: str) -> List[str]:
        """Extract action items from content."""
        action_items = []
        
        # Extract action items section
        action_items_section = re.search(r"Action items:(.*?)(?:\n\n|$)", content, re.DOTALL)
        if action_items_section:
            action_items_text = action_items_section.group(1)
            for line in action_items_text.strip().split('\n'):
                if line.strip().startswith(tuple(str(i) + "." for i in range(1, 20))):
                    item_text = line.split('.', 1)[1].strip()
                    action_items.append(item_text)
        
        # Also check "Next steps" section for action items
        if not action_items:
            next_steps_section = re.search(r"Next steps:(.*?)(?:\n\n|$)", content, re.DOTALL)
            if next_steps_section:
                next_steps_text = next_steps_section.group(1)
                for line in next_steps_text.strip().split('\n'):
                    if line.strip().startswith(tuple(str(i) + "." for i in range(1, 20))):
                        item_text = line.split('.', 1)[1].strip()
                        action_items.append(item_text)
        
        return action_items
    
    def _extract_trackers(self, content: str, participants: List[Dict[str, Any]]) -> tuple:
        """Extract trackers/keywords and their mentions from content."""
        trackers = []
        tracker_mentions = []
        
        # Parse trackers from the content field
        keywords_section = re.search(r"Keywords tracked:(.*?)(?:\n\n|$)", content, re.DOTALL)
        if keywords_section:
            keywords_text = keywords_section.group(1)
            current_tracker = None
            
            for line in keywords_text.strip().split('\n'):
                line = line.strip()
                
                # New tracker
                if line.startswith(tuple(str(i) + "." for i in range(1, 100))):
                    if '(' in line and ')' in line:
                        parts = line.split('.', 1)[1].strip()
                        tracker_info = parts.split('(', 1)
                        tracker_name = tracker_info[0].strip()
                        count_text = re.search(r'mentioned (\d+) times', parts)
                        count = int(count_text.group(1)) if count_text else 0
                        
                        current_tracker = {
                            "id": f"tracker_{len(trackers)}",
                            "name": tracker_name,
                            "count": count,
                            "type": "keyword"
                        }
                        trackers.append(current_tracker)
                
                # Speaker mention for current tracker
                elif line.startswith('-') and current_tracker:
                    if ':' in line:
                        speaker_info = line.strip('- ').split(':', 1)
                        speaker_name = speaker_info[0].strip()
                        count_text = re.search(r'(\d+) times', speaker_info[1])
                        count = int(count_text.group(1)) if count_text else 0
                        
                        # Find if this speaker is in our participants list by name
                        speaker_data = next((p for p in participants if p["name"] == speaker_name), None)
                        
                        # If speaker not found, create a placeholder
                        if not speaker_data:
                            speaker_data = {
                                "id": f"user_{len(participants)}",
                                "name": speaker_name,
                                "affiliation": "Unknown",
                                "title": "",
                                "is_internal": False
                            }
                        
                        if count > 0:
                            for _ in range(count):
                                tracker_mentions.append({
                                    "tracker_name": current_tracker["name"],
                                    "speaker_id": speaker_data["id"],
                                    "speaker_name": speaker_data["name"],
                                    "speaker_affiliation": speaker_data.get("affiliation", "Unknown"),
                                    "speaker_title": speaker_data.get("title", ""),
                                    "is_internal": speaker_data.get("is_internal", False),
                                    "start_time": 0,  # We don't have this information in the formatted content
                                    "associated_topic": None  # We don't have this information in the formatted content
                                })
        
        return trackers, tracker_mentions
    
    def _extract_topics(self, content: str) -> List[Dict[str, Any]]:
        """Extract topics from content."""
        topics = []
        
        topics_section = re.search(r"Topics discussed:(.*?)(?:\n\n|$)", content, re.DOTALL)
        if topics_section:
            topics_text = topics_section.group(1).strip()
            topic_matches = re.findall(r'([^,()]+)\s*\((\d+)\)', topics_text)
            for topic_name, duration in topic_matches:
                topics.append({
                    "name": topic_name.strip(),
                    "duration": int(duration)
                })
        
        return topics
    
    def _extract_talk_time(self, content: str) -> float:
        """Extract total talk time from content."""
        total_talk_time_seconds = 0
        outline_sections = re.findall(r'\u2022\s+.*?\(starts at (\d+\.\d+), duration: (\d+\.\d+)\):', content, re.DOTALL)
        for _, duration in outline_sections:
            try:
                total_talk_time_seconds += float(duration)
            except (ValueError, TypeError):
                pass
        
        return total_talk_time_seconds
    
    def _extract_interaction_data(self, metadata: Dict[str, Any], participants: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract interaction data from metadata."""
        interaction_data = {
            "speakers": [],
            "stats": []
        }
        
        # Extract interaction data from metadata if available
        interaction_speakers = metadata.get("interaction_speakers", [])
        interaction_stats = metadata.get("interaction_stats", [])
        
        if interaction_speakers:
            # Map speaker IDs to participant data for additional info
            speaker_id_to_participant = {p["id"]: p for p in participants}
            
            # Process each speaker
            processed_speakers = []
            for speaker in interaction_speakers:
                speaker_id = speaker.get("id")
                talk_time = speaker.get("talkTime", 0)
                
                # Get additional info from participants if available
                participant_data = speaker_id_to_participant.get(speaker_id, {})
                speaker_name = participant_data.get("name", "Unknown Speaker")
                is_internal = participant_data.get("is_internal", False)
                
                processed_speakers.append({
                    "id": speaker_id,
                    "name": speaker_name,
                    "talk_time": talk_time,
                    "is_internal": is_internal
                })
            
            # Update interaction speakers
            interaction_data["speakers"] = processed_speakers
        
        if interaction_stats:
            # Process each stat
            processed_stats = []
            for stat in interaction_stats:
                stat_name = stat.get("name", "")
                stat_value = stat.get("value", 0)
                
                if stat_name:
                    processed_stats.append({
                        "name": stat_name,
                        "value": stat_value
                    })
            
            # Update interaction stats
            interaction_data["stats"] = processed_stats
        
        return interaction_data 