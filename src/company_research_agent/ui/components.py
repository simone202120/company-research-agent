"""Rendering helpers for the Streamlit page: timeline, plan editor, report and run metrics."""

from typing import Any, Literal

import streamlit as st

type StepState = Literal["done", "active", "pending", "failed"]

STEPS = [
    ("planner", "Plan the research questions"),
    ("human_approval", "Approve the plan"),
    ("researcher", "Search the web"),
    ("writer", "Write the report"),
    ("reviewer", "Review and finalize"),
]
ICONS: dict[StepState, str] = {
    "done": ":material/check_circle:",
    "active": ":material/progress_activity:",
    "pending": ":material/radio_button_unchecked:",
    "failed": ":material/error:",
}
EXAMPLES = ["Hugging Face", "Mistral AI", "Stripe"]


def timeline(research: dict[str, Any]) -> list[tuple[str, StepState]]:
    """Step labels with their state, derived from the research status and current node."""
    status = research["status"]
    names = [name for name, _ in STEPS]
    if status == "done":
        current = len(STEPS)
    elif status == "awaiting_approval":
        current = names.index("human_approval")
    else:
        node = research.get("current_node") or "human_approval"
        current = names.index(node) if node in names else 0
    states: list[StepState] = []
    for i in range(len(STEPS)):
        if i < current:
            states.append("done")
        elif i == current:
            states.append("failed" if status == "failed" else "active")
        else:
            states.append("pending")
    labels = [label for _, label in STEPS]
    labels[2] += f" ({len(research['plan'])} questions in parallel)"
    return list(zip(labels, states, strict=True))


def render_timeline(research: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown("**Progress**")
        for label, state in timeline(research):
            text = f"**{label}**" if state == "active" else label
            st.markdown(f"{ICONS[state]} {text}")


def edited_plan(plan: list[str]) -> list[str]:
    rows = st.data_editor(
        [{"question": q} for q in plan],
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        column_config={"question": st.column_config.TextColumn("Research question", width="large")},
        key="plan_editor",
    )
    return [q for row in rows if (q := str(row.get("question") or "").strip())]


def render_metrics(research: dict[str, Any]) -> None:
    usage = research.get("usage") or {}
    tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
    latency = research.get("latency_seconds")
    cols = st.columns(5)
    cols[0].metric("Sources", len(research["sources"]))
    cols[1].metric("LLM calls", usage.get("llm_calls", 0))
    cols[2].metric("Tokens", f"{tokens:,}")
    cols[3].metric("Est. cost", f"${usage.get('estimated_cost_usd', 0):.4f}")
    cols[4].metric("Latency", f"{latency:.1f} s" if latency is not None else "n/a")


def report_body(report: str) -> str:
    """The report without its title and Sources section, which the page already shows."""
    body = report.split("\n## Sources\n", 1)[0].strip()
    lines = body.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join("##" + line if line.startswith("## ") else line for line in lines).strip()


def render_report(research: dict[str, Any]) -> None:
    report_col, sources_col = st.columns([3, 1])
    with report_col, st.container(border=True):
        st.markdown(report_body(research["report"]))
    with sources_col, st.container(border=True):
        st.markdown(f"**Sources** :violet-badge[{len(research['sources'])}]")
        for source in research["sources"]:
            st.markdown(
                f"{source['number']}. [{source['title'] or source['url']}]({source['url']})"
            )


def render_raw(research: dict[str, Any]) -> None:
    with st.expander("Raw response", expanded=False):
        st.json(research, expanded=False)
