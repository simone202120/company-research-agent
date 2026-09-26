# company-research-agent

LangGraph agent that researches a company on the web and writes a sourced report, with a human-in-the-loop approval step on the research plan.

> Status: work in progress. See [`docs/design.md`](docs/design.md) for scope and design.

## Development

This project is developed with an AI-assisted workflow using [Claude Code](https://claude.com/claude-code):
project context in [`CLAUDE.md`](CLAUDE.md), specialized agents, slash commands and hooks in
[`.claude/`](.claude/) (auto-formatting, secret protection, session context).

```bash
uv sync
uv run pytest
```

## License

MIT
