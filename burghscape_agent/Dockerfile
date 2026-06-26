FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget jq \
    && rm -rf /var/lib/apt/lists/*

# Install cloudflared (multi-arch)
RUN arch=$(dpkg --print-architecture) && \
    if [ "$arch" = "amd64" ]; then CF_ARCH="amd64"; \
    elif [ "$arch" = "arm64" ]; then CF_ARCH="arm64"; \
    elif [ "$arch" = "armhf" ]; then CF_ARCH="arm"; \
    else CF_ARCH="amd64"; fi && \
    wget -q "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${CF_ARCH}" \
    -O /usr/local/bin/cloudflared && \
    chmod +x /usr/local/bin/cloudflared

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/app/
COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
