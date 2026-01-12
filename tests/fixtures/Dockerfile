# Sample Dockerfile for testing (Debian-based)
FROM debian:bookworm-slim

# Install packages for testing
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
CMD ["bash"]
