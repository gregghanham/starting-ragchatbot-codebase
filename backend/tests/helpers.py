"""
Shared factory helpers and mock content-block classes.
Importable by test modules directly.
"""
import sys
import os

# Ensure the backend directory is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vector_store import SearchResults


# ---------------------------------------------------------------------------
# Lightweight stand-ins for Anthropic SDK content-block types
# ---------------------------------------------------------------------------

class MockTextBlock:
    """Mimics anthropic.types.TextBlock"""
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class MockToolUseBlock:
    """Mimics anthropic.types.ToolUseBlock"""
    def __init__(self, block_id: str, name: str, input_data: dict):
        self.type = "tool_use"
        self.id = block_id
        self.name = name
        self.input = input_data


class MockMessage:
    """Mimics anthropic.types.Message returned by client.messages.create()"""
    def __init__(self, stop_reason: str, content: list):
        self.stop_reason = stop_reason
        self.content = content


# ---------------------------------------------------------------------------
# SearchResults factories
# ---------------------------------------------------------------------------

def make_search_results(documents=None, metadata=None, distances=None):
    return SearchResults(
        documents=documents or ["Sample lesson content about neural networks."],
        metadata=metadata or [
            {"course_title": "Deep Learning Course", "lesson_number": 1, "chunk_index": 0}
        ],
        distances=distances or [0.35],
    )


def make_empty_results():
    return SearchResults(documents=[], metadata=[], distances=[])


def make_error_results(msg="Search failed"):
    return SearchResults.empty(msg)
