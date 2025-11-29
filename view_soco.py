import json

def view_soco_json():
    """Display soco.json content in a readable format"""
    
    try:
        with open('soco.json', 'r', encoding='utf-8') as f:
            matches = json.load(f)
        
        print("=" * 70)
        print(f"📋 SOCO.JSON - Total Matches: {len(matches)}")
        print("=" * 70)
        
        if not matches:
            print("❌ No matches found in file")
            return
        
        for idx, match in enumerate(matches, 1):
            print(f"\n{'='*70}")
            print(f"🏆 Match #{idx}")
            print(f"{'='*70}")
            print(f"ID          : {match.get('id', 'N/A')}")
            print(f"League      : {match.get('league', 'N/A')}")
            print(f"Home Team   : {match.get('team1', {}).get('name', 'N/A')}")
            print(f"Away Team   : {match.get('team2', {}).get('name', 'N/A')}")
            print(f"Date        : {match.get('match_date', 'N/A')}")
            print(f"Time        : {match.get('match_time', 'N/A')}")
            print(f"Duration    : {match.get('duration', 'N/A')} hours")
            
            servers = match.get('servers', [])
            print(f"\n📺 Servers ({len(servers)} available):")
            print("-" * 70)
            
            for s_idx, server in enumerate(servers, 1):
                print(f"\n  [{s_idx}] {server.get('label', 'N/A')}")
                url = server.get('url', 'N/A')
                if len(url) > 60:
                    print(f"      URL: {url[:60]}...")
                else:
                    print(f"      URL: {url}")
        
        print("\n" + "=" * 70)
        print("✅ Display complete")
        print("=" * 70)
        
    except FileNotFoundError:
        print("❌ Error: soco.json not found")
        print("Run scrape_soco.py or scrape_soco_selenium.py first")
    except json.JSONDecodeError:
        print("❌ Error: Invalid JSON format in soco.json")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    view_soco_json()
