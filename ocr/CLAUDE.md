# OCR Project Guidelines

## Commands
- Run OCR script: `python ocr.py`
- Install dependencies: `pip install -r requirements.txt`
- Format code: `black ocr.py`
- Type checking: `mypy ocr.py`
- Linting: `pylint ocr.py`

## Code Style
- Follow PEP 8 conventions
- Use type hints for all functions and variables
- Use Pydantic models for data validation
- Group imports: standard library, third-party, local
- Use async/await for concurrent operations
- Document functions with docstrings
- Error handling with try/except blocks
- Use logfire for structured logging
- Variable naming: snake_case for variables/functions, PascalCase for classes
- Limit concurrency with semaphores when needed
- Store sensitive data in .env files (not hardcoded)
- Use pathlib for file path operations