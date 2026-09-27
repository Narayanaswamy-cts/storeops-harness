# StoreOps API — container image for the demonstration deployment.
#
# Two stages so the runtime image carries no build backend and no wheel cache.
# The app is installed as a package rather than copied onto PYTHONPATH, which
# keeps the src/ layout working exactly as it does under pytest.

FROM python:3.11-slim AS build

WORKDIR /build

# Dependency metadata first: this layer is cached until pyproject.toml changes,
# so ordinary source edits do not re-resolve dependencies.
COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir .


FROM python:3.11-slim AS runtime

# Run unprivileged. The app holds no state on disk -- repositories are in-memory
# dicts -- so it needs no writable volume.
RUN useradd --create-home --shell /usr/sbin/nologin storeops

COPY --from=build /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STOREOPS_ENV=container \
    STOREOPS_API_PREFIX=/api/v1

USER storeops
WORKDIR /home/storeops

EXPOSE 8000

# /health is unprefixed and touches no module state, so it is a true liveness
# probe rather than a smoke test of the API surface.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["uvicorn", "storeops.main:app", "--host", "0.0.0.0", "--port", "8000"]
