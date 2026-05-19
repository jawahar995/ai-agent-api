# ai-agent-api

## Purpose
Python FastAPI + LangGraph data-plane runtime for real-time AI, streaming, and ingestion.

## 1. Technical Framework
- Runtime: Python 3.11+, FastAPI (for HTTP endpoints), Asyncio
- AI and Graph Architecture: LangGraph (stateful workflow automation)
- Media Core Integration: `livekit-agents` suite, Silero VAD, Deepgram plugins
- Vector Mechanics: ChromaDB, `langchain-unstructured`, `tiktoken`

## 2. Directory Structure Blueprint
```text
ai-agent-api/
├── src/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application mounting http/agent processing engines
│   ├── agent.py                # Main LiveKit asynchronous entrypoint and event pipeline
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py            # LangGraph state configurations
│   │   └── workflow.py         # Formulates standard dynamic tool-calling paths
│   ├── services/
│   │   ├── __init__.py
│   │   ├── estimator.py        # Tokenizer tracking logic utilizing tiktoken elements
│   │   ├── ingestion.py        # High-resolution multi-modal document extraction pipeline
│   │   └── url_ingestion.py    # Recursive website content markdown extractor
│   └── tools/
│       ├── __init__.py
│       ├── chroma_rag.py       # Scoped vector search retrieval function
│       ├── sql_connector.py    # Runtime read-only database query abstraction tool
│       └── webhooks.py         # Outbound action notifier utilities
├── requirements.txt
└── .env
```

## Core Responsibilities
- Real-time voice/media execution with LiveKit Agents, Silero VAD, and Deepgram plugins.
- Asynchronous multi-agent graph execution and runtime state management.
- Document and URL ingestion pipelines for multimodal extraction and partitioned vector indexing.
- Pre-flight estimate processing for file/url token and compute metrics.
- Dynamic provider orchestration (OpenAI, Gemini, Bedrock) from tenant profile settings.
- Session-end telemetry aggregation and reporting back to control-plane APIs.

## 3. Runtime Process Flows

### Real-time WebRTC Async Agent Process
- Establishes persistent loop listeners reacting instantly to incoming user media events.
- Reads embedded authorization markers from room metadata records.
- Dynamically constructs client-specific system context wrappers for runtime execution.

### LangGraph Execution Loop
- Uses LangGraph to manage stateful model operations, replacing deprecated synchronous looping tools.
- Coordinates transitions between speech streaming outputs and dynamic tool calling.
- Supports tool orchestration paths including ChromaDB vector searching, read-only SQL querying, and external webhooks.

### High-Resolution Extraction Pipeline
- Parses heterogeneous documents (.pdf, .xlsx, .docx) and website matrices.
- Applies advanced layout analysis to split tabular objects and graphical blocks.
- Summarizes complex structures using lightweight processing models.
- Updates independent target collections in ChromaDB.

### Pre-Flight Estimation Routine
- Runs instant textual analyses on uncompressed files using localized tokenization configurations (tiktoken).
- Calculates raw volume patterns and projected multi-modal processing overhead costs.
- Maps runtime duration footprints before triggering expensive model execution credits.

## 4. Pre-Flight Estimate Workflow
Instead of embedding documents immediately on upload, ingestion is split into an Analyze Phase and an Execute Phase.

```text
[User Uploads File / URL]
         |
         v
[Python Worker: Token and Cost Estimation] (fast and cheap)
         |
         v
[React Frontend: Displays Tokens, Estimated Cost and Processing Time]
         |
    [Get User Approval] -- (Cancel) --> [Abort and Purge File]
         |
      (Approve)
         v
[Python Worker: Execute Full Ingestion and Embeddings]
```

### 4.1 Analyze Phase (No Embedding Calls)
- Read the uploaded file/URL content and normalize text similarly to the ingestion pipeline.
- Chunk content using the same splitter configuration used in execution mode.
- Count tokens per chunk using `tiktoken` (or provider-specific tokenizers).
- Calculate estimated cost/time from token totals and processing profile heuristics.
- Return the estimate payload to the frontend for user confirmation.

### 4.2 Execute Phase (After Approval)
- Trigger full ingestion only after explicit user approval.
- Run extraction, summarization, embedding, and vector write operations.
- Persist ingestion artifacts and emit completion telemetry.

### 4.3 Why This Is Fast and Low Cost
- The estimate phase does not call embedding APIs or summary model inference.
- Tokenization and chunk simulation are local compute operations.
- Result: near-instant estimation, zero model quota usage, and no embedding cost during pre-flight.

## Interfaces
- Inbound from ai-agent-app-api for estimate and ingestion orchestration.
- Runtime interaction with LiveKit media server cluster for real-time session handling.
- Local vector persistence in tenant-isolated ChromaDB directories.
- Outbound telemetry callback to ai-agent-app-api.

## Does Not Own
- Tenant dashboard UI rendering.
- Primary account/subscription database state updates.

## Primary Workspace Paths
- ai-agent-api/main.py
- ai-agent-api/services/agent_service.py
- ai-agent-api/services/user_service.py
- ai-agent-api/services/launcher.py
- ai-agent-api/routes/admin.py
- ai-agent-api/routes/agent.py
- ai-agent-api/routes/auth.py

## Operational Notes
- Enforce strict tenant isolation for tool loading, vector paths, and context propagation.
- Keep long-running operations asynchronous to preserve low-latency behavior.

---
Owner: Runtime AI Team
Status: Active
Last Updated: 2026-05-15
