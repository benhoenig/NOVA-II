# Directives

This directory contains SOPs (Standard Operating Procedures) written in Markdown that define workflows for the AI agent.

## What is a Directive?

A directive is a natural language instruction set that tells the AI agent:
- **Goal**: What you want to accomplish
- **Inputs**: What data/information is needed
- **Tools**: Which execution scripts to use
- **Outputs**: What deliverables to produce
- **Edge cases**: Common errors and how to handle them

## Directive Template

```markdown
# [Workflow Name]

## Goal
[Brief description of what this workflow accomplishes]

## Inputs
- Input 1: [description]
- Input 2: [description]

## Execution Scripts
- `execution/script_name.py` - [what it does]

## Output
- [Description of deliverable, e.g., Google Sheet with columns X, Y, Z]

## Edge Cases
- **Error type**: How to handle it
- **Rate limits**: Batch processing strategy
```

## Best Practices

1. **Be specific**: Write as if instructing a mid-level employee
2. **Update continuously**: Add learnings from errors and edge cases
3. **Reference scripts**: Always point to specific execution scripts
4. **Define outputs clearly**: Specify exact format and location of deliverables

## Example Directives

Create directive files like:
- `scrape_website.md` - Web scraping workflow
- `generate_report.md` - Data analysis and reporting
- `send_email_campaign.md` - Email automation

The AI agent will read these and orchestrate the execution scripts accordingly.
