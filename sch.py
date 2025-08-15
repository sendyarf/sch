import json
import os
from typing import List, Dict, Any
import re
from fuzzywuzzy import fuzz
from datetime import datetime, timedelta
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Function to normalize names
def normalize_name(name: str) -> str:
    name = re.sub(r'\s*\([^)]*\)', '', name)  # Remove parentheses
    name = name.lower().strip()
    accents = {'ñ': 'n', 'é': 'e', 'í': 'i', 'ó': 'o', 'á': 'a', 'ú': 'u'}
    for acc, repl in accents.items():
        name = name.replace(acc, repl)
    return name

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
            return idx
    return -1

# Function for fuzzy matching (rere.json and manual.json)
def find_match_rere_manual(schedule: List[Dict[str, Any]], item: Dict[str, Any], threshold: float = 0.65) -> int:
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
        
        league_score = max(fuzz.token_sort_ratio(norm_league, sch_norm_league), fuzz.partial_ratio(norm_league, sch_norm_league)) / 100.0
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

        total_score = (0.1 * league_score + 0.5 * team_score + 0.2 * date_score + 0.2 * time_score)
        
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
def find_match_inplaynet(schedule: List[Dict[str, Any]], item: Dict[str, Any], threshold: float = 0.65) -> int:
    best_match_idx = -1
    best_score = 0.0
    norm_league = normalize_name(item['league'])
    norm_team1 = normalize_name(item['team1']['name'])
    norm_team2 = normalize_name(item['team2']['name'])

    for idx, sch in enumerate(schedule):
        sch_norm_league = normalize_name(sch['league'])
        sch_norm_team1 = normalize_name(sch['team1']['name'])
        sch_norm_team2 = normalize_name(sch['team2']['name'])
        
        league_score = max(fuzz.token_sort_ratio(norm_league, sch_norm_league), fuzz.partial_ratio(norm_league, sch_norm_league)) / 100.0
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
def find_match_sportsonline(schedule: List[Dict[str, Any]], item: Dict[str, Any], threshold: float = 0.65) -> int:
    best_match_idx = -1
    best_score = 0.0
    norm_team1 = normalize_name(item['team1']['name'])
    norm_team2 = normalize_name(item['team2']['name'])
    time = item['kickoff_time']
    date = item['kickoff_date'] if item['kickoff_date'] else "1970-01-01"

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

# Load all JSON files
with open('event.json', 'r', encoding='utf-8') as f:
    event_data = json.load(f)
event_data = translate_data(event_data, trans_dict)

with open('rere.json', 'r', encoding='utf-8') as f:
    rere_data = json.load(f)
rere_data = translate_data(rere_data, trans_dict)

with open('inplaynet.json', 'r', encoding='utf-8') as f:
    inplaynet_data = json.load(f)
inplaynet_data = translate_data(inplaynet_data, trans_dict)

with open('sportsonline.json', 'r', encoding='utf-8') as f:
    sportsonline_data = json.load(f)
sportsonline_data = translate_data(sportsonline_data, trans_dict)

with open('manual.json', 'r', encoding='utf-8') as f:
    manual_data = json.load(f)
manual_data = translate_data(manual_data, trans_dict)

# Initialize schedule with event.json
schedule: List[Dict[str, Any]] = event_data.copy()

# Process rere.json
for item in rere_data:
    match_idx = find_match_rere_manual(schedule, item, threshold=0.65)
    if match_idx != -1:
        schedule[match_idx]['servers'].extend(item['servers'])
        logging.info(f"Merged servers for {item['id']} from rere.json")
    else:
        schedule.append(item)
        logging.info(f"Added new entry {item['id']} from rere.json")

# Process inplaynet.json
for item in inplaynet_data:
    match_idx = find_match_inplaynet(schedule, item, threshold=0.65)
    if match_idx != -1:
        schedule[match_idx]['servers'].extend(item['servers'])
        logging.info(f"Merged servers for {item['id']} from inplaynet.json")
    else:
        schedule.append(item)
        logging.info(f"Added new entry {item['id']} from inplaynet.json")

# Process sportsonline.json
for item in sportsonline_data:
    match_idx = find_match_sportsonline(schedule, item, threshold=0.65)
    if match_idx != -1:
        schedule[match_idx]['servers'].extend(item['servers'])
        logging.info(f"Merged servers for {item['id']} from sportsonline.json")
    else:
        logging.info(f"Skipped {item['id']} from sportsonline.json (no match)")

# Process manual.json
for item in manual_data:
    match_idx = find_match_rere_manual(schedule, item, threshold=0.65)
    if match_idx != -1:
        schedule[match_idx]['servers'].extend(item['servers'])
        logging.info(f"Merged servers for {item['id']} from manual.json")
    else:
        schedule.append(item)
        logging.info(f"Added new entry {item['id']} from manual.json")

# Save to schedule.json
with open('sch/schedule.json', 'w', encoding='utf-8') as f:
    json.dump(schedule, f, indent=2, ensure_ascii=False)
logging.info("Saved output to schedule.json")