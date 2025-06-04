# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Running the Application
```bash
python main.py
```

### Installing Dependencies
```bash
pip install -r requirements.txt
```

### Virtual Environment Setup
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Architecture Overview

RSS Terminal is a Python tkinter application that provides a terminal-style RSS feed reader. The application follows a clean separation of concerns with three main components:

### Core Components

1. **Main Entry (`main.py`)**: Handles dependency checking and application initialization
2. **Application Coordinator (`rss_terminal/app.py`)**: Orchestrates all components and manages the application lifecycle
3. **UI Layer (`rss_terminal/ui.py`)**: Terminal-style tkinter interface with amber-on-black color scheme
4. **Feed Manager (`rss_terminal/feed_manager.py`)**: Handles RSS feed parsing, article deduplication, and background fetching
5. **Configuration (`rss_terminal/config.py`)**: Manages INI-based config and JSON state persistence
6. **Utilities (`rss_terminal/utils.py`)**: Date parsing and time formatting utilities

### Key Design Patterns

- **Component Coordination**: `RSSTerminalApp` acts as the central coordinator, injecting dependencies and setting up communication between components
- **Background Processing**: Feed fetching runs in a separate daemon thread with callback-based UI updates
- **State Persistence**: Last-seen article GUIDs are tracked in `last_seen.json` to identify new articles
- **Article Deduplication**: Headlines are deduplicated both within a single fetch and across existing articles
- **Memory Management**: Articles are automatically cleaned up (2-day retention, 1000 article limit)

### Configuration System

The application uses `rss_config.ini` for settings and feed configuration:
- Feed sources are defined with short codes (e.g., BN_MRKT, TCHMEME) that appear in the terminal UI
- Refresh intervals, timezone, and weather settings are configurable
- Default config is auto-generated if missing

### Threading Model

- Main thread handles UI and tkinter events
- Background daemon thread fetches feeds periodically
- Initial fetch is scheduled via tkinter's `after()` method
- UI updates are delivered via callbacks to maintain thread safety