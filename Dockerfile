FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the Streamlit port
EXPOSE 8080

# Run all services using a shell script
CMD ["/bin/bash", "-c", "python -m seller_agent.hotel_agent & python -m seller_agent.flight_agent & python -m seller_agent.itinerary_agent & streamlit run buyer_agent/streamlit_app.py --server.port 8080 --server.address 0.0.0.0"]
