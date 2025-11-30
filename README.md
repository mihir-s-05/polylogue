# LLM Council - Multi-Agent Deliberation System

An MVP implementation of a multi-agent deliberation system where several LLM "council members" debate and explore ideas as nodes in a DAG (Directed Acyclic Graph), orchestrated by an "overseer" LLM.

## Overview

The LLM Council system enables sophisticated reasoning through multi-agent deliberation:

1. **User submits a question** → The system creates a council conversation
2. **Overseer analyzes** the question and provides initial framing
3. **Opening Phase**: Each of 4 agents provides their initial perspective
4. **Debate Phase**: Agents iteratively contribute, building on ideas, raising objections, proposing branches
5. **Synthesis Phase**: Overseer synthesizes final answer from the deliberation

All ideas are tracked as nodes in a DAG, with similarity detection to prevent duplication and automatic scoring to prioritize promising directions.

## Architecture

### Core Components

- **models.py**: Data models (ConversationState, IdeaNode, AgentState, TranscriptMessage)
- **storage.py**: In-memory data storage (dicts/lists)
- **llm_helpers.py**: LLM and embedding helpers (currently stubs for MVP)
- **agents.py**: Agent personas and prompt building
- **overseer.py**: Overseer logic for managing deliberation
- **dag_manager.py**: DAG node management and similarity detection
- **scheduler.py**: Orchestration logic for phases and turn-taking
- **main.py**: FastAPI HTTP endpoints
- **cli.py**: Command-line interface

### Agent Personas

1. **Bold Innovator**: Creative, risk-taking, paradigm-shifting
2. **Risk-Averse Critic**: Analytical, identifies problems and edge cases
3. **Pragmatic Builder**: Implementation-focused, considers feasibility
4. **Systems Thinker**: Holistic, considers second-order effects

## Installation

```bash
# Clone the repository
cd polylogue

# Install dependencies
pip install -r requirements.txt
```

## Usage

### CLI Mode

Run a single deliberation:

```bash
python cli.py "What are the key considerations for building a scalable web application?"
```

Interactive mode:

```bash
python cli.py --interactive
```

Reset data:

```bash
python cli.py --reset
```

### API Mode

Start the FastAPI server:

```bash
python main.py
```

Or using uvicorn:

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

### API Endpoints

#### POST /council_chat

Start a council deliberation:

```bash
curl -X POST "http://localhost:8000/council_chat" \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "What are the trade-offs between microservices and monolithic architecture?"}'
```

Response:

```json
{
  "final_answer": "...",
  "council_summary": "...",
  "conversation_id": "conv_abc123",
  "total_messages": 15,
  "total_nodes": 8,
  "tokens_used": 3245
}
```

#### GET /conversations/{conversation_id}

Get details about a specific conversation:

```bash
curl "http://localhost:8000/conversations/conv_abc123"
```

#### GET /health

Health check:

```bash
curl "http://localhost:8000/health"
```

#### DELETE /reset

Reset all data (for testing):

```bash
curl -X DELETE "http://localhost:8000/reset"
```

## Data Models

### ConversationState

Tracks overall conversation state:
- `id`, `user_prompt`, `mode`, `phase`
- `overseer_summary` (updated throughout deliberation)
- `active_node_ids`, `priority_node_ids`
- Token budget and usage tracking
- Configuration (max_branches, max_depth, max_debate_rounds)

### IdeaNode

Represents an idea in the DAG:
- `id`, `summary`, `artifact` (full text)
- `parents` (list of parent node IDs)
- `status` (ACTIVE, COMPLETE, PRUNED)
- `score` (for prioritization)
- `embedding` (for similarity detection)
- `equivalent_to` (for deduplication)

### AgentState

