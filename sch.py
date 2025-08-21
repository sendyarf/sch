import json
import os
from typing import List, Dict, Any
import re
from fuzzywuzzy import fuzz
from datetime import datetime, timedelta
import logging

# Set up logging to console and file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('merge.log'),
        logging.StreamHandler()
    ]
)

# Function to subtract 10 minutes from a time, adjusting date if necessary
def subtract_ten_minutes(date_str: str, time_str: str) -> tuple[str, str]:
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        dt = dt - timedelta(minutes=10)
        new_date = dt.strftime("%Y-%m-%d")
        new_time = dt.strftime("%H:%M")
        return new_date, new_time
    except ValueError as e:
        logging.error(f"Error processing date/time {date_str} {time_str}: {str(e)}")
        return date_str, time_str  # Return original values in case of error

# Function to normalize names
def normalize_name(name: str) -> str:
    name = re.sub(r'\s*\([^)]*\)', '', name)
    name = name.lower().strip()
    accents = {'ñ': 'n', 'é': 'e', 'í': 'i', 'ó': 'o', 'á': 'a', 'ú': 'u'}
    for acc, repl in accents.items():
        name = name.replace(acc, repl)
    return name

# Function to remove duplicate servers
def remove_duplicate_servers(existing_servers: List[Dict[str, str]], new_servers: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    result = existing_servers.copy()
    for server in new_servers:
        server_tuple = (server['url'], server['label'])
        if server_tuple not in seen:
            seen.add(server_tuple)
            result.append(server)
            logging.debug(f"Added server {server['url']} ({server['label']})")
        else:
            logging.debug(f"Skipped duplicate server {server['url']} ({server['label']})")
    return result

# Function to translate data
def translate_data(data: List[Dict[str, Any]], trans_dict: Dict[str, str]) -> List[Dict[str, Any]]:
    translated = []
    for item in data:
        trans_item = item.copy()
        trans_item['league'] = trans_dict.get(trans_item['league'], trans_item['league'])
        trans_item['team1']['name'] = trans_dict.get(trans_item['team1']['name'], trans_item['team1']['name'])
        trans_item['team2']['name'] = trans_dict.get(trans_item['team2']['name'], trans_item['team2']['name'])
        translated.append(trans_item)
    return translated

# Function to calculate time difference in minutes
def time_difference(time1: str, time2: str, date1: str, date2: str) -> float:
    try:
        dt1 = datetime.strptime(f"{date1} {time1}", "%Y-%m-%d %H:%M")
        dt2 = datetime.strptime(f"{date2} {time2}", "%Y-%m-%d %H:%M")
        diff = abs((dt1 - dt2).total_seconds() / 60)
        return diff
    except ValueError:
        return float('inf')

# Function for strict matching (fallback)
def strict_match_rere_manual(schedule: List[Dict[str, Any]], item: Dict[str, Any]) -> int:
    norm_league = normalize_name(item['league'])
    norm_team1 = normalize_name(item['team1']['name'])
    norm_team2 = normalize_name(item['team2']['name'])
    date = item['kickoff_date']
    time = item['kickoff_time']
    for idx, sch in enumerate(schedule):
        sch_norm_league = normalize_name(sch['league'])
        sch_norm_team1 = normalize_name(sch['team1']['name'])
        sch_norm_team2 = normalize_name(sch['team2']['name'])
        if (sch_norm_league == norm_league and
            ((sch_norm_team1 == norm_team1 and sch_norm_team2 == norm_team2) or
             (sch_norm_team1 == norm_team2 and sch_norm_team2 == norm_team1)) and
            sch['kickoff_date'] == date and
            sch['kickoff_time'] == time):
            logging.debug(f"Strict match found for {item['id']} with {sch['id']}")
            return idx
    return -1

def strict_match_inplaynet(schedule: List[Dict[str, Any]], item: Dict[str, Any]) -> int:
    norm_league = normalize_name(item['league'])
    norm_team1 = normalize_name(item['team1']['name'])
    norm_team2 = normalize_name(item['team2']['name'])
    for idx, sch in enumerate(schedule):
        sch_norm_league = normalize_name(sch['league'])
        sch_norm_team1 = normalize_name(sch['team1']['name'])
        sch_norm_team2 = normalize_name(sch['team2']['name'])
        if (sch_norm_league == norm_league and
            ((sch_norm_team1 == norm_team1 and sch_norm_team2 == norm_team2) or
             (sch_norm_team1 == norm_team2 and sch_norm_team2 == norm_team1))):
            logging.debug(f"Strict match found for {item['id']} with {sch['id']}")
            return idx
    return -1

def strict_match_sportsonline(schedule: List[Dict[str, Any]], item: Dict[str, Any]) -> int:
    norm_team1 = normalize_name(item['team1']['name'])
    norm_team2 = normalize_name(item['team2']['name'])
    time = item['kickoff_time']
    for idx, sch in enumerate(schedule):
        sch_norm_team1 = normalize_name(sch['team1']['name'])
        sch_norm_team2 = normalize_name(sch['team2']['name'])
        if (((sch_norm_team1 == norm_team1 and sch_norm_team2 == norm_team2) or
             (sch_norm_team1 == norm_team2 and sch_norm_team2 == norm_team1)) and
            sch['kickoff_time'] == time):
            logging.debug(f"Strict match found for {item['id']} with {sch['id']}")
            return idx
    return -1

# Function for fuzzy matching (rere.json and manual.json)
def find_match_rere_manual(schedule: List[Dict[str, Any]], item: Dict[str, Any], threshold: float = 0.8) -> int:
    best_match_idx = -1
    best_score = 0.0
    norm_league = normalize_name(item['league'])
    norm_team1 = normalize_name(item['team1']['name'])
    norm_team2 = normalize_name(item['team2']['name'])
    date = item['kickoff_date']
    time = item['kickoff_time']

    for idx, sch in enumerate(schedule):
        sch_norm_league = normalize_name(sch['league'])
        sch_norm_team1 = normalize_name(sch['team1']['name'])
        sch_norm_team2 = normalize_name(sch['team2']['name'])
        
        league_score = fuzz.token_sort_ratio(norm_league, sch_norm_league) / 100.0
        if league_score < 0.9:
            logging.debug(f"Skipping {item['id']} vs {sch['id']} due to low league_score={league_score:.2f}")
            continue
        
        team1_score = max(fuzz.token_sort_ratio(norm_team1, sch_norm_team1), fuzz.partial_ratio(norm_team1, sch_norm_team1)) / 100.0
        team2_score = max(fuzz.token_sort_ratio(norm_team2, sch_norm_team2), fuzz.partial_ratio(norm_team2, sch_norm_team2)) / 100.0
        team_score = max(
            (team1_score + team2_score) / 2,
            (max(fuzz.token_sort_ratio(norm_team1, sch_norm_team2), fuzz.partial_ratio(norm_team1, sch_norm_team2)) +
             max(fuzz.token_sort_ratio(norm_team2, sch_norm_team1), fuzz.partial_ratio(norm_team2, sch_norm_team1))) / 200.0
        )
        
        date_score = 1.0 if date == sch['kickoff_date'] else 0.0
        time_diff = time_difference(time, sch['kickoff_time'], date, sch['kickoff_date'])
        time_score = 1.0 if time_diff <= 30 else max(0.0, 1.0 - time_diff / 120.0)

        total_score = (0.3 * league_score + 0.6 * team_score + 0.05 * date_score + 0.05 * time_score)
        
        logging.debug(
            f"Comparing {item['id']} with {sch['id']}: league_score={league_score:.2f}, team_score={team_score:.2f}, "
            f"date_score={date_score:.2f}, time_score={time_score:.2f}, total_score={total_score:.2f}"
        )
        
        if total_score >= threshold and total_score > best_score:
            best_score = total_score
            best_match_idx = idx

    # Fallback to strict matching
    if best_match_idx == -1:
        strict_idx = strict_match_rere_manual(schedule, item)
        if strict_idx != -1:
            logging.debug(f"Fallback to strict match for {item['id']}")
            return strict_idx

    return best_match_idx

# Function for fuzzy matching (inplaynet.json)
def find_match_inplaynet(schedule: List[Dict[str, Any]], item: Dict[str, Any], threshold: float = 0.8) -> int:
    best_match_idx = -1
    best_score = 0.0
    norm_league = normalize_name(item['league'])
    norm_team1 = normalize_name(item['team1']['name'])
    norm_team2 = normalize_name(item['team2']['name'])

    for idx, sch in enumerate(schedule):
        sch_norm_league = normalize_name(sch['league'])
        sch_norm_team1 = normalize_name(sch['team1']['name'])
        sch_norm_team2 = normalize_name(sch['team2']['name'])
        
        league_score = fuzz.token_sort_ratio(norm_league, sch_norm_league) / 100.0
        if league_score < 0.9:
            logging.debug(f"Skipping {item['id']} vs {sch['id']} due to low league_score={league_score:.2f}")
            continue
        
        team1_score = max(fuzz.token_sort_ratio(norm_team1, sch_norm_team1), fuzz.partial_ratio(norm_team1, sch_norm_team1)) / 100.0
        team2_score = max(fuzz.token_sort_ratio(norm_team2, sch_norm_team2), fuzz.partial_ratio(norm_team2, sch_norm_team2)) / 100.0
        team_score = max(
            (team1_score + team2_score) / 2,
            (max(fuzz.token_sort_ratio(norm_team1, sch_norm_team2), fuzz.partial_ratio(norm_team1, sch_norm_team2)) +
             max(fuzz.token_sort_ratio(norm_team2, sch_norm_team1), fuzz.partial_ratio(norm_team2, sch_norm_team1))) / 200.0
        )

        total_score = (0.3 * league_score + 0.7 * team_score)
        
        logging.debug(
            f"Comparing {item['id']} with {sch['id']}: league_score={league_score:.2f}, team_score={team_score:.2f}, "
            f"total_score={total_score:.2f}"
        )
        
        if total_score >= threshold and total_score > best_score:
            best_score = total_score
            best_match_idx = idx

    # Fallback to strict matching
    if best_match_idx == -1:
        strict_idx = strict_match_inplaynet(schedule, item)
        if strict_idx != -1:
            logging.debug(f"Fallback to strict match for {item['id']}")
            return strict_idx

    return best_match_idx

# Function for fuzzy matching (sportsonline.json)
def find_match_sportsonline(schedule: List[Dict[str, Any]], item: Dict[str, Any], threshold: float = 0.8) -> int:
    best_match_idx = -1
    best_score = 0.0
    norm_team1 = normalize_name(item['team1']['name'])
    norm_team2 = normalize_name(item['team2']['name'])
    time = item['kickoff_time']
    date = item['kickoff_date'] if 'kickoff_date' in item else "1970-01-01"

    for idx, sch in enumerate(schedule):
        sch_norm_team1 = normalize_name(sch['team1']['name'])
        sch_norm_team2 = normalize_name(sch['team2']['name'])
        
        team1_score = max(fuzz.token_sort_ratio(norm_team1, sch_norm_team1), fuzz.partial_ratio(norm_team1, sch_norm_team1)) / 100.0
        team2_score = max(fuzz.token_sort_ratio(norm_team2, sch_norm_team2), fuzz.partial_ratio(norm_team2, sch_norm_team2)) / 100.0
        team_score = max(
            (team1_score + team2_score) / 2,
            (max(fuzz.token_sort_ratio(norm_team1, sch_norm_team2), fuzz.partial_ratio(norm_team1, sch_norm_team2)) +
             max(fuzz.token_sort_ratio(norm_team2, sch_norm_team1), fuzz.partial_ratio(norm_team2, sch_norm_team1))) / 200.0
        )
        
        time_diff = time_difference(time, sch['kickoff_time'], date, sch['kickoff_date'])
        time_score = 1.0 if time_diff <= 30 else max(0.0, 1.0 - time_diff / 120.0)

        total_score = (0.4 * time_score + 0.6 * team_score)
        
        logging.debug(
            f"Comparing {item['id']} with {sch['id']}: team_score={team_score:.2f}, time_score={time_score:.2f}, "
            f"total_score={total_score:.2f}"
        )
        
        if total_score >= threshold and total_score > best_score:
            best_score = total_score
            best_match_idx = idx

    # Fallback to strict matching
    if best_match_idx == -1:
        strict_idx = strict_match_sportsonline(schedule, item)
        if strict_idx != -1:
            logging.debug(f"Fallback to strict match for {item['id']}")
            return strict_idx

    return best_match_idx

# Load translation dict
trans_file = 'translate/en.json'
trans_dict = {}
if os.path.exists(trans_file):
    with open(trans_file, 'r', encoding='utf-8') as f:
        trans_dict = json.load(f)
    logging.info(f"Loaded translation dictionary with {len(trans_dict)} entries")
else:
    logging.warning("Translation file 'translate/en.json' not found")

# Load all JSON files
try:
    with open('event.json', 'r', encoding='utf-8') as f:
        event_data = json.load(f)
    event_data = translate_data(event_data, trans_dict)
    logging.info(f"Loaded {len(event_data)} entries from event.json")
except FileNotFoundError:
    logging.error("File 'event.json' not found")
    event_data = []

try:
    with open('rere.json', 'r', encoding='utf-8') as f:
        rere_data = json.load(f)
    rere_data = translate_data(rere_data, trans_dict)
    logging.info(f"Loaded {len(rere_data)} entries from rere.json")
except FileNotFoundError:
    logging.warning("File 'rere.json' not found")
    rere_data = []

try:
    with open('inplaynet.json', 'r', encoding='utf-8') as f:
        inplaynet_data = json.load(f)
    inplaynet_data = translate_data(inplaynet_data, trans_dict)
    logging.info(f"Loaded {len(inplaynet_data)} entries from inplaynet.json")
except FileNotFoundError:
    logging.warning("File 'inplaynet.json' not found")
    inplaynet_data = []

try:
    with open('sportsonline.json', 'r', encoding='utf-8') as f:
        sportsonline_data = json.load(f)
    sportsonline_data = translate_data(sportsonline_data, trans_dict)
    logging.info(f"Loaded {len(sportsonline_data)} entries from sportsonline.json")
except FileNotFoundError:
    logging.warning("File 'sportsonline.json' not found")
    sportsonline_data = []

try:
    with open('manual.json', 'r', encoding='utf-8') as f:
        manual_data = json.load(f)
    manual_data = translate_data(manual_data, trans_dict)
    logging.info(f"Loaded {len(manual_data)} entries from manual.json")
except FileNotFoundError:
    logging.error("File 'manual.json' not found")
    manual_data = []

# Initialize schedule with event.json
schedule: List[Dict[str, Any]] = event_data.copy()
logging.info(f"Initialized schedule with {len(schedule)} entries from event.json")

# Log initial schedule for debugging
logging.debug(f"Initial schedule content: {json.dumps(schedule, indent=2)}")

# Process rere.json
for item in rere_data:
    match_idx = find_match_rere_manual(schedule, item, threshold=0.8)
    if match_idx != -1:
        schedule[match_idx]['servers'] = remove_duplicate_servers(schedule[match_idx]['servers'], item['servers'])
        logging.info(f"Merged servers for {item['id']} from rere.json")
    else:
        schedule.append(item)
        logging.info(f"Added new entry {item['id']} from rere.json")

# Process inplaynet.json
for item in inplaynet_data:
    match_idx = find_match_inplaynet(schedule, item, threshold=0.8)
    if match_idx != -1:
        schedule[match_idx]['servers'] = remove_duplicate_servers(schedule[match_idx]['servers'], item['servers'])
        logging.info(f"Merged servers for {item['id']} from inplaynet.json")
    else:
        schedule.append(item)
        logging.info(f"Added new entry {item['id']} from inplaynet.json")

# Process sportsonline.json
for item in sportsonline_data:
    match_idx = find_match_sportsonline(schedule, item, threshold=0.8)
    if match_idx != -1:
        schedule[match_idx]['servers'] = remove_duplicate_servers(schedule[match_idx]['servers'], item['servers'])
        logging.info(f"Merged servers for {item['id']} from sportsonline.json")
    else:
        logging.info(f"Skipped {item['id']} from sportsonline.json (no match)")

# Process manual.json
for item in manual_data:
    if item['id'].startswith('tes'):  # Force entries with 'tes' in id to be added as new
        schedule.append(item)
        logging.info(f"Force added new entry {item['id']} from manual.json")
        continue
    match_idx = find_match_rere_manual(schedule, item, threshold=0.8)
    if match_idx != -1:
        schedule[match_idx]['servers'] = remove_duplicate_servers(schedule[match_idx]['servers'], item['servers'])
        logging.info(f"Merged servers for {item['id']} from manual.json")
    else:
        schedule.append(item)
        logging.info(f"Added new entry {item['id']} from manual.json")

# Adjust match_time to be 10 minutes earlier than kickoff_time
for item in schedule:
    item['match_date'], item['match_time'] = subtract_ten_minutes(item['kickoff_date'], item['kickoff_time'])
    logging.debug(f"Adjusted {item['id']}: match_date={item['match_date']}, match_time={item['match_time']}")

# Log final schedule for debugging
logging.debug(f"Final schedule content: {json.dumps(schedule, indent=2)}")

# Ensure output directory exists
output_dir = 'sch'
os.makedirs(output_dir, exist_ok=True)

# Save to schedule.json
output_path = os.path.join(output_dir, 'schedule.json')
try:
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, indent=2, ensure_ascii=False)
    logging.info(f"Saved output to {output_path}")
except Exception as e:
    logging.error(f"Failed to save schedule.json: {str(e)}")
