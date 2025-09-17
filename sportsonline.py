import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime, timedelta
from pytz import timezone
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_date_for_day(target_day, base_date):
    """Map a day (e.g., 'WEDNESDAY') to the corresponding date in the current week."""
    days_of_week = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    target_day = target_day.upper()
    if target_day not in days_of_week:
        return base_date
    
    current_weekday = base_date.weekday()  # 0 = Monday, 6 = Sunday
    target_weekday = days_of_week.index(target_day)
    delta_days = target_weekday - current_weekday
    if delta_days < -3:
        delta_days += 7  # Assume next week's day if more than 3 days in the past
    elif delta_days > 3:
        delta_days -= 7  # Assume previous week's day if more than 3 days in the future
    return base_date + timedelta(days=delta_days)

def convert_london_to_jakarta(time_str, date_str):
    try:
        # Define time zones
        london_tz = timezone('Europe/London')
        jakarta_tz = timezone('Asia/Jakarta')
        
        # Parse the time with the given date
        datetime_str = f"{date_str} {time_str}"
        london_time = london_tz.localize(datetime.strptime(datetime_str, "%Y-%m-%d %H:%M"))
        
        # Convert to Jakarta time
        jakarta_time = london_time.astimezone(jakarta_tz)
        
        # Extract time component (date is not used in output)
        jakarta_time_str = jakarta_time.strftime("%H:%M")
        return jakarta_time_str
    except ValueError as e:
        logging.error(f"Error converting time {time_str} with date {date_str}: {e}")
        return time_str  # Fallback to original time

def parse_time_minus_10(time_str, date_str):
    try:
        # Parse the input time with the given date
        london_tz = timezone('Europe/London')
        datetime_str = f"{date_str} {time_str}"
        london_time = london_tz.localize(datetime.strptime(datetime_str, "%Y-%m-%d %H:%M"))
        
        # Subtract 10 minutes
        london_time_minus_10 = london_time - timedelta(minutes=10)
        
        # Convert to Jakarta time
        jakarta_tz = timezone('Asia/Jakarta')
        jakarta_time = london_time_minus_10.astimezone(jakarta_tz)
        
        return jakarta_time.strftime("%H:%M")
    except ValueError as e:
        logging.error(f"Error parsing time {time_str} with date {date_str}: {e}")
        return time_str  # Fallback to original time

def extract_channel_from_url(url):
    # Extract the channel name from the URL (e.g., 'hd3' from 'https://sportzonline.si/channels/hd/hd3.php')
    match = re.search(r'channels/(?:hd|pt|bra)/([^/]+)\.php$', url)
    if match:
        return match.group(1)
    logging.warning(f"Could not extract channel from URL: {url}")
    return None

def scrape_sportsonline():
    url = "https://sportsonline.sn/prog.txt"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        # Ensure response is decoded as UTF-8
        response.encoding = 'utf-8'
    except requests.RequestException as e:
        logging.error(f"Failed to fetch URL {url}: {e}")
        return []
    
    # Log the raw response for debugging
    logging.debug(f"Raw response content: {response.text[:500]}...")  # First 500 chars
    
    # Try parsing as HTML with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser', from_encoding='utf-8')
    pre_tag = soup.find("pre")
    
    if pre_tag:
        logging.info("Found <pre> tag, parsing as HTML")
        lines = pre_tag.text.strip().split("\n")
    else:
        logging.info("No <pre> tag found, treating response as plain text")
        lines = response.text.strip().split("\n")
    
    matches = []
    current_event = None
    current_time = None
    current_day = None
    base_date = datetime.now().date()  # Use current date as base (2025-08-14)
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if the line is a day header
        if line in ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]:
            current_day = line
            logging.info(f"Processing day: {current_day}")
            continue
        
        # Skip irrelevant lines
        if line.startswith("====") or line.startswith("*") or line.startswith(" ") or \
           "UPDATE" in line or "INFO:" in line or "IMPORTANT:" in line or "CHANNELS" in line or \
           line.startswith("HD") or line.startswith("BR"):
            continue
        
        # Match the pattern for an event line
        match_pattern = re.match(r'(\d{2}:\d{2})\s+(.+?)(?:\s+x\s+(.+?))?\s+\|\s+(https://sportzonline\.st/channels/(?:hd|pt|bra)/[^/]+\.php)$', line)
        if not match_pattern:
            logging.debug(f"Line skipped, no match: {line}")
            continue
        
        time_str, team_or1, team2_opt, url = match_pattern.groups()
        team_or1 = team_or1.strip()
        team2 = team2_opt.strip() if team2_opt else ""
        
        # Extract channel from URL
        channel = extract_channel_from_url(url)
        if not channel:
            continue
        
        # Get the date for the current day
        event_date = get_date_for_day(current_day or "THURSDAY", base_date).strftime("%Y-%m-%d")
        
        # Convert times to Jakarta time
        kickoff_time_jakarta = convert_london_to_jakarta(time_str, event_date)
        match_time_jakarta = convert_london_to_jakarta(time_str, event_date)  # Use the same function as kickoff_time
        
        # Create ID
        id_str = team_or1.replace(" ", "").replace(":", "-")
        if team2:
            id_str += "-" + team2.replace(" ", "").replace(":", "-")
        
        # Check if this is a new event or a new server for the same event
        if current_time == time_str and current_event == (team_or1, team2):
            # Add server to the last match
            matches[-1]["servers"].append({
                "url": f"https://multi.govoet.my.id/?ss={channel}",
                "label": f"CH-{len(matches[-1]['servers']) + 1}"
            })
        else:
            # Create new match entry
            match_data = {
                "id": id_str,
                "league": "",
                "team1": {"name": team_or1},
                "team2": {"name": team2} if team2 else {"name": ""},
                "kickoff_date": "",
                "kickoff_time": kickoff_time_jakarta,
                "match_date": "",
                "match_time": match_time_jakarta,
                "duration": "3.5",
                "servers": [{
                    "url": f"https://multi.govoet.my.id/?ss={channel}",
                    "label": "CH-1"
                }]
            }
            matches.append(match_data)
            current_time = time_str
            current_event = (team_or1, team2)
            logging.info(f"Added match: {id_str}")
    
    # Save to sportsonline.json
    try:
        with open("sportsonline.json", "w", encoding="utf-8") as f:
            json.dump(matches, f, indent=2, ensure_ascii=False)
        logging.info("Data saved to sportsonline.json")
    except IOError as e:
        logging.error(f"Failed to save to sportsonline.json: {e}")
    
    return matches

if __name__ == "__main__":
    data = scrape_sportsonline()
    print("Data has been scraped and saved to sportsonline.json")
