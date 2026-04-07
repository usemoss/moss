FROM ghcr.io/open-webui/open-webui:main AS base

# The Moss Rust binary (moss_core) needs GLIBC >= 2.38.
# Open WebUI ships on Debian 12 (GLIBC 2.36), so we pull the
# newer libc from Debian testing/trixie.
RUN echo "deb http://deb.debian.org/debian trixie main" > /etc/apt/sources.list.d/trixie.list \
    && apt-get update -qq \
    && apt-get install -y -qq -t trixie libc6 libc-bin libstdc++6 \
    && rm /etc/apt/sources.list.d/trixie.list \
    && apt-get update -qq \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "inferedge-moss>=1.0.0b18"
