FROM docker.io/library/python:3.13-slim AS python-base

RUN apt-get update && apt-get -y upgrade

    # python
ENV PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    \
    # pip
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    \
    # paths
    # this is where our requirements + virtual environment will live
    PYSETUP_PATH="/code"


# `builder-base` stage is used to build deps + create our virtual environment
FROM python-base AS builder-base
RUN apt-get install --no-install-recommends -y \
        # deps for building python deps
        build-essential git

# install UV
RUN pip install uv

# copy project requirement files here to ensure they will be cached.
WORKDIR $PYSETUP_PATH
COPY uv.lock pyproject.toml README.md ./

# install runtime deps
RUN uv sync --frozen --no-dev --no-install-project

# Copy the source code
COPY ./app ./app

# install main app
RUN uv sync --frozen --no-dev


# `production` image used for runtime
FROM python-base AS production

ENV FASTAPI_ENV=production
ENV HTTP_PORT=8000

# Copy the dependencies
COPY --from=builder-base $PYSETUP_PATH $PYSETUP_PATH

WORKDIR $PYSETUP_PATH

EXPOSE $HTTP_PORT

# --proxy-headers to trust headers from the proxy (e.g. Traefik)
CMD exec $PYSETUP_PATH/.venv/bin/uvicorn app.main:app --proxy-headers --host 0.0.0.0 --port $HTTP_PORT
