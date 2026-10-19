# Use the official lightweight Python 3.11 image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Set Playwright browser path for shared system-wide access
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Copy the requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies and Playwright Chromium with OS dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --default-timeout=120 --retries=5 -r requirements.txt \
    && mkdir -p /ms-playwright \
    && playwright install --with-deps chromium \
    && chmod -R 755 /ms-playwright

# Copy the rest of the application files (.env, skippy.db, and resume.md are excluded via .dockerignore)
COPY . .

# Permanently suppress Streamlit telemetry and configure runtime server parameters
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV SKIPPY_WEBHOOK_HOST=0.0.0.0
ENV LITELLM_DISABLE_REDACT_SECRETS=true
ENV LITELLM_LOCAL_MODEL_COST_MAP=True

# Expose Streamlit dashboard and background ingestion webhook
EXPOSE 8501
EXPOSE 8000

# Start the application
CMD ["streamlit", "run", "app.py"]