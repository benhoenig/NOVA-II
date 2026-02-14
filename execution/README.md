# Execution Scripts

This directory contains deterministic Python scripts that handle the actual work.

## Purpose

Execution scripts are the **reliable, testable tools** that the AI agent orchestrates. They handle:
- API calls
- Data processing
- File operations
- Database interactions
- Web scraping
- Report generation

## Why Deterministic Scripts?

LLMs are probabilistic. If you ask an AI to do 5 tasks with 90% accuracy each, overall success is only 59%. By pushing complexity into deterministic Python code, we achieve near-100% reliability per step.

## Script Guidelines

### Structure
Each script should:
1. **Load environment variables** from `.env`
2. **Accept clear inputs** (command-line args or function params)
3. **Handle errors gracefully** with informative messages
4. **Return/output clear results**
5. **Be well-commented** for future maintenance

### Template
```python
#!/usr/bin/env python3
"""
Script description here.

Usage:
    python script_name.py <arg1> <arg2>
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main(arg1, arg2):
    """Main function with clear purpose."""
    try:
        # Your logic here
        result = process_data(arg1, arg2)
        return result
    except Exception as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    main(sys.argv[1], sys.argv[2])
```

## Best Practices

1. **One script, one purpose**: Keep scripts focused
2. **Error handling**: Use try/except with informative messages
3. **Logging**: Print progress for visibility
4. **Testing**: Test scripts independently before integration
5. **Comments**: Explain complex logic and API quirks
6. **Env vars**: Never hardcode secrets, use `.env`

## Common Patterns

- **API clients**: Reusable modules for external services
- **Data processors**: Transform and clean data
- **File handlers**: Read/write operations with error handling
- **Validators**: Input validation and sanity checks

The AI agent will call these scripts based on directives. Keep them reliable!
