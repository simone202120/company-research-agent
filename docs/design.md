# company-research-agent — Design

## Goal
Give the agent a company name; it plans the research, waits for a human to approve or edit the plan,
searches the web in parallel, writes a structured report with sources, and self-reviews it.

Demo story (2 minutes): research the interviewer's company, edit one plan item, approve, watch the
nodes progress, read the report with sources, open the Langfuse trace.

## Graph (LangGraph)
State (typed): company, plan (list of research questions), approved flag, search results per question,
draft report, review feedback, revision count, final report.

```
START -> planner -> human_approval (interrupt) -> researcher (fan-out per question, Send API)
      -> writer -> reviewer -> (needs revision and revisions < max) ? writer : END
```

- planner: 4-6 research questions covering overview, products, tech stack, recent news, competitors.
  Structured output.
- human_approval: `interrupt()` exposing the plan; resume with approved/edited plan.
- researcher: one branch per question; Tavily search (DuckDuckGo fallback), keep top results with URL,
  title, snippet; summarize per question with sources.
- writer: markdown report with sections and inline numbered citations; only facts from sources.
- reviewer: structured verdict (ok / revise + feedback); max 1 revision (configurable).
- Checkpointer: SQLite (`langgraph-checkpoint-sqlite`), thread id per research, resumable.

## API (FastAPI)
- `POST /research` `{company}` → runs until the interrupt, returns `{thread_id, plan}`.
- `POST /research/{thread_id}/approve` `{plan?}` → resumes (background), returns status.
- `GET /research/{thread_id}` → status (`awaiting_approval | running | done | failed`), current node,
  report and sources when done.
- `GET /health`.

## UI (Streamlit)
Input company → shows editable plan → approve → progress by node → rendered report with sources and
download as markdown.

## Observability
Langfuse LangChain callback handler on every graph run: node spans, tool calls, tokens, cost.

## Non-goals
Paid data sources, crawling full websites, scheduling, auth.

## Testing
- Unit (fake LLM + fake search tool): each node in isolation; graph routing (revision loop stops at
  max); interrupt/resume flow with in-memory checkpointer; report citation integrity (every citation
  number maps to a source); API routes with dependency overrides.
- Integration: full graph with fake LLM and SQLite checkpointer on disk, resume after restart.
- LLM: one real run on a well-known company, asserting structure (sections present, >= 5 sources).

## Deliverables
Docker compose (api, ui), README with graph diagram, `docs/architecture.md`, `docs/code-map.md`,
CI green, coverage >= 80%.
