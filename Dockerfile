FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY autopilot/ autopilot/
COPY run_autopilot.py .

RUN pip install --no-cache-dir .

VOLUME /root/.autopilot

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["autopilot"]
