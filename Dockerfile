# =============================================================================
# Dockerfile — Blender Web Service for Render.com
# =============================================================================
# Uses official Blender binary (not building from source — would take hours)
# Provides: scene rendering, file processing, animation rendering via FastAPI
# =============================================================================

FROM python:3.11-slim

LABEL description="Blender Web Service — Render 3D scenes, process .blend files, render animations"
LABEL maintainer="Blender Web Service"

# ── System dependencies ──────────────────────────────────────────────────────
# Blender requires OpenGL, X11 libraries, and various system libs even in
# headless mode. These are the minimal set needed for blender --background.
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    ca-certificates \
    xz-utils \
    # Blender runtime dependencies
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libxi6 \
    libxkbcommon0 \
    libxxf86vm1 \
    libdbus-1-3 \
    libegl1 \
    libxfixes3 \
    libxcb-cursor0 \
    libxcb-keysyms1 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xinput0 \
    libxcb-xkb1 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-sync1 \
    libxcb-util1 \
    libxcb-xv0 \
    libxkbcommon-x11-0 \
    libnss3 \
    libnspr4 \
    && rm -rf /var/lib/apt/lists/*

# ── Install Blender ──────────────────────────────────────────────────────────
# Download official Blender release. This is MUCH faster than building from
# source and is the standard approach for containerized Blender deployments.
ENV BLENDER_VERSION=4.2.0
ENV BLENDER_DOWNLOAD_URL=https://download.blender.org/release/Blender4.2/blender-${BLENDER_VERSION}-linux-x64.tar.xz
ENV BLENDER_INSTALL_DIR=/opt/blender

RUN echo "Downloading Blender ${BLENDER_VERSION}..." \
    && wget --progress=dot:giga "${BLENDER_DOWNLOAD_URL}" -O /tmp/blender.tar.xz \
    && mkdir -p "${BLENDER_INSTALL_DIR}" \
    && tar -xf /tmp/blender.tar.xz -C "${BLENDER_INSTALL_DIR}" --strip-components=1 \
    && rm /tmp/blender.tar.xz \
    # Verify the blender binary exists
    && test -f "${BLENDER_INSTALL_DIR}/blender" \
    && ln -s "${BLENDER_INSTALL_DIR}/blender" /usr/local/bin/blender

# ── Python Dependencies ──────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application Code ─────────────────────────────────────────────────────────
COPY app/ ./app/

# Create temp directory for uploads and outputs
RUN mkdir -p /tmp/blender_service

# ── Runtime Configuration ────────────────────────────────────────────────────
EXPOSE 8000

# Health check — Render uses this to verify the service is alive
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the FastAPI server with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]