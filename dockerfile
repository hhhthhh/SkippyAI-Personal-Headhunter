# Use the official lightweight Python 3.11 image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser and all required system dependencies automatically
RUN playwright install --with-deps chromium

# Copy the rest of the application files (Make sure skippy.db is in .dockerignore!)
COPY . .

# Permanently suppress Streamlit telemetry and lock the port
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Expose the standard Streamlit port
EXPOSE 8501

# Start the application
CMD ["streamlit", "run", "app.py"]