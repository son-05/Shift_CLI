# AutoPilot — AI-Powered Terminal Automation CLI

> Natural language → shell commands → safe execution

AutoPilot is an AI-powered terminal assistant that converts plain English instructions
into executable shell commands using a 3-agent pipeline on Azure AI Foundry.

## Quick Start

```bash
pip install autopilot-cli
autopilot
```

On first run, you'll be guided through setup:
1. Enter your **Azure AI Foundry** project endpoint
2. AutoPilot auto-detects your OS (Windows/macOS/Linux)
3. Start describing tasks!

## How It Works

```
You: "Set up a Python project with a virtual environment"
    ↓
┌─────────────────────────────────────────────────────┐
│  Planner Agent    → decomposes into ordered steps   │
│  Researcher Agent → finds exact commands + risk     │
│  Writer Agent     → final clean execution plan      │
└─────────────────────────────────────────────────────┘
    ↓
AutoPilot shows you each command with risk levels:
  ● safe     — no data loss, fully reversible
  ▲ moderate — changes system state, but reversible
  ■ dangerous — permanent/destructive (blocked by default)
    ↓
You confirm → commands execute one by one
```

## Features

- **Natural Language Input** — describe tasks in plain English
- **3-Agent Pipeline** — Planner → Researcher → Writer via Azure AI Foundry
- **Risk-Aware Safety** — commands rated safe/moderate/dangerous with color coding
- **OS Auto-Detection** — generates commands for your specific OS and shell
- **Human-in-the-Loop** — clarifying questions before execution for better results
- **Interactive CLI** — Rich terminal UI with tables, spinners, and panels
- **Command History** — persistent SQLite log of all tasks and results
- **Step-by-Step Mode** — confirm each command individually

## Usage

### Interactive Mode
```bash
autopilot
```

### Single Task
```bash
autopilot -t "create a new React project with TypeScript"
```

### Skip Clarifying Questions
```bash
autopilot --no-hitl -t "install Docker on this machine"
```

### View History
```bash
autopilot history
```

### Reconfigure
```bash
autopilot setup
```

## Configuration

AutoPilot stores its config at `~/.autopilot/config.json`.

### Required: Azure AI Foundry Endpoint
Get your endpoint from: **Azure AI Foundry portal → your project → Overview**

You can also set it via environment variable:
```bash
export AZURE_FOUNDRY_ENDPOINT=https://your-resource.services.ai.azure.com/api/projects/your-project
```

Or create a `.env` file in your working directory:
```env
AZURE_FOUNDRY_ENDPOINT=https://your-resource.services.ai.azure.com/api/projects/your-project
```

### Azure Authentication
AutoPilot uses `DefaultAzureCredential` which supports:
- Azure CLI login (`az login`)
- Environment variables
- Managed Identity
- Visual Studio Code credentials

## Safety

AutoPilot takes command safety seriously:

| Risk Level | Examples | Behavior |
|------------|----------|----------|
| 🟢 Safe | `mkdir`, `ls`, `pip install` | Shown for confirmation |
| 🟡 Moderate | `apt install`, `chmod 644` | Shown with warnings |
| 🔴 Dangerous | `rm -rf`, `dd`, `mkfs` | **Blocked by default** |

Dangerous commands matching known destructive patterns are **always blocked** and cannot be executed through AutoPilot.

## Requirements

- Python 3.10+
- Azure AI Foundry project with the `autopilot` workflow deployed
- Azure authentication configured (e.g., `az login`)

## Development

```bash
# Clone the repo
git clone https://github.com/your-username/AutoPilot.git
cd AutoPilot

# Install in editable mode
pip install -e ".[dev]"

# Run locally
python run_autopilot.py

# Build for PyPI
python -m build

# Check distribution
twine check dist/*
```

## Project Structure

```
AutoPilot/
├── pyproject.toml              # PyPI package config
├── README.md
├── run_autopilot.py            # Local dev shortcut
│
├── autopilot/                  # Main package
│   ├── cli.py                  # Interactive REPL + Rich UI
│   ├── config.py               # Azure Foundry config manager
│   ├── executor.py             # Safe command executor
│   │
│   ├── agents/                 # Agent pipeline
│   │   ├── prompts.py          # System prompts (Planner/Researcher/Writer)
│   │   └── pipeline.py         # Foundry conversations API wrapper
│   │
│   ├── hitl/                   # Human-in-the-loop
│   │   └── questioner.py       # Clarifying question generator
│   │
│   └── memory/                 # Persistent history
│       └── store.py            # SQLite command log
│
├── context.md                  # Agent prompt reference
├── problem_stmt.md             # Problem statement
└── workflow.py                 # Original Foundry workflow
```

## License

MIT License — see [LICENSE](LICENSE)
