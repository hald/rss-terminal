"""
Utility functions for the RSS Terminal application.
"""
import re
import html
import time
import datetime
import requests
from dateutil import parser
import pytz
import html2text

def parse_date(entry):
    """Try to parse date from entry in various formats"""
    if hasattr(entry, 'published_parsed') and entry.published_parsed:
        return time.mktime(entry.published_parsed)
    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
        return time.mktime(entry.updated_parsed)
    elif hasattr(entry, 'published') and entry.published:
        try:
            dt_obj = parser.parse(entry.published)
            return dt_obj.timestamp()
        except:
            pass
    elif hasattr(entry, 'updated') and entry.updated:
        try:
            dt_obj = parser.parse(entry.updated)
            return dt_obj.timestamp()
        except:
            pass
    
    # If all else fails, use current time
    return time.time()

def get_formatted_time(timestamp=None, timezone="America/Los_Angeles"):
    """Get time formatted for display in the specified timezone"""
    tz = pytz.timezone(timezone)
    if timestamp:
        # Convert timestamp to datetime and localize
        dt_obj = datetime.datetime.fromtimestamp(timestamp).replace(tzinfo=pytz.UTC)
        local_time = dt_obj.astimezone(tz)
    else:
        # Current time
        local_time = datetime.datetime.now(tz)
    
    return local_time.strftime("%H:%M")

def get_weather_data(airport_code):
    """Get current weather data for specified airport code"""
    try:
        url = f"https://aviationweather.gov/api/data/metar?ids={airport_code}&hours=0&order=id%2C-obs&format=json"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                weather = data[0]
                temp_c = weather.get('temp')
                
                if temp_c is not None:
                    # Convert Celsius to Fahrenheit
                    temp_f = (temp_c * 9/5) + 32
                    return {
                        'temp_c': round(temp_c, 1),
                        'temp_f': round(temp_f, 1),
                        'airport': airport_code,
                        'last_updated': weather.get('reportTime')
                    }
        
        return None
    except Exception as e:
        print(f"Error fetching weather: {e}")
        return None

def truncate_headline(headline, max_length=90):
    """Truncate headline if it's too long"""
    if len(headline) > max_length:
        return headline[:max_length] + "..."
    return headline

def clean_description_text(text):
    """Clean up HTML or markdown text for better readability"""
    if not text:
        return text
        
    # Remove empty markdown links like [](url)
    text = re.sub(r'\[\]\(([^)]+)\)', r'\1', text)
    
    # Replace markdown links with text and URL
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)
    
    # Replace consecutive spaces with a single space
    text = re.sub(r' {2,}', ' ', text)
    
    # Remove multiple asterisks (bold/italic formatting)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    
    # Remove multiple underscores (bold/italic formatting)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)
    
    # Clean up quotes
    text = re.sub(r'> ', '', text)
    
    # Convert multiple new lines to double new lines for paragraph breaks
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Replace horizontal rules (--- or ***) with a clean separator
    text = re.sub(r'(\-{3,}|\*{3,})', '\n' + '-' * 40 + '\n', text)
    
    # Add proper spacing after periods if missing
    text = re.sub(r'\.([A-Z])', r'. \1', text)
    
    # Cleanup any HTML entities that might remain
    text = html.unescape(text)
    
    # Handle common HTML tags that might remain
    text = re.sub(r'</?br\s*/?>', '\n', text)
    text = re.sub(r'</?p\s*/?>', '\n\n', text)
    
    # General cleanup of any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    return text.strip()

def html_to_text(html_content):
    """Convert HTML content to plain text"""
    if not html_content:
        return "No description available for this article."
    
    # First try direct HTML unescaping (simpler and often works better for simple HTML)
    text = html.unescape(html_content)
    
    # If it still looks like HTML, use html2text for conversion
    if "<" in text and ">" in text:
        # Initialize html2text converter with some configuration
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.body_width = 0  # Don't wrap text at a specific width
        h.unicode_snob = True  # Use Unicode instead of ASCII
        
        try:
            # Convert HTML to markdown-style text
            text = h.handle(text)
        except Exception:
            # If html2text fails, go back to the unescaped version
            pass
    
    # Clean up the description text for better readability
    return clean_description_text(text)