import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
import re
import base64

def scrape_inplaynet_improved():
    """
    Versi yang diperbaiki dengan:
    - Improved URL detection logic
    - Better element staleness handling
    - Enhanced iframe management
    - More robust error handling
    - Dynamic wait strategies
    """
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')  # Nonaktifkan untuk test
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--start-maximized")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-notifications')
    options.add_argument('--disable-web-security')
    options.add_argument('--allow-running-insecure-content')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 30)
    long_wait = WebDriverWait(driver, 120)

    def safe_switch_to_default():
        """Safely switch to default content"""
        try:
            driver.switch_to.default_content()
            return True
        except Exception as e:
            print(f"     Warning: Error switching to default content: {e}")
            return False

    def safe_switch_to_iframe():
        """Safely switch to sportsbook iframe"""
        try:
            safe_switch_to_default()
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, 'sportsbook_iframe')))
            return True
        except Exception as e:
            print(f"     Warning: Error switching to iframe: {e}")
            return False

    def wait_for_page_load():
        """Wait for page to fully load"""
        try:
            wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
            time.sleep(1)
            return True
        except:
            return False

    def is_detail_page_loaded(match_id):
        """Check if detail page is loaded using multiple methods"""
        try:
            # Method 1: Check URL contains match ID
            current_url = driver.current_url
            if match_id in current_url:
                return True
            
            # Method 2: Check for detail page elements
            try:
                driver.find_element(By.CSS_SELECTOR, ".match-name, .g-title")
                return True
            except:
                pass
            
            # Method 3: Check for stream container or tabs
            try:
                driver.find_element(By.CSS_SELECTOR, ".stream-switcher, #live-stream")
                return True
            except:
                pass
            
            return False
        except:
            return False

    # --- LOGIN ---
    try:
        print("Mencoba login...")
        driver.get('https://demo.inplaynet.com/en/')
        
        try:
            close_button = WebDriverWait(driver, 7).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.new-sportsbook-message.visible .close")))
            driver.execute_script("arguments[0].click();", close_button)
        except TimeoutException:
            pass
            
        login_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, 'login')))
        driver.execute_script("arguments[0].click();", login_button)
        wait.until(EC.visibility_of_element_located((By.NAME, 'userName'))).send_keys('greezeal')
        driver.find_element(By.NAME, 'password').send_keys('dont4skme')
        driver.find_element(By.CSS_SELECTOR, 'form.signin button[type="submit"]').click()
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[@class='user dotted-hidden' and text()='greezeal']")))
        print("Login berhasil!")
    except Exception as e:
        print(f"Gagal melakukan login. Error: {e}")
        driver.quit()
        return []

    # --- FASE 1: SETUP EVENT VIEW ---
    event_view_url = "https://demo.inplaynet.com/en/sportsbook/live#/live/eventview"
    try:
        print("Masuk ke halaman event view...")
        driver.get(event_view_url)
        
        if not safe_switch_to_iframe():
            raise Exception("Gagal masuk ke iframe sportsbook")
        
        print("Berhasil masuk ke iframe sportsbook.")
        time.sleep(3)
        
        print("Mengaktifkan filter video...")
        video_filter = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.stream')))
        driver.execute_script("arguments[0].click();", video_filter)
        
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.stream.active')))
        print("Filter video berhasil diaktifkan.")
        time.sleep(2)
        
    except Exception as e:
        print(f"Gagal pada tahap setup awal. Error: {e}")
        driver.quit()
        return []

    # --- FASE 2: COLLECT MATCH DATA ---
    match_data = []
    try:
        print("Mengumpulkan daftar ID pertandingan dengan live stream...")
        match_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.live-tree-match")))
        
        for el in match_elements:
            try:
                match_id = el.get_attribute('mid')
                if not match_id:
                    continue
                
                # Extract sport
                sport = "N/A"
                sport_selectors = [
                    "./ancestor::div[contains(@class, 'sport')]//span[contains(@class, 'sport-icon')]",
                    "./ancestor::div[contains(@class, 'sport')]//div[contains(@class, 'sport-name')]"
                ]
                
                for selector in sport_selectors:
                    try:
                        sport_elem = el.find_element(By.XPATH, selector)
                        sport_raw = sport_elem.get_attribute('sport')
                        if not sport_raw:
                            class_attr = sport_elem.get_attribute('class')
                            if 'sport-icon-' in class_attr:
                                sport_raw = class_attr.split('sport-icon-')[-1].split(' ')[0]
                        if not sport_raw:
                            sport_raw = sport_elem.text.strip()
                        
                        if sport_raw:
                            sport = ' '.join(word.capitalize() for word in sport_raw.replace('-', ' ').split())
                            print(f"     --> Sport ditemukan: {sport}")
                            break
                        else:
                            print(f"     --> Sport tidak valid: {sport} (raw: {sport_raw})")
                    except Exception as e:
                        continue
                
                # Extract competition
                competition = "N/A"
                competition_selectors = [
                    "./ancestor::div[contains(@class, 'champ')]//div[contains(@class, 'champ-name')]//span",
                    "./ancestor::div[contains(@class, 'champ')]//div[contains(@class, 'champ-name')]",
                    "./ancestor::div[contains(@class, 'champ')]//span[contains(@class, 'league')]"
                ]
                
                for selector in competition_selectors:
                    try:
                        competition = el.find_element(By.XPATH, selector).text.strip()
                        if competition:
                            print(f"     --> Competition ditemukan: {competition}")
                            break
                    except Exception:
                        continue
                
                match_data.append({
                    "match_id": match_id,
                    "sport": sport,
                    "competition": competition
                })
                
            except Exception as e:
                print(f"Gagal memproses elemen pertandingan: {e}")
                continue
                
        print(f"Berhasil mengumpulkan {len(match_data)} ID pertandingan dengan live stream.")
        
    except Exception as e:
        print(f"Gagal mengumpulkan daftar pertandingan. Error: {e}")
        driver.quit()
        return []

    # --- FASE 3: PROCESS EACH MATCH ---
    scraped_data = []
    failed_ids = []
    
    for i, match in enumerate(match_data, 1):
        match_id = match["match_id"]
        sport = match["sport"]
        competition = match["competition"]
        print(f"\n--- [{i}/{len(match_data)}] Memproses ID: {match_id} ---")
        
        max_retries = 2  # Mengurangi dari 5 menjadi 2
        retry_count = 0
        delay_times = [2, 4]  # Menyesuaikan delay times untuk 2 percobaan
        
        match_success = False
        
        while retry_count < max_retries and not match_success:
            try:
                print(f"  Percobaan {retry_count + 1}/{max_retries}")
                
                # Step 1: Return to event view
                print("  1. Kembali ke event view...")
                safe_switch_to_default()
                driver.get(event_view_url)
                
                if not safe_switch_to_iframe():
                    raise Exception("Gagal masuk ke iframe")
                
                wait_for_page_load()
                
                # Reactivate video filter if needed
                try:
                    stream_filter = driver.find_element(By.CSS_SELECTOR, 'div.stream')
                    if 'active' not in stream_filter.get_attribute('class'):
                        driver.execute_script("arguments[0].click();", stream_filter)
                        time.sleep(1)
                except:
                    pass
                
                # Step 2: Find and click match
                print(f"  2. Mencari dan mengklik pertandingan ID {match_id}...")
                
                # Try to find the match element with retries
                match_element = None
                for find_attempt in range(3):
                    try:
                        match_xpath = f"//li[@mid='{match_id}']"
                        match_element = wait.until(EC.presence_of_element_located((By.XPATH, match_xpath)))
                        break
                    except:
                        if find_attempt < 2:
                            print(f"     Percobaan {find_attempt + 1} mencari element gagal, coba lagi...")
                            time.sleep(2)
                        else:
                            raise Exception("Element pertandingan tidak ditemukan")
                
                # Scroll to element and click
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", match_element)
                    time.sleep(1)
                    
                    # Try different click methods
                    click_success = False
                    
                    # Method 1: JavaScript click
                    try:
                        driver.execute_script("arguments[0].click();", match_element)
                        click_success = True
                    except:
                        pass
                    
                    # Method 2: ActionChains click
                    if not click_success:
                        try:
                            ActionChains(driver).move_to_element(match_element).click().perform()
                            click_success = True
                        except:
                            pass
                    
                    # Method 3: Direct click
                    if not click_success:
                        match_element.click()
                        click_success = True
                        
                except Exception as e:
                    raise Exception(f"Gagal mengklik element: {e}")
                
                # Step 3: Wait for detail page with improved detection
                print("  3. Menunggu halaman detail terbuka...")
                
                detail_loaded = False
                wait_time = 0
                max_wait_time = 90
                
                while wait_time < max_wait_time and not detail_loaded:
                    time.sleep(1)
                    wait_time += 1
                    
                    if is_detail_page_loaded(match_id):
                        detail_loaded = True
                        break
                    
                    # Every 15 seconds, try to re-ensure iframe
                    if wait_time % 15 == 0:
                        safe_switch_to_iframe()
                
                if not detail_loaded:
                    raise TimeoutException("Halaman detail tidak termuat dalam waktu yang ditentukan")
                
                # Additional delay based on retry count
                time.sleep(delay_times[retry_count])
                
                # Step 4: Ensure iframe
                print("  4. Pastikan iframe...")
                safe_switch_to_iframe()
                
                # Step 5: Extract additional info if needed
                if sport == "N/A" or competition == "N/A":
                    print("  5. Mencoba ekstrak sport/competition dari halaman detail...")
                    
                    if sport == "N/A":
                        sport_selectors_detail = [
                            "//div[contains(@class, 'breadcrumb')]//span[contains(@class, 'sport')]",
                            "//div[contains(@class, 'match-info')]//span[contains(@class, 'sport')]",
                            "//div[contains(@class, 'g-title')]//span[contains(@class, 'sport')]"
                        ]
                        for selector in sport_selectors_detail:
                            try:
                                sport_raw = driver.find_element(By.XPATH, selector).text.strip()
                                if sport_raw:
                                    sport = ' '.join(word.capitalize() for word in sport_raw.replace('-', ' ').split())
                                    print(f"     --> Sport dari detail: {sport}")
                                    break
                            except:
                                continue
                    
                    if competition == "N/A":
                        competition_selectors_detail = [
                            "//div[contains(@class, 'championship')]//span",
                            "//div[contains(@class, 'match-info')]//div[contains(@class, 'champ-name')]",
                            "//div[contains(@class, 'g-title')]//span[contains(@class, 'champ')]",
                            "//div[contains(@class, 'match-info')]//span[contains(@class, 'league')]"
                        ]
                        for comp_selector in competition_selectors_detail:
                            try:
                                competition = driver.find_element(By.XPATH, comp_selector).text.strip()
                                if competition:
                                    print(f"     --> Competition dari detail: {competition}")
                                    break
                            except:
                                continue
                
                # Step 6: Click Live Stream tab
                print("  6. Mengklik tab Live Stream...")
                livestream_selectors = [
                    "//div[contains(@class, 'stream-switcher')]//span[contains(text(), 'Live Stream')]/parent::div",
                    "//div[@class='stream-switcher']//div[contains(@class, 'active')]/following-sibling::div",
                    "//span[contains(text(), 'Live Stream')]/parent::div",
                    "//div[contains(@class, 'stream-switcher')]//div[2]"
                ]
                
                livestream_clicked = False
                for selector in livestream_selectors:
                    try:
                        livestream_tab = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                        if 'active' not in (livestream_tab.get_attribute('class') or ''):
                            driver.execute_script("arguments[0].click();", livestream_tab)
                            print("     Tab Live Stream berhasil diklik.")
                            time.sleep(3)
                        livestream_clicked = True
                        break
                    except Exception:
                        continue
                
                if not livestream_clicked:
                    raise Exception("Gagal mengklik tab Live Stream")
                
                # Step 7: Wait for stream container
                print("  7. Menunggu container live stream...")
                try:
                    live_stream_container = wait.until(EC.visibility_of_element_located((By.ID, "live-stream")))
                    print("     Container live stream terdeteksi.")
                    time.sleep(2)
                except TimeoutException:
                    raise Exception("Container live stream tidak muncul")

                # Step 8: Get iframe URL
                print("  8. Mengambil URL iframe...")
                stream_url = None
                
                iframe_selectors = [
                    "#live-stream .iframe-wrapper iframe",
                    "#live-stream iframe",
                    ".iframe-wrapper iframe",
                    "iframe[src*='livestream']",
                    "iframe[src*='stream']"
                ]
                
                for selector in iframe_selectors:
                    try:
                        print(f"     Mencoba selector: {selector}")
                        iframe_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                        
                        for attempt in range(5):
                            try:
                                stream_url = iframe_element.get_attribute('src')
                                if stream_url and stream_url.strip() and stream_url != 'about:blank':
                                    print(f"     --> URL iframe ditemukan: {stream_url[:80]}...")
                                    break
                                else:
                                    print(f"     Percobaan {attempt + 1}: URL masih kosong, menunggu...")
                                    time.sleep(2)
                            except StaleElementReferenceException:
                                print(f"     Percobaan {attempt + 1}: Element stale, mencari ulang...")
                                iframe_element = driver.find_element(By.CSS_SELECTOR, selector)
                                time.sleep(1)
                        
                        if stream_url and stream_url.strip() and stream_url != 'about:blank':
                            break
                            
                    except Exception:
                        continue
                
                if not stream_url or not stream_url.strip() or stream_url == 'about:blank':
                    raise Exception("Tidak dapat mengambil URL iframe yang valid")

                # Step 9: Get team/event info
                print("  9. Mengambil info tim/event...")
                team_home = None
                team_away = None
                event_name = None
                
                is_motogp = sport in ["MotoGP", "Motorcycling"]
                
                if is_motogp:
                    print("     --> Deteksi MotoGP/Motorcycling, mencari nama event...")
                    event_selectors = [
                        ".g-title.match-name",
                        ".match-name", 
                        ".event-title",
                        ".g-title",
                        ".match-header .title",
                        ".event-name"
                    ]
                    for selector in event_selectors:
                        try:
                            event_name = driver.find_element(By.CSS_SELECTOR, selector).text.strip()
                            if event_name:
                                print(f"     --> Nama event: {event_name}")
                                break
                        except:
                            continue
                            
                    if not event_name:
                        event_name = f"MotoGP Event ID {match_id}"
                        print(f"     --> Nama event tidak ditemukan, menggunakan: {event_name}")
                else:
                    print("     --> Format tim, mencari team_home dan team_away...")
                    
                    # Try multiple methods to extract team names
                    teams_found = False
                    
                    # Method 1: Look for team spans
                    team_selectors = [
                        ".g-title.match-name .team",
                        ".match-name .team",
                        ".g-title .team",
                        ".match-header .team",
                        "span.team"
                    ]
                    
                    for selector in team_selectors:
                        try:
                            team_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            if len(team_elements) >= 2:
                                team_home = team_elements[0].text.strip()
                                team_away = team_elements[1].text.strip()
                                if team_home and team_away:
                                    print(f"     --> Team Home: {team_home}")
                                    print(f"     --> Team Away: {team_away}")
                                    teams_found = True
                                    break
                        except:
                            continue
                    
                    # Method 2: Try to parse from title text with various separators
                    if not teams_found:
                        title_selectors = [
                            ".g-title.match-name",
                            ".match-name",
                            ".g-title",
                            ".match-header .title",
                            "h1.title",
                            ".event-title"
                        ]
                        
                        separators = [" - ", " vs ", " v ", " : ", " x "]
                        
                        for title_selector in title_selectors:
                            try:
                                title_element = driver.find_element(By.CSS_SELECTOR, title_selector)
                                teams_text = title_element.text.strip()
                                print(f"     --> Mencoba parse dari title: '{teams_text}'")
                                
                                for separator in separators:
                                    if separator in teams_text:
                                        parts = teams_text.split(separator)
                                        if len(parts) >= 2:
                                            team_home = parts[0].strip()
                                            team_away = parts[1].strip()
                                            if team_home and team_away:
                                                print(f"     --> Team Home (parsed): {team_home}")
                                                print(f"     --> Team Away (parsed): {team_away}")
                                                teams_found = True
                                                break
                                
                                if teams_found:
                                    break
                                    
                            except:
                                continue
                    
                    # Method 3: Try XPath approaches
                    if not teams_found:
                        xpath_selectors = [
                            "//div[contains(@class, 'match-name')]//span[contains(@class, 'team')]",
                            "//div[contains(@class, 'g-title')]//span[contains(@class, 'team')]",
                            "//span[@class='team']",
                            "//div[contains(@class, 'team')]"
                        ]
                        
                        for xpath_selector in xpath_selectors:
                            try:
                                team_elements = driver.find_elements(By.XPATH, xpath_selector)
                                if len(team_elements) >= 2:
                                    team_home = team_elements[0].text.strip()
                                    team_away = team_elements[1].text.strip()
                                    if team_home and team_away:
                                        print(f"     --> Team Home (xpath): {team_home}")
                                        print(f"     --> Team Away (xpath): {team_away}")
                                        teams_found = True
                                        break
                            except:
                                continue
                    
                    # Method 4: Look for any text content and try to extract team names
                    if not teams_found:
                        try:
                            # Get all text from the page and look for patterns
                            page_text = driver.find_element(By.TAG_NAME, "body").text
                            lines = [line.strip() for line in page_text.split('\n') if line.strip()]
                            
                            for line in lines[:20]:  # Check first 20 lines
                                for separator in [" - ", " vs ", " v ", " : ", " x "]:
                                    if separator in line and len(line) < 100:  # Reasonable length
                                        parts = line.split(separator)
                                        if len(parts) == 2:
                                            potential_home = parts[0].strip()
                                            potential_away = parts[1].strip()
                                            # Basic validation - not too long, not too short
                                            if 2 <= len(potential_home) <= 30 and 2 <= len(potential_away) <= 30:
                                                team_home = potential_home
                                                team_away = potential_away
                                                print(f"     --> Team Home (text scan): {team_home}")
                                                print(f"     --> Team Away (text scan): {team_away}")
                                                teams_found = True
                                                break
                                if teams_found:
                                    break
                        except:
                            pass
                    
                    # Fallback if nothing found
                    if not teams_found or not team_home or not team_away:
                        team_home = f"Home Match ID {match_id}"
                        team_away = f"Away Match ID {match_id}"
                        print(f"     --> Menggunakan fallback names")
                
                # Try to get competition info from detail page if still N/A
                if competition == "N/A":
                    print("     --> Mencoba ekstrak competition dari halaman detail...")
                    competition_selectors = [
                        ".championship-name",
                        ".league-name", 
                        ".competition-name",
                        ".tournament-name",
                        ".breadcrumb .competition",
                        ".match-info .competition",
                        "//div[contains(@class, 'championship')]",
                        "//div[contains(@class, 'league')]",
                        "//span[contains(@class, 'competition')]"
                    ]
                    
                    for comp_selector in competition_selectors:
                        try:
                            if comp_selector.startswith("//"):
                                comp_element = driver.find_element(By.XPATH, comp_selector)
                            else:
                                comp_element = driver.find_element(By.CSS_SELECTOR, comp_selector)
                            
                            comp_text = comp_element.text.strip()
                            if comp_text and len(comp_text) > 3:  # Basic validation
                                competition = comp_text
                                print(f"     --> Competition dari detail: {competition}")
                                break
                        except:
                            continue

                # Success! Create data entry
                is_single_team = not team_away.strip()
                event_name = f"{team_home} vs {team_away}" if not is_single_team else team_home
                print(f"     --> BERHASIL! Data untuk {event_name} telah dikumpulkan.")
                
                # Create team names without special characters for ID
                safe_team1 = re.sub(r'[^a-zA-Z0-9]', '', team_home)
                safe_team2 = re.sub(r'[^a-zA-Z0-9]', '', team_away) if not is_single_team else ""
                
                # Encode the stream URL for the new format
                encoded_url = base64.b64encode(stream_url.encode('utf-8')).decode('utf-8')
                new_stream_url = f"https://multi.govoet.my.id/?iframe={encoded_url}"
                
                data_entry = {
                    "id": f"{safe_team1}-{safe_team2}" if not is_single_team else safe_team1,
                    "league": competition,
                    "team1": {
                        "name": team_home
                    },
                    "team2": {
                        "name": team_away if not is_single_team else ""
                    },
                    "kickoff_date": "live",
                    "kickoff_time": "live",
                    "match_date": "live",
                    "match_time": "live",
                    "duration": "3.5",
                    "servers": [
                        {
                            "url": new_stream_url,
                            "label": "CH-NA"
                        }
                    ]
                }
                
                if is_motogp:
                    data_entry["sport"] = sport
                
                scraped_data.append(data_entry)
                match_success = True
                break

            except Exception as e:
                retry_count += 1
                print(f"  --> GAGAL memproses ID {match_id} (Percobaan {retry_count}/{max_retries}): {type(e).__name__} - {str(e)}")
                
                if retry_count >= 3:
                    print("     Melakukan refresh halaman...")
                    try:
                        driver.refresh()
                        time.sleep(3)
                    except:
                        pass
                
                if retry_count < max_retries:
                    print("  Mencoba ulang...")
                    time.sleep(2)
                    continue
                else:
                    failed_ids.append(match_id)

        if i < len(match_data):
            print("  10. Jeda antar pertandingan...")
            time.sleep(2)

    # --- CLEANUP ---
    print(f"\n{'='*50}")
    print(f"SCRAPING SELESAI!")
    print(f"Total berhasil: {len(scraped_data)} dari {len(match_data)} pertandingan")
    if failed_ids:
        print(f"ID yang gagal: {failed_ids}")
    print(f"{'='*50}")

    driver.quit()
    
    # Save results
    with open('inplaynet.json', 'w', encoding='utf-8') as f:
        json.dump(scraped_data, f, ensure_ascii=False, indent=4)
    
    if scraped_data:
        print("\nPreview hasil:")
        for i, data in enumerate(scraped_data[:3], 1):
            if "event_name" in data:
                print(f"  {i}. {data['event_name']} - {data['sport']} - {data['league']}")
            else:
                print(f"  {i}. {data['team1']['name']} vs {data['team2']['name']} - {data['league']}")
            print(f"     URL: {data['servers'][0]['url'][:60]}...")
        
        if len(scraped_data) > 3:
            print(f"  ... dan {len(scraped_data) - 3} lainnya")
    
    return scraped_data

if __name__ == "__main__":
    scrape_inplaynet_improved()