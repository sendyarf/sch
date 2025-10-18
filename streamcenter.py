import requests
import json
from datetime import datetime
import pytz
import base64
import os

def scrape_and_convert_data():
    # URL API
    url = "https://backendstreamcenter.youshop.pro:488/api/Parties?pageNumber=1&pageSize=500"
    
    try:
        # Headers untuk menghindari blokir
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Request data
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse JSON
        data = response.json()
        
        # Timezone setup
        london_tz = pytz.timezone('Europe/London')
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        
        converted_data = []
        
        for item in data:
            try:
                # Parse nama tim dari name field
                name = item.get('name', '')
                team1_name = ""
                team2_name = ""
                
                # Cek jika format "Team1 vs Team2"
                if name and ' vs ' in name:
                    name_parts = name.split(' vs ')
                    if len(name_parts) == 2:
                        team1_name = name_parts[0].strip()
                        team2_name = name_parts[1].strip()
                
                # Cek jika format "Team1 at Team2" (dari gameName)
                elif item.get('gameName') and ' at ' in item.get('gameName', ''):
                    game_name = item.get('gameName', '')
                    teams = game_name.split(' at ')
                    if len(teams) == 2:
                        team1_name = teams[1].strip()  # Home team
                        team2_name = teams[0].strip()  # Away team
                
                # Jika tidak ada format vs/at, gunakan name sebagai team1 dan team2 kosong
                else:
                    team1_name = name.strip() if name else "Event"
                    team2_name = ""  # Team2 dikosongkan untuk event seperti F1, MotoGP, dll
                
                # Konversi waktu dari London ke Jakarta
                begin_time_str = item.get('beginPartie')
                end_time_str = item.get('endPartie')
                
                kickoff_date = ""
                kickoff_time = ""
                duration = "3.5"
                
                if begin_time_str:
                    try:
                        # Parse waktu London
                        begin_utc = datetime.fromisoformat(begin_time_str.replace('Z', '+00:00'))
                        begin_london = begin_utc.astimezone(london_tz)
                        
                        # Konversi ke Jakarta
                        begin_jakarta = begin_london.astimezone(jakarta_tz)
                        
                        # Format tanggal dan waktu
                        kickoff_date = begin_jakarta.strftime('%Y-%m-%d')
                        kickoff_time = begin_jakarta.strftime('%H:%M')
                        
                        # Hitung durasi
                        if end_time_str:
                            try:
                                end_utc = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                                end_london = end_utc.astimezone(london_tz)
                                end_jakarta = end_london.astimezone(jakarta_tz)
                                
                                # Hitung durasi dalam jam
                                duration_hours = (end_jakarta - begin_jakarta).total_seconds() / 3600
                                duration = f"{duration_hours:.1f}"
                            except:
                                pass
                    except Exception as time_error:
                        print(f"Error processing time for item {item.get('id')}: {time_error}")
                
                # Parse servers dari videoUrl
                servers = []
                video_url = item.get('videoUrl', '')
                if video_url:
                    # Split multiple streams
                    stream_parts = video_url.split(';')
                    for stream in stream_parts:
                        stream = stream.strip()
                        if '<' in stream:
                            url_part, label_part = stream.split('<', 1)
                            url_part = url_part.strip()
                            label_part = label_part.strip()
                            
                            # Encode URL ke base64 seperti contoh
                            url_bytes = url_part.encode('utf-8')
                            base64_bytes = base64.b64encode(url_bytes)
                            base64_url = base64_bytes.decode('utf-8')
                            
                            # Format URL dengan base64 encoded
                            encoded_url = f"https://multi.govoet.my.id/?iframe={base64_url}"
                            
                            # Format label
                            if 'arabic' in label_part.lower() or 'ar' in label_part.lower():
                                label = "CH-AR"
                            elif 'english' in label_part.lower() or 'en' in label_part.lower():
                                label = "CH-EN"
                            elif 'french' in label_part.lower() or 'fr' in label_part.lower():
                                label = "CH-FR"
                            elif 'spanish' in label_part.lower() or 'es' in label_part.lower():
                                label = "CH-ES"
                            else:
                                label = f"CH-{label_part.upper()}"
                            
                            servers.append({
                                "url": encoded_url,
                                "label": label
                            })
                
                # Buat data dalam format template dengan id dan league kosong
                converted_item = {
                    "id": "",  # Dikosongkan
                    "league": "",  # Dikosongkan
                    "team1": {
                        "name": team1_name
                    },
                    "team2": {
                        "name": team2_name
                    },
                    "kickoff_date": kickoff_date,
                    "kickoff_time": kickoff_time,
                    "match_date": kickoff_date,
                    "match_time": kickoff_time,
                    "duration": duration,
                    "servers": servers
                }
                
                converted_data.append(converted_item)
                
            except Exception as e:
                print(f"Error processing item {item.get('id')}: {e}")
                continue
        
        return converted_data
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return []

# Jalankan fungsi
if __name__ == "__main__":
    result = scrape_and_convert_data()
    
    # Print hasil ke console
    print(f"Berhasil mengkonversi {len(result)} pertandingan")
    
    # Simpan ke file streamcenter.json
    with open('streamcenter.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print("Data disimpan ke streamcenter.json")
    
    # Print contoh data untuk debugging
    if result:
        print("\nContoh data yang dihasilkan:")
        for i, item in enumerate(result[:5]):
            print(f"{i+1}. Team1: '{item['team1']['name']}', Team2: '{item['team2']['name']}'")
    
    # Cari dan tampilkan data F1 khusus untuk debugging
    f1_events = [item for item in result if 'F1' in item['team1']['name']]
    if f1_events:
        print("\nEvent F1 yang ditemukan:")
        for i, event in enumerate(f1_events):
            print(f"{i+1}. {event['team1']['name']} - {event['kickoff_date']} {event['kickoff_time']}")