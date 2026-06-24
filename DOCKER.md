# Shift_CLI — Docker Usage

## Prerequisites
- Docker installed and running
- Azure AI Foundry endpoint
- `.env` file in your working directory (copy from `.env.example`)

```env
AZURE_FOUNDRY_ENDPOINT=https://your-resource.services.ai.azure.com/api/projects/your-project
```

## Build

```bash
docker build -t shift-cli .
```

## Run

### Interactive mode (recommended)
```bash
docker run -it \
  -v $(pwd)/.env:/app/.env \
  -v ~/.shift_cli:/root/.shift_cli \
  shift-cli
```

### Single task
```bash
docker run -it \
  -v $(pwd)/.env:/app/.env \
  shift-cli -t "your task here"
```

### Skip clarifying questions
```bash
docker run -it \
  -v $(pwd)/.env:/app/.env \
  shift-cli --no-hitl -t "your task here"
```

### View history
```bash
docker run -it \
  -v ~/.shift_cli:/root/.shift_cli \
  shift-cli history
```

### Reconfigure endpoint
```bash
docker run -it \
  -v ~/.shift_cli:/root/.shift_cli \
  shift-cli setup
```

## Volumes

| Volume | Purpose |
|--------|---------|
| `$(pwd)/.env:/app/.env` | Passes your Azure endpoint into the container |
| `~/.shift_cli:/root/.shift_cli` | Persists config and task history between runs |
