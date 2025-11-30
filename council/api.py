"""
FastAPI API for the LLM Council system.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from council.scheduler import run_council_conversation

app = FastAPI(
    title="LLM Council API",
    description="A multi-agent deliberation system where LLM council members debate and explore ideas",
    version="0.1.0"
)


class CouncilChatRequest(BaseModel):
    """Request body for /council_chat endpoint."""
    user_prompt: str


class CouncilChatResponse(BaseModel):
    """Response body for /council_chat endpoint."""
    final_answer: str
    council_summary: str


@app.post("/council_chat", response_model=CouncilChatResponse)
def council_chat(request: CouncilChatRequest) -> CouncilChatResponse:
    """
    Run a complete council deliberation on the user's prompt.
    
    This endpoint:
    1. Creates a new ConversationState
    2. Initializes the overseer
    3. Runs the opening phase (each agent provides initial stance)
    4. Runs the debate phase (agents discuss and refine ideas)
    5. Runs overseer synthesis
    6. Returns the final answer and council summary
    
    Args:
        request: The request containing the user's prompt
        
    Returns:
        CouncilChatResponse with final_answer and council_summary
    """
    if not request.user_prompt or not request.user_prompt.strip():
        raise HTTPException(status_code=400, detail="user_prompt cannot be empty")
    
    result = run_council_conversation(request.user_prompt)
    
    return CouncilChatResponse(
        final_answer=result.get("final_answer", ""),
        council_summary=result.get("council_summary", "")
    )


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
