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

RUN chown -R ubuntu:ubuntu /home/ubuntu/repo

ENV SECURE_GIT_DIR=/evaluation/secure_git/repo.git
ENV REPO_PATH=/home/ubuntu/repo
ENV HOME=/home/ubuntu
ENV MCP_TESTING_MODE=1
ENV HUD_CLIENT_TIMEOUT=3600

WORKDIR /home/ubuntu

CMD ["hud_eval"]