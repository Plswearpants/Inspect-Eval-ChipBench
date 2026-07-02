# Toolchain image for ChipBench scoring: Icarus Verilog (generation/debugging
# simulation) + Yosys/CXXRTL + Verilator (cross-language reference model
# verification, via the vendored Tool_Box/crosslang_verify).
#
# Adapted from the vendored ChipBench Dockerfile
# (https://github.com/zhongkaiyu/ChipBench/blob/main/Dockerfile), with one
# deliberate change: that Dockerfile apt-installs `verilator` from Ubuntu
# 22.04's archive (~v4.038), which is too old for crosslang_verify's
# generated testbenches (compiled against a modern Verilator/CXXRTL API).
# Here Verilator is built from source and pinned to a specific tag instead.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    autoconf \
    flex \
    bison \
    gperf \
    help2man \
    perl \
    ccache \
    libfl2 \
    libfl-dev \
    zlib1g-dev \
    curl \
    wget \
    pkg-config \
    libsystemc-dev \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    clang \
    tcl-dev \
    libreadline-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && ln -s /usr/bin/python3 /usr/bin/python

# Yosys v0.60 (source build, provides the CXXRTL backend/runtime headers
# crosslang_verify links against)
RUN git clone https://github.com/YosysHQ/yosys.git /tmp/yosys \
    && cd /tmp/yosys \
    && git checkout v0.60 \
    && git submodule update --init --recursive \
    && make config-clang \
    && make -j"$(nproc)" \
    && make install \
    && cd / && rm -rf /tmp/yosys

# Icarus Verilog v12 (source build; matches the paper's own gen/debug
# testbench workflow)
RUN git clone https://github.com/steveicarus/iverilog.git /tmp/iverilog \
    && cd /tmp/iverilog \
    && git checkout v12-branch \
    && sh ./autoconf.sh \
    && ./configure \
    && make -j"$(nproc)" \
    && make install \
    && cd / && rm -rf /tmp/iverilog

# Verilator, pinned (source build - see header comment for why this
# replaces the vendored Dockerfile's apt package)
ARG VERILATOR_VERSION=v5.038
RUN git clone https://github.com/verilator/verilator.git /tmp/verilator \
    && cd /tmp/verilator \
    && git checkout "${VERILATOR_VERSION}" \
    && autoconf \
    && ./configure \
    && make -j"$(nproc)" \
    && make install \
    && cd / && rm -rf /tmp/verilator

COPY Tool_Box/crosslang_verify /opt/crosslang_verify

WORKDIR /workspace

CMD ["tail", "-f", "/dev/null"]
