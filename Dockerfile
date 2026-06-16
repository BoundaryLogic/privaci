# PrivaCI community engine image.
# Release builds pin BASE_IMAGE to a digest via --build-arg (see .github/workflows/release.yml).

ARG BASE_IMAGE=python:3.12-slim-bookworm
ARG PRIVACI_VERSION=0.0.0-dev
ARG PRIVACI_CONTRACT_VERSION=1.0
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.version="${PRIVACI_VERSION}" \
      io.boundarylogic.contract_version="${PRIVACI_CONTRACT_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp

WORKDIR /opt/privaci

COPY requirements.txt requirements-nlp.txt pyproject.toml README.md ./
COPY src/ src/

# Install build deps, build wheels, and purge in a single layer so the
# toolchain (~195 MB of gcc/libpq-dev) never persists in the final image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && pip install --no-cache-dir -r requirements.txt -r requirements-nlp.txt \
    && pip install --no-cache-dir --no-deps . \
    && python -m spacy download en_core_web_sm \
    && apt-get purge -y --auto-remove gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/* /root/.cache /tmp/*

RUN groupadd --gid 10001 privaci \
    && useradd --uid 10001 --gid 10001 --home-dir /tmp --shell /usr/sbin/nologin privaci \
    && chown -R privaci:privaci /opt/privaci

USER 10001:10001

ENTRYPOINT ["privaci"]
