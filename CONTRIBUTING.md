# Contributing

ReviewTrace is early-stage open-source infrastructure for auditable literature review. Contributions are welcome.

## Areas where help is especially useful

- Retrieval connectors (new paper APIs, full-text sources)
- Citation expansion (ranking, filtering, coverage improvements)
- Audit schema design and export formats
- Evaluation datasets and benchmark runs
- Web UI improvements
- Documentation and tutorials
- Testing and reproducibility

## Development setup

```bash
conda create -n reviewtrace python=3.11 -y
conda activate reviewtrace
pip install -e ".[all-llm]"
```

## Checks

Before submitting a pull request, run:

```bash
pytest
ruff check reviewtrace tests
mypy reviewtrace
```

All three should pass cleanly.

## Guidelines

- Open an issue before starting large architectural changes so we can discuss the design first.
- Keep pull requests focused — one concern per PR.
- Include tests for new functionality.
- Do not commit `.env` files or API keys.
