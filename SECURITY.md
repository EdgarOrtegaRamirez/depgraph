# Security Policy

## Reporting Security Issues

If you discover a security vulnerability in DepGraph, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email security concerns to the maintainers.

## Scope

DepGraph is a static analysis tool that reads dependency files and source code locally. It:

- Does **not** make network requests
- Does **not** execute code
- Does **not** store or transmit data
- Only reads files in the specified directory

## Input Validation

DepGraph validates all file paths and content to prevent:

- Path traversal attacks
- Injection through package names
- Denial of service through deeply nested structures

## Dependencies

DepGraph has **zero runtime dependencies**. Dev dependencies (pytest, ruff) are only used during development and testing.
