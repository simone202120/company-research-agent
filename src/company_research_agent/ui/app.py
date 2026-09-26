"""Streamlit page: pick a company, edit and approve the plan, follow progress, read the report."""

import re
from typing import Any

import streamlit as st

from company_research_agent.config import get_settings
from company_research_agent.ui.api_client import ApiError, ResearchApi
from company_research_agent.ui.components import (
    EXAMPLES,
    edited_plan,
    render_metrics,
    render_raw,
    render_report,
    render_timeline,
)

POLL_SECONDS = 2


def start(api: ResearchApi, company: str) -> None:
    with st.status(f"Planning the research on {company}...", expanded=False):
        try:
            st.session_state.thread_id = api.start(company)["thread_id"]
        except ApiError as exc:
            st.session_state.error = str(exc)
            return
    st.rerun()


def render_start(api: ResearchApi) -> None:
    with st.form("start"):
        company = st.text_input("Company", max_chars=100, placeholder="e.g. Hugging Face")
        submitted = st.form_submit_button("Plan research", type="primary")
    if submitted and company.strip():
        start(api, company.strip())
    st.caption("Or try an example")
    for col, example in zip(st.columns(len(EXAMPLES)), EXAMPLES, strict=True):
        if col.button(example, icon=":material/business:", width="stretch"):
            start(api, example)


def render_plan(api: ResearchApi, research: dict[str, Any]) -> None:
    st.subheader(f"Research plan for {research['company']}")
    st.caption("Edit, add or remove questions (at most 6), then approve to start the research.")
    plan = edited_plan(research["plan"])
    if st.button("Approve plan", type="primary", icon=":material/play_arrow:"):
        if not 1 <= len(plan) <= 6:
            st.warning("Keep between 1 and 6 questions before approving.")
            return
        try:
            api.approve(research["thread_id"], plan)
        except ApiError as exc:
            st.error(str(exc))
            return
        st.rerun()


@st.fragment(run_every=POLL_SECONDS)
def render_progress(api: ResearchApi, thread_id: str) -> None:
    try:
        research = api.get(thread_id)
    except ApiError as exc:
        st.error(str(exc))
        return
    if research["status"] != "running":
        st.rerun()
    st.subheader(f"Researching {research['company']}")
    render_timeline(research)


def render_done(research: dict[str, Any]) -> None:
    st.subheader(f"Report on {research['company']}")
    render_metrics(research)
    actions = st.columns([1, 1, 4])
    slug = re.sub(r"[^a-z0-9]+", "-", research["company"].lower()).strip("-") or "company"
    actions[0].download_button(
        "Download .md",
        research["report"],
        file_name=f"{slug}-research.md",
        mime="text/markdown",
        icon=":material/download:",
    )
    if research.get("trace_url"):
        actions[1].link_button("Langfuse trace", research["trace_url"], icon=":material/timeline:")
    render_report(research)


def render_sidebar(api: ResearchApi) -> None:
    with st.sidebar:
        st.markdown("### Settings")
        st.caption(f"API: `{api.base_url}`")
        if api.healthy():
            st.badge("API online", icon=":material/check:", color="green")
        else:
            st.badge("API offline", icon=":material/cloud_off:", color="red")
        thread_id = st.session_state.get("thread_id")
        if thread_id:
            st.markdown("### Current research")
            st.caption(f"Thread `{thread_id}`")
            if st.button("New research", icon=":material/add:", width="stretch"):
                st.session_state.clear()
                st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Company Research Agent", page_icon=":material/travel_explore:", layout="wide"
    )
    st.title("Company Research Agent")
    st.caption(
        "Plans the research, waits for your approval, searches the web in parallel and writes a "
        "sourced report."
    )
    api = ResearchApi(get_settings().api_url)
    render_sidebar(api)
    if error := st.session_state.pop("error", None):
        st.error(error)

    thread_id = st.session_state.get("thread_id")
    if not thread_id:
        render_start(api)
        return
    try:
        research = api.get(thread_id)
    except ApiError as exc:
        st.error(str(exc))
        return

    status = research["status"]
    if status == "awaiting_approval":
        render_plan(api, research)
    elif status == "running":
        render_progress(api, thread_id)
    elif status == "done":
        render_done(research)
    else:
        st.error(
            "The research failed. Start a new research from the sidebar, or check the API logs. "
            f"Details: {research.get('error') or 'unknown error'}"
        )
        render_timeline(research)
    render_raw(research)


if __name__ == "__main__":
    main()
