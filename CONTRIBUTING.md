# Contributing

Contributions are welcome!

## Code Style

This project follows the [PEP 8](https://peps.python.org/pep-0008/) Python style guide.  
Please ensure all code is PEP 8–compliant before submitting a pull request.

## Workflow

1. Fork the repo and clone your fork.

2. Create a branch:
```bash
git checkout -b feature/brief-description
```

3. Make your changes and commit with a clear message:
```bash
git commit -m "short description of change"
```

4. Push and open a pull request against main.

## Tests & Linting
We use tox to run checks:
```
pip install tox
tox -e py
```

## Reporting Issues

Search existing issues before opening a new one. Include a clear title, description, and steps to reproduce.
