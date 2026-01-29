"""
Data Retrieval Models
Models for agent data retrieval operations (from agents/data/retrieval.py)
"""
from typing import List
from pydantic import BaseModel


class MatchingTableContents(BaseModel):
    """Contents of a matching table including reasoning and columns."""
    chain_of_thought_reasoning: List[str]
    columns: List[str]


class MatchingTable(BaseModel):
    """A matching table with its contents and selection reason."""
    table_name: str
    table_contents: MatchingTableContents
    table_selection_reason: str


class RetrievalResults(BaseModel):
    """Results of the retrieval process."""
    results: List[MatchingTable]
