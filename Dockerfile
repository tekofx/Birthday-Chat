FROM alpine:latest AS ngrok-builder
RUN apk add --no-cache wget tar
RUN wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz && \
    tar xvzf ngrok-v3-stable-linux-amd64.tgz -C /tmp

FROM python:3.10-alpine
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy ngrok binary
COPY --from=ngrok-builder /tmp/ngrok /usr/local/bin/ngrok
RUN chmod +x /usr/local/bin/ngrok

# Copy entrypoint script
COPY entrypoint.sh .
# CRITICAL: Ensure line endings are LF and script is executable
RUN sed -i 's/\r$//' ./entrypoint.sh && chmod +x ./entrypoint.sh

EXPOSE 8000 4040

ENTRYPOINT ["./entrypoint.sh"]
