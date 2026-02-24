# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (needed for some Python packages)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create a data directory for ChromaDB (in case it doesn't exist)
RUN mkdir -p data/chroma

# Expose the port Streamlit runs on (Hugging Face Spaces use 7860)
EXPOSE 7860

# Check if chroma database exists, if not, ingest documents
ENTRYPOINT ["sh", "-c", "if [ ! -d \"data/chroma\" ] || [ -z \"$(ls -A data/chroma)\" ]; then python scripts/ingest_documents.py --source-dir ./data --chroma-persist ./data/chroma; fi && streamlit run app/streamlit_app.py --server.port=7860 --server.address=0.0.0.0"]
