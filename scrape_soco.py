import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime
import base64
from urllib.parse import urljoin, urlparse, parse_qs

def encode_url_to_base64(url):
    """Encode URL to base64"""
    return base64.b64encode(url.encode()).decode()

def scrape_indonesia_league_matches():
    """Scrape Indonesia league matches from socolive111.ac"""
    
    base_url = "https://socolive111.ac/"
    
    # Headers to mimic browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': base_url
    }
    
    try:
        # Request the main page
        print(f"Fetching {base_url}...")
        response = requests.get(base_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all match items
        match_items = soup.find_all('div', class_='match-item')
        
        indonesia_matches = []
        
        print(f"\nFound {len(match_items)} total matches")
        print("Filtering Indonesia league matches...\n")
        
        for match_item in match_items:
            # Check if it's Indonesia league
            comp_elem = match_item.find('div', class_='match-item__comp')
            if not comp_elem:
                continue
                
            league_name = comp_elem.text.strip()
            
            # Filter only Indonesia league
            if "Giải bóng đá VĐQG Indonesia" not in league_name:
                continue
            
            print(f"Processing: {league_name}")
            
            # Extract match URL
            link_elem = match_item.find('a', class_='link-match')
            if not link_elem or not link_elem.get('href'):
                continue
            
            match_url = urljoin(base_url, link_elem['href'])
            
            # Extract time
            time_elem = match_item.find('div', class_='match-item__time')
            time_text = time_elem.find('span').text.strip() if time_elem else ""
            
            # Extract teams
            home_team_elem = match_item.find('div', class_='name-home')
            away_team_elem = match_item.find('div', class_='name-away')
            
            home_team = home_team_elem.find('span').text.strip() if home_team_elem else "Unknown"
            away_team = away_team_elem.find('span').text.strip() if away_team_elem else "Unknown"
            
            print(f"  Match: {home_team} vs {away_team}")
            print(f"  Time: {time_text}")
            
            # Extract BLV (commentators/channels)
            blv_items = match_item.find_all('div', class_='blv-item-scl')
            
            if not blv_items:
                print(f"  No BLV channels found, skipping...")
                continue
            
            servers = []
            
            for blv_item in blv_items:
                blv_link = blv_item.find('a', class_='dropdown-item')
                if not blv_link or not blv_link.get('href'):
                    continue
                
                blv_url = urljoin(base_url, blv_link['href'])
                blv_name = blv_link.find('span').text.strip() if blv_link.find('span') else "Unknown"
                
                # Extract blv parameter from URL
                parsed_url = urlparse(blv_url)
                query_params = parse_qs(parsed_url.query)
                
                if 'blv' not in query_params:
                    continue
                
                blv_id = query_params['blv'][0]
                
                # Create the m3u8 stream URL
                stream_url = f"https://live.inplyr.com/room/{blv_id}.m3u8"
                
                # Encode to base64
                encoded_url = encode_url_to_base64(stream_url)
                
                # Create the player URL
                player_url = f"https://multi.govoet.my.id/?hls={encoded_url}"
                
                servers.append({
                    "url": player_url,
                    "label": f"CH-VN ({blv_name})"
                })
                
                print(f"  Channel: {blv_name} (BLV ID: {blv_id})")
            
            if not servers:
                print(f"  No valid servers found, skipping...")
                continue
            
            # Parse time (format: "HH:MM DD/MM")
            try:
                time_parts = time_text.split()
                if len(time_parts) >= 2:
                    time_str = time_parts[0]  # "19:00"
                    date_str = time_parts[1]  # "29/11"
                    
                    # Add current year
                    current_year = datetime.now().year
                    date_obj = datetime.strptime(f"{date_str}/{current_year} {time_str}", "%d/%m/%Y %H:%M")
                    
                    match_date = date_obj.strftime("%Y-%m-%d")
                    match_time = date_obj.strftime("%H:%M")
                else:
                    match_date = datetime.now().strftime("%Y-%m-%d")
                    match_time = "00:00"
            except:
                match_date = datetime.now().strftime("%Y-%m-%d")
                match_time = "00:00"
            
            # Create match ID from URL
            match_id = urlparse(match_url).path.split('/')[-2] if match_url else ""
            
            # Create match object
            match_data = {
                "id": match_id,
                "league": league_name,
                "team1": {
                    "name": home_team
                },
                "team2": {
                    "name": away_team
                },
                "kickoff_date": match_date,
                "kickoff_time": match_time,
                "match_date": match_date,
                "match_time": match_time,
                "duration": "3.0",
                "servers": servers
            }
            
            indonesia_matches.append(match_data)
            print(f"  Added with {len(servers)} server(s)\n")
        
        return indonesia_matches
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []
    except Exception as e:
        print(f"Error processing data: {e}")
        import traceback
        traceback.print_exc()
        return []

def save_to_json(matches, filename="soco.json"):
    """Save matches to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(matches, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Successfully saved {len(matches)} matches to {filename}")
        return True
    except Exception as e:
        print(f"❌ Error saving to file: {e}")
        return False

def main():
    print("=" * 60)
    print("SOCOLIVE INDONESIA LEAGUE SCRAPER")
    print("=" * 60)
    
    matches = scrape_indonesia_league_matches()
    
    if matches:
        save_to_json(matches, "soco.json")
        
        print("\n" + "=" * 60)
        print(f"SUMMARY: Found {len(matches)} Indonesia league match(es)")
        print("=" * 60)
        
        for i, match in enumerate(matches, 1):
            print(f"\n{i}. {match['team1']['name']} vs {match['team2']['name']}")
            print(f"   Date: {match['match_date']} {match['match_time']}")
            print(f"   Servers: {len(match['servers'])}")
    else:
        print("\n❌ No Indonesia league matches found")

if __name__ == "__main__":
    main()
