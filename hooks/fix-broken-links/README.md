---
name: 'Fix Broken Links'
description: 'Automatically detects and fixes broken links in documentation and code'
tags: ['automation', 'documentation', 'quality']
---

# Fix Broken Links Hook

Automatically detects and fixes broken links in documentation and code during Copilot sessions.

## Overview

This hook runs during Copilot coding sessions to:
- Scan documentation for broken links
- Detect invalid URL references
- Suggest or auto-fix broken links
- Maintain link integrity across the project

## Features

- **Automatic Detection**: Finds broken links in markdown and code files
- **Link Validation**: Verifies URLs are accessible and valid
- **Auto-Fix**: Suggests corrections for common link issues
- **Project-Wide Scanning**: Checks all documentation and code files

## Installation

1. Copy this hook folder to your repository's `.github/hooks/` directory:
   ```bash
   cp -r hooks/fix-broken-links .github/hooks/
   ```

## Configuration

Configure the hook behavior by editing `hooks.json` in this directory. See the hook specification for details on available options.