Tracks agent state:
- `agent_id`, `persona_description`
- `current_node_id` (the idea they're currently working on)
- `last_spoke_at` (for scheduling)
- `is_active`

### TranscriptMessage

Records all messages:
- `id`, `conversation_id`, `speaker`, `content`
- `agent_id` (if speaker is an agent)
- `footer` (parsed [COUNCIL_STATE] metadata)
- `timestamp`

## Council Footer Format

Agents append structured metadata to their responses:

```json
[COUNCIL_STATE]
{
  "current_node_id": "node_abc123",
  "status": "ACTIVE" | "COMPLETE" | "PRUNED",
  "new_branch_proposals": [
    {"summary": "...", "parent_node_id": "..."}
  ],
  "votes": {"node_id": "COMPLETE"},
  "raise_objection_to": {
    "node_id": "...",
    "strength": 0.8,
    "reason": "..."
  }
}
[/COUNCIL_STATE]
```

## TODOs and Future Enhancements

### TODO 1: Real LLM Integration

Currently using stub functions in `llm_helpers.py`. Replace with real OpenAI calls:

```python
# In llm_helpers.py
import openai

def call_llm(role: str, prompt: str, max_tokens: int = 500) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

def get_embedding(text: str) -> List[float]:
    response = openai.Embedding.create(
        model="text-embedding-ada-002",
        input=text
    )
    return response.data[0].embedding
```

### TODO 2: RAG Implementation

In `scheduler.py`, the debate phase has a placeholder for RAG:

```python
# TODO: RAG - Retrieve relevant snippets based on agent's context
# Current location: scheduler.py:run_debate_phase()

# Implementation approach:
# 1. Extract keywords from agent's current node or last message
# 2. Use search_nodes() and search_transcript() to find relevant context
# 3. Pass retrieved snippets to agent prompt
```

### TODO 3: Enhanced Scheduling

In `scheduler.py:select_next_agent()`, implement more sophisticated scheduling:

- Parse recent messages for `raise_objection_to` fields
- Prioritize agents with strong objections
- Weight agents working on priority nodes more heavily
- Add randomness to avoid strictly round-robin

### TODO 4: Persistent Storage

Replace in-memory storage with database (PostgreSQL, MongoDB, etc.):

- Store conversations, messages, nodes, agents
- Enable conversation history and analytics
- Support multiple concurrent conversations

### TODO 5: Advanced DAG Features

- Automatic pruning of low-scoring branches
- Cycle detection (shouldn't happen but good to check)
- Node merging (beyond equivalence marking)
- Visualization endpoint for DAG structure

### TODO 6: Logging and Monitoring

Add structured logging for:
- Performance metrics (response times, token usage)
- Agent behavior patterns
- Node evolution over time
- Quality metrics for final answers

## Development

### Running Tests

```bash
# TODO: Add pytest tests
pytest tests/
```

### Code Structure

```
polylogue/
├── models.py           # Data models
├── storage.py          # In-memory storage
├── llm_helpers.py      # LLM/embedding helpers (stub)
├── agents.py           # Agent personas and prompts
├── overseer.py         # Overseer logic
├── dag_manager.py      # DAG node management
├── scheduler.py        # Orchestration and phases
├── main.py             # FastAPI app
├── cli.py              # CLI entrypoint
└── requirements.txt    # Dependencies
```

## Configuration

Current MVP configuration (in `scheduler.py:run_council_conversation()`):

```python
global_token_budget = 5000    # Total tokens for deliberation
max_branches = 5              # Max priority nodes to track
max_depth = 4                 # Max DAG depth
max_debate_rounds = 3         # Max debate rounds
```

Adjust these values based on your use case.

## Example Output

```
============================================================
NEW COUNCIL CONVERSATION: conv_a1b2c3d4
User prompt: What are the key considerations for building a scalable web application?
============================================================

=== Starting OPENING phase ===

Agent agent_bold_innovator providing opening statement (1/4)...
  Created node: node_opening_1

Agent agent_risk_critic providing opening statement (2/4)...
  Created node: node_opening_2

Agent agent_pragmatic_builder providing opening statement (3/4)...
  Created node: node_opening_3

Agent agent_systems_thinker providing opening statement (4/4)...
  Created node: node_opening_4

=== OPENING phase complete ===

=== DAG Structure ===
Level 0:
  node_opening_1: Here is my opening stance... [ACTIVE] (score: 0.65)
  node_opening_2: As an agent with my perspective... [ACTIVE] (score: 0.58)
  ...

=== Starting DEBATE phase ===

--- Debate Turn 1 (Round 1) ---
Selected agent: agent_bold_innovator
  ...

=== DEBATE phase complete after 12 turns ===

=== Running SYNTHESIS ===

FINAL ANSWER:
Building a scalable web application requires careful consideration of...

COUNCIL SUMMARY:
The council engaged in thoughtful debate, exploring multiple angles...
============================================================
```

## License

MIT License (or your preferred license)

## Contributing

Contributions welcome! Please open an issue or PR.

## Contact

For questions or feedback, please open an issue on GitHub.
