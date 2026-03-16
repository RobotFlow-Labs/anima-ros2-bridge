# ANIMA ROS2 Bridge — Project Command

You are working on the ANIMA ROS2 Bridge project at `/Users/ilessio/Development/AIFLOWLABS/projects/anima-ros2-bridge/`.

## Project Rules
1. All code files MUST be under 480 lines. Split if larger.
2. All code MUST pass `ruff check` with zero errors.
3. All code MUST pass `uv run pytest tests/` with zero failures.
4. All code MUST have type hints and docstrings.
5. Copyright header: `Copyright (c) 2026 AIFLOW LABS LIMITED / RobotFlowLabs`
6. Python 3.14 — use StrEnum, free-threading patterns, modern syntax.
7. Docker containers use `anima_` prefix for all service names.
8. This is 100% original IP — never copy from repositories/ folder.

## Quick Commands
```bash
# Test
uv run pytest tests/ -v

# Lint
ruff check anima_bridge/ tests/

# Format
ruff format anima_bridge/ tests/

# Run bridge (local DDS)
uv run python -m anima_bridge --transport direct_dds

# Run bridge (rosbridge)
uv run python -m anima_bridge --transport rosbridge --url ws://localhost:9090

# Docker
docker compose -f docker/docker-compose.yml up

# Docker dev (with live reload)
docker compose -f docker/docker-compose.yml -f docker/docker-compose.dev.yml up
```

## Architecture
- `anima_bridge/transport/` — Transport abstraction (Direct DDS default, rosbridge compat)
- `anima_bridge/tools/` — 7 MCP tools for ROS2 operations
- `anima_bridge/safety/` — Pre-execution safety validation
- `anima_bridge/context/` — Robot capability discovery + agent prompt injection
- `anima_bridge/commands/` — Direct commands (e-stop, transport switch)
- `docker/` — All Docker infrastructure
- `tests/` — Unit + integration + eval tests
- `repositories/` — Reference code (study only, never deploy)

## When Adding New Code
1. Write the code (under 480 lines per file)
2. Add tests in `tests/unit/`
3. Run `ruff check` — must be clean
4. Run `uv run pytest` — all must pass
5. Add copyright header
