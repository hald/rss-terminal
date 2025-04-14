#!/usr/bin/env python3
"""
RSS Terminal - Main entry point
A Bloomberg terminal-inspired RSS feed reader application
"""
import tkinter as tk
import sys

def check_dependencies():
    """Check for required dependencies and provide helpful error if missing"""
    missing_modules = []
    
    try:
        import pytz
    except ImportError:
        missing_modules.append("pytz")
    
    try:
        from dateutil import parser
    except ImportError:
        missing_modules.append("python-dateutil")
        
    try:
        import feedparser
    except ImportError:
        missing_modules.append("feedparser")
        
    try:
        import html2text
    except ImportError:
        missing_modules.append("html2text")
    
    if missing_modules:
        print(f"ERROR: Missing required modules: {', '.join(missing_modules)}")
        print(f"Please install them using: pip install {' '.join(missing_modules)}")
        return False
    
    return True

def main():
    """Main application entry point"""
    # Check dependencies first
    if not check_dependencies():
        sys.exit(1)
    
    # Import here to avoid errors if dependencies are missing
    from rss_terminal.app import RSSTerminalApp
    
    # Create the Tk root window
    root = tk.Tk()
    
    # Initialize the app
    app = RSSTerminalApp(root)
    
    # Set up close handling
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Start the Tk main loop
    root.mainloop()

if __name__ == "__main__":
    main()