"""
FastAPI application for the LLM Council system.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

from scheduler import run_council_conversation
from agents import initialize_agents
import storage


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Initialize FastAPI app
app = FastAPI(
    title="LLM Council API",
    description="Multi-agent deliberation system with DAG-based idea exploration",
    version="0.1.0"
)


# Request/Response models
class CouncilChatRequest(BaseModel):
    """Request model for council chat."""
    user_prompt: str


class CouncilChatResponse(BaseModel):
    """Response model for council chat."""
    final_answer: str
    council_summary: str
    conversation_id: str
    total_messages: int
    total_nodes: int
    tokens_used: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    agents_initialized: bool
    total_conversations: int


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize agents on startup."""
    logger.info("Starting LLM Council API...")

    # Initialize agents if not already done
    if not storage.get_all_agents():
        logger.info("Initializing council agents...")
        agents = initialize_agents()
        logger.info(f"Initialized {len(agents)} agents: {[a.agent_id for a in agents]}")
    else:
        logger.info("Agents already initialized")

    logger.info("LLM Council API ready!")


# Endpoints
@app.get("/", response_model=dict)
async def root():
    """Root endpoint with API information."""
    return {
        "message": "LLM Council API",
        "version": "0.1.0",
        "endpoints": {
            "POST /council_chat": "Start a council deliberation",
            "GET /health": "Health check",
            "GET /conversations/{conversation_id}": "Get conversation details",
            "GET /": "This endpoint"
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    agents = storage.get_all_agents()
    conversations = len(storage.conversations)

    return HealthResponse(
        status="healthy",
        agents_initialized=len(agents) > 0,
        total_conversations=conversations
    )


@app.post("/council_chat", response_model=CouncilChatResponse)
async def council_chat(request: CouncilChatRequest):
    """
    Run a council deliberation on the user's prompt.

    This endpoint:
    1. Creates a new conversation
    2. Initializes the overseer
    3. Runs the opening phase (4 agents give initial stances)
    4. Runs the debate phase (iterative multi-turn deliberation)
    5. Synthesizes a final answer

    Returns the final answer, council summary, and metadata.
    """
    try:
        logger.info(f"Received council chat request: {request.user_prompt[:100]}...")

        # Run the council conversation
        result = run_council_conversation(request.user_prompt)

        # Return response
        return CouncilChatResponse(
            final_answer=result["final_answer"],
            council_summary=result["council_summary"],
            conversation_id=result["conversation_id"],
            total_messages=result["total_messages"],
            total_nodes=result["total_nodes"],
            tokens_used=result["tokens_used"]
        )

    except Exception as e:
        logger.error(f"Error in council_chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversations/{conversation_id}", response_model=dict)
async def get_conversation(conversation_id: str):
    """
    Get details about a specific conversation.

    Returns conversation state, messages, and nodes.
    """
    conversation = storage.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = storage.get_messages_for_conversation(conversation_id)
    nodes = storage.get_nodes_for_conversation(conversation_id)

    return {
        "conversation": {
            "id": conversation.id,
            "user_prompt": conversation.user_prompt,
            "mode": conversation.mode.value,
            "phase": conversation.phase.value,
            "current_round": conversation.current_round,
            "used_tokens": conversation.used_tokens,
            "overseer_summary": conversation.overseer_summary
        },
        "statistics": {
            "total_messages": len(messages),
            "total_nodes": len(nodes),
            "active_nodes": len([n for n in nodes if n.status.value == "ACTIVE"]),
            "completed_nodes": len([n for n in nodes if n.status.value == "COMPLETE"]),
            "pruned_nodes": len([n for n in nodes if n.status.value == "PRUNED"])
        },
        "messages": [
            {
                "id": msg.id,
                "speaker": msg.speaker.value,
                "agent_id": msg.agent_id,
                "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in messages[-10:]  # Last 10 messages
        ],
        "nodes": [
            {
                "id": node.id,
                "summary": node.summary,
                "status": node.status.value,
                "score": node.score,
                "created_by": node.created_by_agent_id,
                "parents": node.parents
            }
            for node in nodes
        ]
    }


@app.delete("/reset")
async def reset_all_data():
    """
    Reset all data (for testing/demo purposes).

    WARNING: This deletes all conversations, messages, nodes, and agents.
    """
    storage.clear_all_data()

    # Re-initialize agents
    agents = initialize_agents()

    return {
        "status": "reset_complete",
        "message": "All data cleared and agents re-initialized",
        "agents": [a.agent_id for a in agents]
    }


if __name__ == "__main__":
    import uvicorn

    # Run the server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
