from company_research_agent.core.report import (
    cited_numbers,
    global_numbers,
    invalid_citations,
    number_sources,
    remap_citations,
    render_report,
    strip_invalid_citations,
)
from company_research_agent.core.state import Finding


def finding(question: str, *urls: str) -> Finding:
    return {
        "question": question,
        "summary": "",
        "results": [{"title": u, "url": u, "snippet": ""} for u in urls],
    }


def test_number_sources_deduplicates_urls_in_order() -> None:
    sources = number_sources([finding("a", "u1", "u2"), finding("b", "u2", "u3")])
    assert [(s["number"], s["url"]) for s in sources] == [(1, "u1"), (2, "u2"), (3, "u3")]


def test_global_numbers_maps_local_positions_to_source_numbers() -> None:
    findings = [finding("a", "u1", "u2"), finding("b", "u2", "u3")]
    assert global_numbers(findings[1], number_sources(findings)) == {1: 2, 2: 3}


def test_cited_numbers_reads_single_and_grouped_citations() -> None:
    assert cited_numbers("a [1] b [2, 3] c [10] [link](http://x)") == {1, 2, 3, 10}


def test_invalid_citations_reports_numbers_outside_sources() -> None:
    assert invalid_citations("a [1] b [0] c [4, 2]", source_count=3) == [0, 4]


def test_remap_citations_rewrites_and_drops_unknown_numbers() -> None:
    assert remap_citations("x [1] y [2, 3] z [9]", {1: 5, 3: 7}) == "x [5] y [7] z "


def test_strip_invalid_citations_keeps_valid_ones() -> None:
    assert strip_invalid_citations("a [1][4] b [2, 5]", source_count=2) == "a [1] b [2]"


def test_render_report_appends_numbered_sources_and_strips_invalid_citations() -> None:
    sources = number_sources([finding("a", "https://a.test")])
    report = render_report("# R\n\nFact [1] and [2].", sources)
    assert "Fact [1] and ." in report
    assert report.endswith("## Sources\n\n1. [https://a.test](https://a.test)\n")
    assert invalid_citations(report, len(sources)) == []


def test_render_report_without_sources_says_so() -> None:
    assert "No sources found." in render_report("# R", [])
