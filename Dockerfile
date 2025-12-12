# FROM ubuntu:24.04

# ENV DEBIAN_FRONTEND=noninteractive

# # =============================================================================
# # Install build dependencies
# # =============================================================================
# RUN apt-get update && apt-get install -y \
#     python3-pip git sudo \
#     build-essential cmake ninja-build \
#     libcurl4-openssl-dev libssl-dev libevent-dev zlib1g-dev \
#     ccache \
#     findutils \
#     && rm -rf /var/lib/apt/lists/*

# # =============================================================================
# # Configure ccache for path-agnostic caching
# # CCACHE_BASEDIR and CCACHE_NOHASHDIR ensure cache hits even when
# # file paths differ slightly between builds
# # =============================================================================
# ENV CCACHE_DIR=/var/cache/ccache
# ENV CCACHE_MAXSIZE=5G
# ENV CCACHE_COMPRESS=1
# ENV CCACHE_BASEDIR=/
# ENV CCACHE_NOHASHDIR=1
# ENV PATH="/usr/lib/ccache:$PATH"

# RUN mkdir -p /var/cache/ccache && \
#     chmod 777 /var/cache/ccache && \
#     ccache --max-size=5G && \
#     ccache --set-config=compression=true

# # =============================================================================
# # Install evaluation framework
# # =============================================================================
# COPY . /evaluation
# WORKDIR /evaluation
# RUN pip install --break-system-packages -e .

# # =============================================================================
# # Create ubuntu user
# # =============================================================================
# # RUN useradd -m -s /bin/bash -u 1000 ubuntu 2>/dev/null || true

# # =============================================================================
# # Configure git globally
# # =============================================================================
# RUN git config --system user.email "agent@evaluation.local" && \
#     git config --system user.name "Evaluation Agent" && \
#     git config --system --add safe.directory '*'

# # =============================================================================
# # Clone repository to AGENT'S workspace (not secure_repo)
# # This is the key change - we build where the agent will work
# # =============================================================================
# WORKDIR /home/ubuntu

# RUN git clone --recurse-submodules \
#     https://github.com/transmission/transmission.git \
#     /home/ubuntu/repo

# # =============================================================================
# # Build at HEAD in the agent's workspace
# # CMake will hardcode paths as /home/ubuntu/repo - exactly what we want!
# # =============================================================================
# WORKDIR /home/ubuntu/repo

# RUN mkdir -p build && cd build && \
#     cmake -G Ninja \
#         -DCMAKE_BUILD_TYPE=RelWithDebInfo \
#         -DENABLE_GTK=OFF \
#         -DENABLE_QT=OFF \
#         -DENABLE_MAC=OFF \
#         -DENABLE_TESTS=ON \
#         -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
#         -DCMAKE_C_COMPILER_LAUNCHER=ccache \
#         .. && \
#     ninja -j$(nproc) && \
#     echo "Build complete. ccache stats:" && \
#     ccache --show-stats

# # =============================================================================
# # Verify build artifacts
# # =============================================================================
# RUN echo "=== Verifying build artifacts ===" && \
#     echo "Ninja build files:" && \
#     ls -la /home/ubuntu/repo/build/*.ninja && \
#     echo "" && \
#     echo "Sample object files:" && \
#     find /home/ubuntu/repo/build -name "*.o" | head -5 && \
#     echo "" && \
#     echo "Total object file count:" && \
#     find /home/ubuntu/repo/build -name "*.o" | wc -l

# # =============================================================================
# # Move .git to secure location for archive operations
# # The agent won't have access to this - it's locked to root only
# # =============================================================================
# RUN mv /home/ubuntu/repo/.git /evaluation/secure_git && \
#     chown -R root:root /evaluation/secure_git && \
#     chmod -R 700 /evaluation/secure_git

# # Also remove .git from submodules (agent can't access these either)
# RUN find /home/ubuntu/repo -name ".git" -type d -exec rm -rf {} + 2>/dev/null || true && \
#     find /home/ubuntu/repo -name ".git" -type f -delete 2>/dev/null || true

# # =============================================================================
# # Set ownership of agent workspace
# # Agent can modify source files but not access secure_git
# # =============================================================================
# RUN chown -R ubuntu:ubuntu /home/ubuntu/repo

# # =============================================================================
# # Environment variables
# # =============================================================================
# ENV SECURE_GIT_DIR=/evaluation/secure_git
# ENV REPO_PATH=/home/ubuntu/repo
# ENV MCP_TESTING_MODE=1
# ENV HOME=/home/ubuntu

# WORKDIR /home/ubuntu

# CMD ["hud_eval"]

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    git sudo \
    curl \
    wget \
    python3 \
    python3-pip \
    build-essential \
    cmake \
    ninja-build \
    libcurl4-openssl-dev \
    libssl-dev \
    libevent-dev \
    zlib1g-dev \
    ccache \
    findutils \
    && rm -rf /var/lib/apt/lists/*


ENV CCACHE_DIR=/var/cache/ccache
ENV CCACHE_MAXSIZE=5G
ENV CCACHE_COMPRESS=1
ENV CCACHE_BASEDIR=/
ENV CCACHE_NOHASHDIR=1
ENV PATH="/usr/lib/ccache:$PATH"

RUN mkdir -p /var/cache/ccache && \
    chmod 777 /var/cache/ccache && \
    ccache --max-size=5G && \
    ccache --set-config=compression=true

COPY . /evaluation
WORKDIR /evaluation
RUN pip install --break-system-packages -e . --no-cache-dir

RUN git config --system user.email "agent@evaluation.local" && \
    git config --system user.name "Evaluation Agent" && \
    git config --system --add safe.directory '*'

WORKDIR /home/ubuntu

RUN git clone --recurse-submodules https://github.com/transmission/transmission.git /home/ubuntu/repo

WORKDIR /home/ubuntu/repo

RUN mkdir -p build && cd build && \
    cmake -G Ninja \
        -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DENABLE_GTK=OFF \
        -DENABLE_QT=OFF \
        -DENABLE_MAC=OFF \
        -DENABLE_TESTS=ON \
        -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
        -DCMAKE_C_COMPILER_LAUNCHER=ccache \
        .. && \
    ninja -j$(nproc)

RUN mkdir -p /evaluation/secure_git && \
    mv /home/ubuntu/repo/.git /evaluation/secure_git/repo.git && \
    chown -R root:root /evaluation/secure_git && \
    chmod -R 700 /evaluation/secure_git

RUN find /home/ubuntu/repo -name ".git" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /home/ubuntu/repo -name ".git" -type f -delete 2>/dev/null || true

RUN chown -R ubuntu:ubuntu /home/ubuntu/repo &&

ENV SECURE_GIT_DIR=/evaluation/secure_git/repo.git
ENV REPO_PATH=/home/ubuntu/repo
ENV HOME=/home/ubuntu
ENV MCP_TESTING_MODE=1

WORKDIR /home/ubuntu

CMD ["hud_eval"]