# CI-tested, local-only demonstration container. NOT a public production release.
FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
WORKDIR /opt/kuodra

# Separate dependency layer, without copying any owner-provided originals.
COPY requirements-ui.txt .
RUN python -m pip install --no-cache-dir -r requirements-ui.txt

# Python/checked-in public evidence only. Never COPY the repo wholesale.
COPY proofinvest/*.py ./proofinvest/
COPY disclosure_lightning/*.py ./disclosure_lightning/
COPY fixtures/*.json ./fixtures/
COPY docs/evidence/*.json ./docs/evidence/
COPY streamlit_app.py .

USER 10001:10001
EXPOSE 8501
CMD ["python", "-B", "-m", "streamlit", "run", "streamlit_app.py", "--server.address=127.0.0.1", "--server.port=8501", "--server.headless=true", "--server.enableCORS=true", "--server.enableXsrfProtection=true", "--browser.gatherUsageStats=false"]
