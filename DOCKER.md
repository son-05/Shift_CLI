# AutoPilot — Docker Usage

## Prerequisites
- Docker installed and running
- Azure AI Foundry endpoint
- `.env` file in your working directory (copy from `.env.example`)

```env
AZURE_FOUNDRY_ENDPOINT=https://your-resource.services.ai.azure.com/api/projects/your-project
```

## Build

```bash
docker build -t autopilot-cli .
```

## Run

### Interactive mode (recommended)
```bash
docker run -it \
  -v $(pwd)/.env:/app/.env \
  -v ~/.autopilot:/root/.autopilot \
  autopilot-cli
```

### Single task
```bash
docker run -it \
  -v $(pwd)/.env:/app/.env \
  autopilot-cli -t "your task here"
```

### Skip clarifying questions
```bash
docker run -it \
  -v $(pwd)/.env:/app/.env \
  autopilot-cli --no-hitl -t "your task here"
```

### View history
```bash
docker run -it \
  -v ~/.autopilot:/root/.autopilot \
  autopilot-cli history
```

### Reconfigure endpoint
```bash
docker run -it \
  -v ~/.autopilot:/root/.autopilot \
  autopilot-cli setup
```

## Volumes

| Volume | Purpose |
|--------|---------|
| `$(pwd)/.env:/app/.env` | Passes your Azure endpoint into the container |
| `~/.autopilot:/root/.autopilot` | Persists config and task history between runs |
