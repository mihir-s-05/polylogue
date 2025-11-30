# LLM Council

A multi-agent deliberation system where several LLM "council members" debate and explore ideas as nodes in a DAG, orchestrated by an "overseer" LLM.

## Installation

```bash
pip install -e .
```

## Usage

### API Server

Start the FastAPI server:

```bash
uvicorn council.api:app --host 0.0.0.0 --port 8000
```

Then make a POST request:

```bash
curl -X POST "http://localhost:8000/council_chat" \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "What is the best approach for building a sustainable city?"}'
```

### CLI

Run a council conversation from the command line:

```bash
python -m council.cli "What are the benefits of remote work?"
```

Or with JSON output:

```bash
python -m council.cli "What are the benefits of remote work?" --json
```

## Architecture

- **council/models.py**: Data models (TranscriptMessage, IdeaNode, AgentState, ConversationState)
- **council/registries.py**: In-memory storage for all entities
- **council/llm_helpers.py**: LLM and embedding stub functions (replace with real OpenAI calls)
- **council/overseer.py**: Overseer logic for orchestrating deliberation
- **council/agents.py**: Agent personas and prompt builders
- **council/dag.py**: DAG/node management for idea exploration
- **council/scheduler.py**: Turn management and phase orchestration
- **council/api.py**: FastAPI endpoints
- **council/cli.py**: CLI entrypoint

## Development

Install with development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```
