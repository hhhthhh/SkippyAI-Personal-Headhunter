# Use the official lightweight Python 3.11 image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Install system dependencies required for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy the rest of the application files
COPY . .

# Permanently suppress Streamlit telemetry and lock the port
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Expose the standard Streamlit port
EXPOSE 8501

# Start the application
CMD ["streamlit", "run", "app.py"]