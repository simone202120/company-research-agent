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
