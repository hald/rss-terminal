# Bloomberg-Style Financial News Terminal

A Python application that displays RSS feeds in a Bloomberg terminal-inspired interface. This app provides a nostalgic and professional financial news experience with real-time updates from various sources.

## Features

- Authentic Bloomberg terminal UI aesthetic
- Sections for "Top Ranked News" and "Time Ordered News"
- Clickable headlines that open articles in your web browser
- Automatic feed refreshing with countdown timer
- Configurable news sources with standardized source codes (like BFW, RNS, BN)
- Timeline sorted by publication time
- Color-coded interface with amber text on black background

## Installation

### Prerequisites

- Python 3.6+
- Required Python packages:
  - tkinter (usually comes with Python)
  - feedparser
  - pytz
  - python-dateutil

### Install Dependencies

```bash
pip install feedparser pytz python-dateutil
```

## Usage

1. Edit the `terminal_config.ini` file to add your preferred RSS feeds and set the refresh interval
2. Run the application:

```bash
python bloomberg_terminal.py
```

3. Click on any headline to open the article in your default web browser

## Configuration

The application uses a configuration file named `terminal_config.ini` to store settings:

```ini
[Settings]
refresh_interval = 300  # Refresh interval in seconds
timezone = America/Los_Angeles  # Standard timezone name

[Feeds]
# Format: SOURCECODE = feed_url
BBGMKT = https://www.bloomberg.com/feed/markets/sitemap_index.xml
RTRSFI = https://www.reutersagency.com/feed/
BFW = https://www.nasdaq.com/feed/rssoutbound?category=Business+Wire
```

Source codes are displayed next to headlines in the terminal interface. For an authentic Bloomberg look, use 3-6 character source codes.

### Timezone Configuration

The application uses standard timezone names. Some common examples:
- `America/Los_Angeles` (US Pacific, GMT-7/8)
- `America/New_York` (US Eastern, GMT-4/5)
- `Europe/London` (UK, GMT/BST)
- `Asia/Tokyo` (Japan, GMT+9)

## Interface Elements

The application mimics the key elements of a Bloomberg terminal:

- Top navigation menu with dropdown
- Securities ticker bar
- Function menu with blue background
- News sections with headlines, sources and timestamps
- Status bar with function indicators
- Dense, information-rich layout

Headlines are displayed in chronological order with a numbering system, source code, and timestamp. Clicking any headline opens the full article in your web browser.

## Keyboard Shortcuts

- F2: Manual refresh of all feeds

## About

This application is inspired by the Bloomberg Professional Terminal, providing a nostalgic way to consume news feeds in a professional financial interface.