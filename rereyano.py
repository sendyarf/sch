import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime, timedelta
from pytz import timezone

def convert_paris_to_jakarta(date_str, time_str):
    # Define time zones
    paris_tz = timezone('Europe/Paris')
    jakarta_tz = timezone('Asia/Jakarta')
    
    # Parse the date and time
    datetime_str = f"{date_str} {time_str}"
    paris_time = paris_tz.localize(datetime.strptime(datetime_str, "%Y-%m-%d %H:%M"))
    
    # Convert to Jakarta time
    jakarta_time = paris_time.astimezone(jakarta_tz)
    
    # Extract date and time components
    jakarta_date = jakarta_time.strftime("%Y-%m-%d")
    jakarta_time_str = jakarta_time.strftime("%H:%M")
    
    return jakarta_date, jakarta_time_str

def parse_time_minus_10(time_str, date_str):
    # Parse the input time
    paris_tz = timezone('Europe/Paris')
    datetime_str = f"{date_str} {time_str}"
    paris_time = paris_tz.localize(datetime.strptime(datetime_str, "%Y-%m-%d %H:%M"))
    
    # Subtract 10 minutes
    paris_time_minus_10 = paris_time - timedelta(minutes=10)
    
    # Convert to Jakarta time
    jakarta_tz = timezone('Asia/Jakarta')
    jakarta_time = paris_time_minus_10.astimezone(jakarta_tz)
    
    return jakarta_time.strftime("%H:%M")

def scrape_rereyano():
    url = "https://rereyano.ru/"
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Find the first textarea which contains the match listings
    textarea = soup.find("textarea")
    if not textarea:
        raise ValueError("No textarea found on the page")
    
    lines = textarea.text.strip().split("\n")
    
    matches = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Match the pattern for a game line
        match_pattern = re.match(r'(\d{2}-\d{2}-\d{4}) \(([\d:]+)\) (.+?) : (.+?)(?: - (.+?))?(?:\s*\(CH\d+\w+\)\s*)*$', line)
        if not match_pattern:
            continue
        
        date_str, time_str, league, team_or1, team2_opt = match_pattern.groups()
        league = league.strip()
        team_or1 = team_or1.strip()
        team2 = team2_opt.strip() if team2_opt else ""
        
        # Extract channels
        channel_matches = re.findall(r'\(CH(\d+)(\w+)\)', line)
        servers = []
        for num, suffix in channel_matches:
            server_url = f"https://multi.govoet.my.id/?envivo={num}"
            label = f"CH-{suffix.upper()}"
            servers.append({"url": server_url, "label": label})
        
        if not servers:
            continue  # Skip if no servers
        
        # Convert date to YYYY-MM-DD
        date_parts = date_str.split("-")
        kickoff_date = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
        
        # Convert kickoff time to Jakarta time
        kickoff_date_jakarta, kickoff_time_jakarta = convert_paris_to_jakarta(kickoff_date, time_str)
        
        # Calculate match_time (10 minutes before kickoff) in Jakarta time
        match_time_jakarta = parse_time_minus_10(time_str, kickoff_date)
        match_date_jakarta = kickoff_date_jakarta
        
        # Create ID
        id_str = league.replace(" ", "") + "-" + team_or1.replace(" ", "")
        if team2:
            id_str += "-" + team2.replace(" ", "")
        
        match_data = {
            "id": id_str,
            "league": league,
            "team1": {"name": team_or1},
            "team2": {"name": team2} if team2 else {"name": ""},
            "kickoff_date": kickoff_date_jakarta,
            "kickoff_time": kickoff_time_jakarta,
            "match_date": match_date_jakarta,
            "match_time": match_time_jakarta,
            "duration": "3.5",
            "servers": servers
        }
        
        matches.append(match_data)
    
    # Save to rere.json
    with open("rere.json", "w", encoding="utf-8") as f:
        json.dump(matches, f, indent=2)
    
    return matches

if __name__ == "__main__":
    data = scrape_rereyano()
    print("Data has been scraped and saved to rere.json")