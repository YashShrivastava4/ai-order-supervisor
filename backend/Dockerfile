FROM python:3.12-slim

WORKDIR /app

# curl/ca-certificates to fetch the Temporal CLI, tar to unpack it
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install the Temporal CLI (single binary, gives us `temporal server start-dev`).
# Detects amd64/arm64 so this works regardless of the build machine's architecture.
RUN ARCH=$(dpkg --print-architecture) \
    && curl -sSL "https://temporal.download/cli/archive/latest?platform=linux&arch=${ARCH}" -o /tmp/temporal-cli.tar.gz \
    && mkdir -p /tmp/temporal-cli \
    && tar -xzf /tmp/temporal-cli.tar.gz -C /tmp/temporal-cli \
    && mv /tmp/temporal-cli/temporal /usr/local/bin/temporal \
    && chmod +x /usr/local/bin/temporal \
    && rm -rf /tmp/temporal-cli /tmp/temporal-cli.tar.gz

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
