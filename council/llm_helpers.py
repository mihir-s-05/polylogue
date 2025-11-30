"""
LLM and embedding helper functions.
Contains stub implementations that will be replaced with real OpenAI calls later.
"""

import json
import math
from council.models import IdeaNode
from council import registries


def call_llm(role: str, prompt: str, max_tokens: int = 500) -> str:
    """
    Stub function for LLM calls. Returns dummy responses based on role.
    
    TODO: Replace with real OpenAI API calls.
    
    Args:
        role: The role of the caller (e.g., "overseer_init", "overseer_update", 
              "overseer_synthesis", "agent_opening", "agent_debate")
        prompt: The prompt to send to the LLM
        max_tokens: Maximum tokens for the response
        
    Returns:
        A dummy response string with a [COUNCIL_STATE] footer for agent roles
    """
    # Generate role-specific dummy responses
    if role == "overseer_init":
        return "Initial council summary: Analyzing the user's request to facilitate productive deliberation among council members."
    
    elif role == "overseer_update":
        return "Updated summary: The council is making progress. Key themes are emerging from the discussion."
    
    elif role == "overseer_synthesis":
        return json.dumps({
            "final_answer": "After careful deliberation, the council has reached a synthesized conclusion that considers multiple perspectives including innovation, risk management, and practical implementation.",
            "council_summary": "The council engaged in productive debate, with members presenting diverse viewpoints. Key areas of agreement and disagreement were identified and resolved through collaborative discussion."
        })
    
    elif role == "agent_opening":
        # Return a dummy opening statement with council footer
        return """Based on my analysis, I propose an initial approach that aligns with my perspective.
        
This is my opening stance on the matter, considering the various factors at play.

[COUNCIL_STATE]
{
    "current_node_id": null,
    "status": "proposing",
    "new_branch_proposals": [{"summary": "Initial proposal based on my persona", "parent_id": null}],
    "votes": {},
    "raise_objection_to": null
}
[/COUNCIL_STATE]"""
    
    elif role == "agent_debate":
        # Return a dummy debate contribution with council footer
        return """I've considered the recent discussion and want to add my perspective.

Building on what has been said, I believe we should consider additional factors.

[COUNCIL_STATE]
{
    "current_node_id": null,
    "status": "contributing",
    "new_branch_proposals": [],
    "votes": {},
    "raise_objection_to": null
}
[/COUNCIL_STATE]"""
    
    else:
        return f"Dummy response for role: {role}"


def get_embedding(text: str) -> list[float]:
    """
    Stub function for generating embeddings. Returns a dummy embedding vector.
    
    TODO: Replace with real OpenAI embeddings API call.
    
    Args:
        text: The text to embed
        
    Returns:
        A dummy 128-dimensional embedding vector
    """
    # Generate a simple deterministic dummy embedding based on text hash
    hash_val = hash(text)
    embedding = []
    for i in range(128):
        # Create somewhat varied values based on text hash
        val = math.sin(hash_val + i) * 0.5 + 0.5
        embedding.append(val)
    return embedding


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        Cosine similarity value between -1 and 1
    """
    if len(vec1) != len(vec2) or len(vec1) == 0:
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)


def similarity_search_nodes(
    query_embedding: list[float], 
    conversation_id: str, 
    top_k: int = 5
) -> list[IdeaNode]:
    """
    Search for similar nodes based on embedding similarity.
    
    Args:
        query_embedding: The query embedding vector
        conversation_id: Filter nodes by conversation
        top_k: Number of top results to return
        
    Returns:
        List of IdeaNodes sorted by similarity (highest first)
    """
    conversation_nodes = registries.get_conversation_nodes(conversation_id)
    
    # Calculate similarities
    node_scores = []
    for node in conversation_nodes:
        if node.embedding:
            similarity = cosine_similarity(query_embedding, node.embedding)
            node_scores.append((node, similarity))
    
    # Sort by similarity (descending) and return top_k
    node_scores.sort(key=lambda x: x[1], reverse=True)
    return [node for node, _ in node_scores[:top_k]]


# RAG Stub Functions - TODO: Implement with real embeddings and search

def search_nodes(query: str, conversation_id: str, k: int = 5) -> list[IdeaNode]:
    """
    Search nodes by query text using embeddings.
    
    TODO: Implement with real embedding-based search.
    
    Args:
        query: Search query text
        conversation_id: Filter by conversation
        k: Number of results to return
        
    Returns:
        List of relevant IdeaNodes
    """
    query_embedding = get_embedding(query)
    return similarity_search_nodes(query_embedding, conversation_id, k)


def search_transcript(query: str, conversation_id: str, k: int = 5) -> list:
    """
    Search transcript messages by query text.
    
    TODO: Implement with real embedding-based search.
    
    Args:
        query: Search query text
        conversation_id: Filter by conversation
        k: Number of results to return
        
    Returns:
        List of relevant TranscriptMessages
    """
    # For MVP, just return recent messages
    all_messages = registries.get_conversation_messages(conversation_id)
    # Sort by timestamp and return last k
    sorted_messages = sorted(all_messages, key=lambda m: m.timestamp, reverse=True)
    return sorted_messages[:k]
