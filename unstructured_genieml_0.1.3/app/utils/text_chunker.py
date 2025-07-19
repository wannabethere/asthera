"""
Utility functions for chunking text documents
"""

from typing import List


def chunk_document(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """
    Split text into overlapping chunks of roughly equal size.

    Args:
        text: Text to split into chunks
        chunk_size: Size of chunks in characters
        chunk_overlap: Overlap between chunks in characters

    Returns:
        List of text chunks
    """
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        # Find the end of this chunk
        end = start + chunk_size

        # If we're at the end of the text, just use the remainder
        if end >= len(text):
            chunks.append(text[start:])
            break

        # Try to find a natural break point (newline or period)
        # Look backward from the computed end to find a good break point
        natural_break = end

        # Search in the last 20% of the chunk for a paragraph break
        search_start = max(end - int(chunk_size * 0.2), start)

        # Try to find paragraph break first
        last_paragraph = text.rfind("\n\n", search_start, end)
        if last_paragraph > search_start:
            natural_break = last_paragraph + 2  # Include the newlines
        else:
            # If no paragraph break, try to find a single newline
            last_newline = text.rfind("\n", search_start, end)
            if last_newline > search_start:
                natural_break = last_newline + 1  # Include the newline
            else:
                # If no newline, try to find a sentence end
                last_period = text.rfind(". ", search_start, end)
                if last_period > search_start:
                    natural_break = last_period + 2  # Include the period and space

        # Add this chunk to our list
        chunks.append(text[start:natural_break])

        # Start the next chunk, accounting for overlap
        start = natural_break - chunk_overlap
        if start < 0:
            start = 0

    return chunks