# Contributing to Autonomous Insurance Claims Processor

Thank you for your interest in contributing to the Autonomous Insurance Claims Processor! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

This project follows a code of conduct to ensure a welcoming environment for all contributors. By participating, you agree to:

- Be respectful and inclusive
- Focus on constructive feedback
- Accept responsibility for mistakes
- Show empathy towards other contributors
- Help create a positive community

## Getting Started

### Prerequisites

- Python 3.11 or higher
- PostgreSQL 15 or higher
- Git
- Docker (optional, for containerized development)

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/autonomous-insurance-claims-processor.git
   cd autonomous-insurance-claims-processor
   ```

2. **Set up Python Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Database Setup**
   ```bash
   # Using Docker
   docker run -d --name postgres -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:15

   # Or install PostgreSQL locally
   ```

4. **Environment Configuration**
   ```bash
   cp autonomous_claims_processor/.env.example autonomous_claims_processor/.env
   # Edit .env with your API keys and database credentials
   ```

5. **Run the Application**
   ```bash
   python start.py
   ```

## Making Changes

### Branch Naming

Use descriptive branch names following this pattern:
- `feature/description-of-feature`
- `bugfix/issue-description`
- `docs/update-documentation`
- `refactor/component-name`

### Code Style

- Follow [PEP 8](https://pep8.org/) style guidelines
- Use type hints for function parameters and return values
- Write descriptive variable and function names
- Keep functions small and focused on a single responsibility
- Add docstrings to all public functions and classes

### Commit Messages

Write clear, descriptive commit messages:
- Start with a verb (Add, Fix, Update, Remove, etc.)
- Keep the first line under 50 characters
- Add a blank line after the first line
- Provide detailed explanation in the body if needed

Example:
```
Add weather verification agent

- Implement NOAA API integration
- Add Tomorrow.io as fallback weather source
- Include confidence scoring for weather claims
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=autonomous_claims_processor --cov-report=html

# Run specific test file
pytest tests/test_claims_processor.py

# Run tests in verbose mode
pytest -v
```

### Writing Tests

- Write unit tests for all new functions
- Include integration tests for API endpoints
- Test both success and failure scenarios
- Use descriptive test names
- Mock external API calls

### Test Coverage

Maintain high test coverage (>80%) for all new code. Run coverage reports regularly.

## Submitting Changes

### Pull Request Process

1. **Create a Pull Request**
   - Ensure your branch is up to date with main
   - Run all tests and ensure they pass
   - Update documentation if needed
   - Add screenshots for UI changes

2. **PR Description**
   - Clearly describe the changes
   - Reference any related issues
   - Include testing instructions
   - List any breaking changes

3. **Code Review**
   - Address review comments promptly
   - Make requested changes
   - Keep the PR focused on a single feature/fix

### Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass and coverage is maintained
- [ ] Documentation is updated
- [ ] No sensitive information is committed
- [ ] Commit messages are clear and descriptive
- [ ] PR description is comprehensive

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

- **Description**: Clear description of the issue
- **Steps to Reproduce**: Step-by-step instructions
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Environment**: Python version, OS, dependencies
- **Logs**: Relevant error messages or logs
- **Screenshots**: If applicable

### Feature Requests

For feature requests, please include:

- **Description**: What feature you'd like to see
- **Use Case**: Why this feature would be useful
- **Implementation Ideas**: Any thoughts on how to implement it
- **Alternatives**: Other solutions you've considered

## Additional Resources

- [Project Documentation](README.md)
- [API Documentation](http://localhost:8000/docs) (when running locally)
- [Python Documentation](https://docs.python.org/3/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

Thank you for contributing to the Autonomous Insurance Claims Processor! 🚀