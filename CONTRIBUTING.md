# Contributing

Thanks for helping improve Muse Mac Connector.

## Priorities

Changes should preserve the project's core security model:

- least privilege by default
- local user approval for sensitive actions
- no committed credentials or user-specific paths
- no silent widening of filesystem or macOS permissions
- localhost-only agent binding

## Development

```bash
./install.sh
./start-secure.sh
```

Run the test suite before opening a pull request:

```bash
.venv/bin/python3 -m unittest discover -s tests -v
```
