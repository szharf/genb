FROM docker.m.daocloud.io/library/python:3.11-alpine3.23

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple \
    PIP_TRUSTED_HOST=mirrors.aliyun.com

WORKDIR /app
COPY pyproject.toml ./
COPY genb_gateway ./genb_gateway
RUN apk upgrade --no-cache \
    && python -m pip install --no-cache-dir . \
    && python -m pip install --no-cache-dir --upgrade "cryptography>=50.0.0" "wheel>=0.46.2" \
    && python -m pip uninstall -y pip setuptools wheel \
    && apk del .python-rundeps sqlite-libs \
    && python -c "import ssl, cryptography, uvicorn; print(ssl.OPENSSL_VERSION)"

USER 65532:65532
EXPOSE 9080
CMD ["python", "-m", "genb_gateway.server"]
