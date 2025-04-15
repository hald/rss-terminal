"""
Configuration handling for the RSS Terminal application.
"""
import os
import configparser
import json

class ConfigManager:
    """Manages application configuration and state persistence"""
    
    def __init__(self, config_file="rss_config.ini", last_seen_file="last_seen.json"):
        self.config_file = config_file
        self.last_seen_file = last_seen_file
        self.refresh_interval = 60  # default: 60 seconds
        self.timezone = "America/Los_Angeles"  # default timezone
        self.airport_code = "KTUS"  # default airport code for weather
        self.weather_update_interval = 900  # default: 15 minutes (in seconds)
        self.feeds = []
        self.last_seen_guids = {}
        
        # Create default config if not exists, then load configuration
        if not os.path.exists(self.config_file):
            self._create_default_config()
        
        self.load_config()
        self.load_last_seen()
    
    def load_config(self):
        """Load configuration from config file"""
        config = configparser.ConfigParser()
        config.read(self.config_file)
        
        if 'Settings' in config:
            self.refresh_interval = config.getint('Settings', 'refresh_interval', fallback=60)
            self.timezone = config.get('Settings', 'timezone', fallback="America/Los_Angeles")
            self.airport_code = config.get('Settings', 'airport_code', fallback="KTUS")
            self.weather_update_interval = config.getint('Settings', 'weather_update_interval', fallback=900)
        
        if 'Feeds' in config:
            self.feeds = []
            for key, url in config['Feeds'].items():
                self.feeds.append({'name': key.upper(), 'url': url})
    
    def _create_default_config(self):
        """Create a default configuration file"""
        config = configparser.ConfigParser()
        config['Settings'] = {
            'refresh_interval': '300',
            'timezone': 'America/Phoenix',
            'airport_code': 'KTUS',
            'weather_update_interval': '900'
        }
        config['Feeds'] = {
            'BBGMKT': 'https://www.bloomberg.com/feed/markets/sitemap_index.xml',
            'RTRSFI': 'https://www.reutersagency.com/feed/',
            'BBCNWS': 'http://feeds.bbci.co.uk/news/rss.xml',
            'CNNTOP': 'http://rss.cnn.com/rss/edition.rss'
        }
        
        with open(self.config_file, 'w') as f:
            config.write(f)
    
    def save_last_seen(self):
        """Save the last seen article GUIDs to file"""
        with open(self.last_seen_file, "w") as f:
            json.dump(self.last_seen_guids, f)
    
    def load_last_seen(self):
        """Load the last seen article GUIDs from file"""
        try:
            if os.path.exists(self.last_seen_file):
                with open(self.last_seen_file, "r") as f:
                    self.last_seen_guids = json.load(f)
        except Exception:
            self.last_seen_guids = {}
    
    def update_last_seen_guid(self, feed_name, guid):
        """Add a GUID to the last seen list for a feed"""
        if feed_name not in self.last_seen_guids:
            self.last_seen_guids[feed_name] = []
        
        if guid not in self.last_seen_guids[feed_name]:
            self.last_seen_guids[feed_name].append(guid)
    
    def is_guid_seen(self, feed_name, guid):
        """Check if a GUID has been seen before for a feed"""
        if feed_name not in self.last_seen_guids:
            return False
        
        return guid in self.last_seen_guids[feed_name]