#!/bin/sh

echo "Starting ngrok..."

# Set auth token
/usr/local/bin/ngrok authtoken $NGROK_AUTHTOKEN

# Start ngrok in background
# Remove the second 'ngrok http' line; one tunnel per port is sufficient
/usr/local/bin/ngrok http --url=$NGROK_URL 8000 --log=stdout &

echo "Starting FastAPI..."
# Start FastAPI
exec python3 -m uvicorn servidor.main:app --host 0.0.0.0 --port 8000
