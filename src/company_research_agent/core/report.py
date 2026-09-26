"""Source numbering and citation integrity for the report: every [n] must map to a listed source."""

import re

from company_research_agent.core.state import Finding, Source

CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def number_sources(findings: list[Finding]) -> list[Source]:
    """Assigns one global number per distinct URL, in the order the findings list them."""
    sources: list[Source] = []
    seen: set[str] = set()
    for finding in findings:
        for result in finding["results"]:
            if result["url"] not in seen:
                seen.add(result["url"])
                sources.append(
                    {"number": len(sources) + 1, "title": result["title"], "url": result["url"]}
                )
    return sources


def global_numbers(finding: Finding, sources: list[Source]) -> dict[int, int]:
    """Maps the 1-based result positions of a finding to their global source numbers."""
    by_url = {source["url"]: source["number"] for source in sources}
    return {i: by_url[result["url"]] for i, result in enumerate(finding["results"], start=1)}


def cited_numbers(text: str) -> set[int]:
    return {int(n) for group in CITATION.findall(text) for n in group.split(",")}


def invalid_citations(text: str, source_count: int) -> list[int]:
    return sorted(n for n in cited_numbers(text) if not 1 <= n <= source_count)


def remap_citations(text: str, mapping: dict[int, int]) -> str:
    """Rewrites citations through `mapping`; numbers missing from it are dropped."""

    def replace(match: re.Match[str]) -> str:
        numbers = [mapping.get(int(n)) for n in match.group(1).split(",")]
        return "".join(f"[{n}]" for n in numbers if n is not None)

    return CITATION.sub(replace, text)


def strip_invalid_citations(text: str, source_count: int) -> str:
    return remap_citations(text, {n: n for n in range(1, source_count + 1)})


def render_report(markdown: str, sources: list[Source]) -> str:
    """Final report: the body with invalid citations removed plus a numbered Sources section."""
    body = strip_invalid_citations(markdown, len(sources)).strip()
    lines = [f"{s['number']}. [{s['title'] or s['url']}]({s['url']})" for s in sources]
    return body + "\n\n## Sources\n\n" + ("\n".join(lines) or "No sources found.") + "\n"
