FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY shift_cli/ shift_cli/
COPY run_shift_cli.py .

RUN pip install --no-cache-dir .

VOLUME /root/.shift_cli

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["shift_cli"]
