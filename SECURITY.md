# Security

ReviewTrace is research infrastructure software. The following areas involve potential security considerations.

## API key handling

API keys are loaded from environment variables or a local `.env` file. Keys are never logged or transmitted to ReviewTrace servers. Do not commit `.env` to version control.

## Local file access

ReviewTrace reads seed paper files, criteria files, and database files from paths you specify. Ensure input paths point to trusted files.

## Prompt injection via retrieved paper text

Paper titles, abstracts, and metadata retrieved from external sources are embedded in LLM prompts for screening and evidence extraction. Adversarially crafted paper metadata could influence LLM outputs. Treat LLM-generated screening decisions and evidence as review assistance, not authoritative ground truth.

## Export path handling

Output file paths are user-specified. Ensure output directories are within trusted, expected locations.

## Web UI server exposure

The `reviewtrace web` and `reviewtrace serve` commands bind to `127.0.0.1` (localhost) by default. If you change the host to `0.0.0.0`, the server becomes accessible to other machines on your network. Do not expose the server on untrusted networks without adding authentication.

## Reporting issues

If you discover a security issue, please open a GitHub issue or contact the maintainer directly before public disclosure.
