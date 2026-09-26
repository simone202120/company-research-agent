# Architecture

## Key design decisions

Each decision lists the trade-off that was accepted.

### Graph state holds plain dicts, not Pydantic models
Search results, findings and sources are `TypedDict`s, so the SQLite checkpointer serializes them
without registering custom types. Pydantic is used only at the edges (LLM structured outputs, API
schemas). Trade-off: no runtime validation inside the state, which is acceptable because every
value is produced by our own nodes.

### Citations are numbered in code, not by the LLM
Researcher branches run in parallel and cite their own results locally (`[1]`, `[2]`). The writer
node numbers sources globally (one number per distinct URL) and rewrites each summary's local
citations before prompting the writer. The reviewer also checks citation integrity
deterministically: an out-of-range citation forces a revision, and if no revision is left the
final report drops the invalid citation. Trade-off: a bit more code, in exchange for a guarantee
that every citation in the final report maps to a listed source.

### The reviewer finalizes the report
The graph ends at the reviewer (`reviewer -> writer | END`): when the verdict is ok or the revision
budget (`MAX_REVISIONS`) is spent, the reviewer renders the final report (body plus a generated
Sources section). Trade-off: the reviewer does two things, but the graph matches the design with
no extra "finalize" node.

### Edited questions keep the company in the search query
A human may edit a question and drop the company name; the researcher prefixes the company when it
is missing, so searches stay on topic.

### Status is derived from the checkpoint
`ResearchRunner` reads the status from the LangGraph checkpoint (interrupt pending, task error,
final report) and keeps only a small in-process registry of active runs. The registry covers the
window between an API call and the first checkpoint of the run and makes approval atomic (a second
approve gets a conflict). Trade-off: status survives restarts, but a run killed mid-way by a
process restart is reported as `failed` ("stopped before completion") rather than resumed, and the
registry assumes a single API process.

### Resume payload is always a dict
The approval interrupt is resumed with `{"plan": [...] | None}`: LangGraph treats
`Command(resume=None)` as "no resume value", so an approval without edits must still send a dict.

### Search falls back provider by provider
`FallbackSearch` tries Tavily (only when `TAVILY_API_KEY` is set) and then DuckDuckGo. A provider
that raises is logged and skipped; one that returns nothing also passes the turn. The search fails
with `SearchError` only when every provider raised, which fails the run. Trade-off: a Tavily outage
silently degrades result quality instead of failing loudly (a warning is logged).

### Synchronous graph with a shared SQLite connection
The graph runs with the synchronous `SqliteSaver` on one connection opened with
`check_same_thread=False`; LangGraph runs the researcher branches in a thread pool and the saver
serializes access with a lock. Trade-off: simpler than the async stack (no `aiosqlite`, plain
functions everywhere), at the cost of blocking a worker thread per active run, which is fine for a
single-user demo.

### Langfuse through the LangChain callback, one trace per research
Tracing is a `CallbackHandler` passed in the run config. Its trace id is derived from the thread id
(`Langfuse.create_trace_id(seed=thread_id)`), so the planning run and the resumed run land in the
same trace and the API can return a link to it without storing anything. Building the link needs
one Langfuse API call (project id, cached after the first success), so only finished researches
get a link, with a 5 s timeout; if Langfuse is unreachable the API returns no link instead of an
error.
`langchain` is a dependency only because `langfuse.langchain` imports it at runtime.

### Approval resumes the run in a FastAPI background task
`POST /research` runs the graph synchronously up to the approval interrupt (one planner call), so
the plan comes back in the response. `POST /research/{id}/approve` claims the thread (409 if it is
not awaiting approval), answers `202`, and resumes the graph in a `BackgroundTasks` job; clients
poll `GET /research/{id}`. Trade-off: no queue or worker process to operate, but runs live inside
the API process (see the status decision above) and a crash loses in-flight runs.

### Missing OpenRouter key fails at startup
`create_llm` raises `ConfigurationError` when `OPENROUTER_API_KEY` is empty, so a misconfigured
deployment fails when the API starts instead of on the first research.

### Usage and latency live in the graph state
Each node adds the token usage of its LLM calls to a `usage` channel with a summing reducer
(parallel researchers included), and the planner, approval and final review record timestamps.
Latency is planning time plus research time, excluding the wait for a human. Keeping them in the
state makes them durable like the rest of the research. Cost is an estimate: tokens times the
configurable `LLM_INPUT_PRICE_PER_MTOK` / `LLM_OUTPUT_PRICE_PER_MTOK`, computed by the API.
Trade-off: it can drift from the real OpenRouter bill (exact per-call cost is visible in Langfuse),
and a structured-output call that fails to parse is not counted (the run fails anyway).
