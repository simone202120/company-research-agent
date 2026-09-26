# One image for both services: the API (default command) and the Streamlit UI.
FROM python:3.12-slim

RUN pip install --no-cache-dir uv==0.9.*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY README.md ./
COPY .streamlit ./.streamlit
COPY src ./src
RUN uv sync --locked --no-dev

RUN useradd --create-home --uid 1000 app && mkdir -p /app/data && chown app:app /app/data
USER app

EXPOSE 8000 8501
CMD ["uvicorn", "company_research_agent.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
