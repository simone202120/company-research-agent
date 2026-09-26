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

## UI and demo polish

The UI is what the interviewer sees first: it must look clean and deliberate, not like a default
Streamlit script.

- Custom theme in `.streamlit/config.toml` (`[theme]`: base, primaryColor, backgroundColor,
  secondaryBackgroundColor, textColor, font, baseRadius) using the palette below. No heavy CSS hacks;
  at most a few lines of `st.markdown(..., unsafe_allow_html=True)` for spacing.
- `st.set_page_config` with title, icon and `layout="wide"`; a short header with the project name and
  a one-line description; a sidebar for settings and state.
- Long operations show progress (`st.status` / `st.progress` / `st.spinner`) with human-readable steps.
- Every screen has a useful empty state: 3 clickable example inputs that run a real demo.
- Results are presented, not dumped: containers with borders, badges, metrics, expanders. Raw JSON
  only in a collapsed "Raw response" expander.
- Show cost and speed of each run (tokens, estimated cost, latency) as small metrics: it proves the
  observability story. Link to the Langfuse trace when tracing is enabled.
- Errors are friendly `st.error` messages that say what to do, never stack traces.
- The UI talks to the FastAPI backend over HTTP (backend URL from settings), never imports `core/`.
- Keep it one file per page under `ui/`, small helpers in one module; no duplicated rendering code.

Palette: light base, background `#FAFAF7`, surface `#FFFFFF`, text `#1F2328`, primary `#5B4BDB`.
Layout: company input with example chips (e.g. "Hugging Face", "Mistral AI", "Stripe"). The plan is
shown as an editable list (`st.data_editor`) with an "Approve plan" primary button. While running, a
vertical timeline of graph nodes (planner, approval, research x N, writer, reviewer) with status icons.
The final report is rendered as markdown with a sources panel and a "Download .md" button.
