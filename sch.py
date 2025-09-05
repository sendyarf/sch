import json
import os
from typing import List, Dict, Any
import re
from fuzzywuzzy import fuzz
from datetime import datetime, timedelta
import logging
import requests  # Ditambahkan untuk request ke GitHub API
import copy      # Ditambahkan untuk menyalin data secara mendalam

# Set up logging to console and file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('merge.log'),
        logging.StreamHandler()
    ]
)

# --- FUNGSI BARU UNTUK MENGAMBIL LOGO DARI GITHUB ---
def get_github_logos() -> Dict[str, str]:
    """
    Mengambil daftar logo dari repositori GitHub dan membuat mapping.
    Key: nama tim yang dinormalisasi (contoh: 'ac-milan')
    Value: URL mentah ke gambar logo
    """
    owner = "sendyarf"
    repo = "logos"
    folder_path = "Logos"
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{folder_path}"
    logo_map = {}

    logging.info(f"Mengambil daftar logo dari GitHub: {api_url}")
    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        files = response.json()
        
        for item in files:
            if item['type'] == 'file' and item['name'].lower().endswith(('.png', '.jpg', '.svg')):
                # Menggunakan nama file tanpa ekstensi sebagai key
                # Contoh: 'ac-milan.png' -> 'ac-milan'
                file_name_key = os.path.splitext(item['name'])[0].lower()
                logo_map[file_name_key] = item['download_url']
        
        logging.info(f"Berhasil mengambil {len(logo_map)} logo dari GitHub.")
        return logo_map
    except requests.exceptions.RequestException as e:
        logging.error(f"Gagal mengambil logo dari GitHub: {e}")
        return {} # Mengembalikan dictionary kosong jika gagal


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
    seen_urls = {server['url'] for server in existing_servers}
    result = existing_servers.copy()
    for server in new_servers:
        if server['url'] not in seen_urls:
            seen_urls.add(server['url'])
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

# --- BAGIAN UTAMA SCRIPT ---

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

# Process rere.json
for item in rere_data:
    match_idx = find_match_rere_manual(schedule, item, threshold=0.8)
    if match_idx != -1:
        schedule[match_idx]['servers'] = remove_duplicate_servers(schedule[match_idx].get('servers', []), item.get('servers', []))
        logging.info(f"Merged servers for {item['id']} from rere.json")
    else:
        schedule.append(item)
        logging.info(f"Added new entry {item['id']} from rere.json")

# Process inplaynet.json
for item in inplaynet_data:
    match_idx = find_match_inplaynet(schedule, item, threshold=0.8)
    if match_idx != -1:
        schedule[match_idx]['servers'] = remove_duplicate_servers(schedule[match_idx].get('servers', []), item.get('servers', []))
        logging.info(f"Merged servers for {item['id']} from inplaynet.json")
    else:
        schedule.append(item)
        logging.info(f"Added new entry {item['id']} from inplaynet.json")

# Process sportsonline.json
for item in sportsonline_data:
    match_idx = find_match_sportsonline(schedule, item, threshold=0.8)
    if match_idx != -1:
        schedule[match_idx]['servers'] = remove_duplicate_servers(schedule[match_idx].get('servers', []), item.get('servers', []))
        logging.info(f"Merged servers for {item['id']} from sportsonline.json")
    else:
        logging.info(f"Skipped {item['id']} from sportsonline.json (no match)")

# Process manual.json
for item in manual_data:
    if item['id'].startswith('tes'):
        schedule.append(item)
        logging.info(f"Force added new entry {item['id']} from manual.json")
        continue
    match_idx = find_match_rere_manual(schedule, item, threshold=0.8)
    if match_idx != -1:
        schedule[match_idx]['servers'] = remove_duplicate_servers(schedule[match_idx].get('servers', []), item.get('servers', []))
        logging.info(f"Merged servers for {item['id']} from manual.json")
    else:
        schedule.append(item)
        logging.info(f"Added new entry {item['id']} from manual.json")

# Adjust match_time to be 10 minutes earlier than kickoff_time
for item in schedule:
    item['match_date'], item['match_time'] = subtract_ten_minutes(item['kickoff_date'], item['kickoff_time'])

# Ensure output directory exists
output_dir = 'sch'
os.makedirs(output_dir, exist_ok=True)

# --- MENYIMPAN FILE schedule.json (OUTPUT ASLI) ---
output_path = os.path.join(output_dir, 'schedule.json')
try:
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, indent=2, ensure_ascii=False)
    logging.info(f"Berhasil menyimpan output asli ke {output_path}")
except Exception as e:
    logging.error(f"Gagal menyimpan schedule.json: {str(e)}")


# --- LOGIKA BARU: MEMBUAT DAN MENYIMPAN schedulegvt.json DENGAN LOGO ---
logging.info("Memulai proses pembuatan schedulegvt.json dengan logo.")

# 1. Panggil fungsi untuk mendapatkan mapping logo dari GitHub
logo_map = get_github_logos()

# Lanjutkan hanya jika berhasil mendapatkan logo
if logo_map:
    schedule_with_logos = []
    for item in schedule:
        # 2. Normalisasi nama tim agar cocok dengan key di logo_map
        # Contoh: "AC Milan" -> "ac milan" -> "ac-milan"
        norm_team1_key = normalize_name(item['team1']['name']).replace(' ', '-')
        norm_team2_key = normalize_name(item['team2']['name']).replace(' ', '-')

        # 3. Cari logo di dalam map
        logo1_url = logo_map.get(norm_team1_key)
        logo2_url = logo_map.get(norm_team2_key)

        # 4. Jika KEDUA logo ditemukan, tambahkan ke daftar baru
        if logo1_url and logo2_url:
            # Gunakan deepcopy untuk memastikan data asli tidak berubah
            new_item = copy.deepcopy(item)
            new_item['team1']['logo'] = logo1_url
            new_item['team2']['logo'] = logo2_url
            schedule_with_logos.append(new_item)
            logging.debug(f"Logo ditemukan untuk '{item['id']}'. Menambahkan ke schedulegvt.json.")
        else:
            logging.debug(f"Melewatkan '{item['id']}' untuk schedulegvt.json (logo tidak ditemukan).")
            if not logo1_url:
                logging.debug(f"  - Logo tidak ditemukan untuk tim 1: {item['team1']['name']} (key: {norm_team1_key})")
            if not logo2_url:
                logging.debug(f"  - Logo tidak ditemukan untuk tim 2: {item['team2']['name']} (key: {norm_team2_key})")
    
    # 5. Simpan daftar baru ke file schedulegvt.json
    output_gvt_path = os.path.join(output_dir, 'schedulegvt.json')
    try:
        with open(output_gvt_path, 'w', encoding='utf-8') as f:
            json.dump(schedule_with_logos, f, indent=2, ensure_ascii=False)
        logging.info(f"Berhasil menyimpan {len(schedule_with_logos)} pertandingan dengan logo ke {output_gvt_path}")
    except Exception as e:
        logging.error(f"Gagal menyimpan schedulegvt.json: {str(e)}")
else:
    logging.warning("Tidak dapat mengambil peta logo dari GitHub. Melewatkan pembuatan schedulegvt.json.")

print("\nProses selesai.")
