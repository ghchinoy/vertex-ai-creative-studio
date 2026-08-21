# Multi-stage build for the credentio C2PA validator service (spike).
#
# Stage 1 (builder) compiles credentio's //tools:c2pa_validate from source with
# Bazelisk + Clang/libc++. Stage 2 (runtime) is a slim Python image carrying only
# the compiled binary, the trust anchors, and the FastAPI service.
#
# STATUS (review honesty): the *service* stage and the app have been smoke-tested
# locally (uvicorn + pytest). The *builder* stage mirrors scripts/build_credentio.sh
# exactly but the full in-Docker Bazel build (~27 min, large download) was NOT run
# in the spike env -- it is written to be correct and reviewable, not yet executed.
# See poc/phase234-build-notes.md.

# --------------------------------------------------------------------------- #
# Stage 1: build the credentio binary
# --------------------------------------------------------------------------- #
FROM debian:12-slim AS builder

ARG CREDENTIO_COMMIT=4ac69fc
ARG BAZELISK_VERSION=1.25.0

RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates curl \
        clang lld libc++-dev libc++abi-dev \
        python3 \
    && rm -rf /var/lib/apt/lists/*

# Bazelisk resolves and runs the Bazel version credentio wants.
RUN curl -fsSL -o /usr/local/bin/bazelisk \
        "https://github.com/bazelbuild/bazelisk/releases/download/v${BAZELISK_VERSION}/bazelisk-linux-amd64" \
    && chmod +x /usr/local/bin/bazelisk

ENV CC=clang CXX=clang++

WORKDIR /src
RUN git clone https://mediaprovenance.googlesource.com/credentio . \
    && git checkout "${CREDENTIO_COMMIT}"

# credentio's .bazelrc forces -stdlib=libc++.
RUN bazelisk build -c opt //tools:c2pa_validate \
    && cp -f bazel-bin/tools/c2pa_validate /usr/local/bin/c2pa_validate \
    && chmod +x /usr/local/bin/c2pa_validate

# --------------------------------------------------------------------------- #
# Stage 2: runtime service
# --------------------------------------------------------------------------- #
# python:3.14-slim per the design contract (repo convention). NB: the app was
# smoke-tested locally on 3.11 -- nothing here uses a 3.12+ feature. See README.
FROM python:3.14-slim AS runtime

# libc++ runtime libraries the compiled binary links against.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libc++1 libc++abi1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The compiled validator + its default trust anchors.
COPY --from=builder /usr/local/bin/c2pa_validate /app/bin/c2pa_validate
COPY trust/ /app/trust/

# Application code + metadata.
COPY pyproject.toml README.md /app/
COPY credentio_validator/ /app/credentio_validator/

RUN pip install --no-cache-dir "fastapi>=0.110" "uvicorn>=0.27" "pydantic>=2" "requests>=2.28"

# runner.py resolves the binary via CREDENTIO_VALIDATE_BIN (falls back to
# ./bin/c2pa_validate). Point it at the copied binary explicitly.
ENV CREDENTIO_VALIDATE_BIN=/app/bin/c2pa_validate
ENV PYTHONUNBUFFERED=1

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/healthz').status==200 else 1)"

CMD ["uvicorn", "credentio_validator.service:app", "--host", "0.0.0.0", "--port", "8080"]
