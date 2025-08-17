import time
import json
import base64
import logging
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from concurrent.futures import ThreadPoolExecutor, as_completed

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# Fungsi untuk encode URL
def encode_url(original_url):
    encoded = base64.b64encode(original_url.encode('utf-8')).decode('utf-8')
    return f"https://multi.govoet.my.id/?iframe={encoded}"

# Fungsi untuk setup browser
def setup_browser(headless=True):
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-cache")
    return webdriver.Chrome(options=chrome_options)

# Fungsi untuk login dan menyimpan cookies
def login(driver, login_url, logger):
    logger.info("Memulai login")
    driver.get(login_url)
    time.sleep(2)

    # Tangani overlay
    try:
        overlay = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.overlay.new-sportsbook-message.visible"))
        )
        logger.info("Overlay ditemukan, mencoba menanganinya")
        try:
            close_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".material-icons.close"))
            )
            close_button.click()
            logger.info("Overlay ditutup dengan tombol close")
            time.sleep(1)
        except TimeoutException:
            logger.info("Tombol close tidak ditemukan, menghilangkan overlay dengan JavaScript")
            driver.execute_script("document.querySelector('div.overlay.new-sportsbook-message.visible').style.display = 'none';")
            time.sleep(1)
    except TimeoutException:
        logger.info("Overlay tidak ditemukan, lanjutkan ke login")

    # Klik tombol login
    try:
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "login"))
        )
        driver.execute_script("arguments[0].click();", login_button)
        logger.info("Tombol login berhasil diklik")
    except TimeoutException:
        logger.error("Tombol login tidak ditemukan atau popup login tidak muncul")
        return False
    except Exception as e:
        logger.error(f"Error saat mencoba klik tombol login: {e}")
        return False

    # Isi form login
    try:
        username_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "userName"))
        )
        password_input = driver.find_element(By.NAME, "password")
        submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        username_input.send_keys("greezeal")
        password_input.send_keys("dont4skme")
        submit_button.click()
        time.sleep(5)
        logger.info("Login berhasil")
        return True
    except Exception as e:
        logger.error(f"Error saat login: {e}")
        return False

# Fungsi untuk memuat cookies
def load_cookies(driver, cookies, logger):
    for cookie in cookies:
        driver.add_cookie(cookie)
    logger.info("Cookies dimuat")

# Fungsi untuk memproses satu pertandingan
def process_match(match_id, base_url, cookies, logger_name):
    logger = logging.getLogger(logger_name)
    driver = setup_browser(headless=True)
    try:
        logger.info(f"Memproses match {match_id}")
        driver.get(base_url)
        load_cookies(driver, cookies, logger)
        time.sleep(1)

        # Navigasi ke halaman event view
        event_view_url = f"{base_url}sportsbook/live#/live/eventview/{match_id}"
        retries = 3
        for attempt in range(retries):
            try:
                driver.get(event_view_url)
                time.sleep(5)
                break
            except Exception as e:
                logger.error(f"Gagal memuat halaman untuk match {match_id} pada percobaan {attempt + 1}: {e}")
                if attempt == retries - 1:
                    return {
                        "id": match_id,
                        "league": "Unknown League",
                        "team1": {"name": "Unknown Team"},
                        "team2": {"name": "Unknown Team"},
                        "kickoff_date": "live",
                        "kickoff_time": "live",
                        "match_date": "live",
                        "match_time": "live",
                        "duration": "live",
                        "servers": []
                    }
                time.sleep(2)

        # Switch ke iframe sportsbook
        try:
            driver.switch_to.frame("sportsbook_iframe")
            logger.info(f"Berhasil switch ke iframe untuk match {match_id}")
            time.sleep(2)
        except Exception as e:
            logger.error(f"Iframe tidak ditemukan untuk match {match_id}: {e}")
            return {
                "id": match_id,
                "league": "Unknown League",
                "team1": {"name": "Unknown Team"},
                "team2": {"name": "Unknown Team"},
                "kickoff_date": "live",
                "kickoff_time": "live",
                "match_date": "live",
                "match_time": "live",
                "duration": "live",
                "servers": []
            }

        # Ambil nama liga dan tim
        league = "Unknown League"
        team1 = "Unknown Team"
        team2 = "Unknown Team"
        sport_type = "unknown"
        for attempt in range(2):
            try:
                content_elem = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.content div.match-info"))
                )
                # Ambil jenis olahraga
                try:
                    sport_type = content_elem.get_attribute("sport") or "unknown"
                    logger.info(f"Jenis olahraga untuk match {match_id}: {sport_type}")
                except:
                    logger.warning(f"Tidak dapat menemukan atribut sport untuk match {match_id}")

                # Ambil nama liga
                try:
                    league_elem = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.champ-name span"))
                    )
                    league = league_elem.text.strip() if league_elem else "Unknown League"
                    logger.info(f"Nama liga untuk match {match_id}: {league}")
                except TimeoutException:
                    try:
                        league_elem = driver.find_element(By.CSS_SELECTOR, "div.champ-name span[title]")
                        league = league_elem.text.strip() if league_elem else "Unknown League"
                        logger.info(f"Nama liga untuk match {match_id} (selector alternatif): {league}")
                    except NoSuchElementException:
                        logger.warning(f"Tidak dapat menemukan nama liga untuk match {match_id}, menggunakan 'Unknown League'")
                        logger.debug(f"Page source untuk match {match_id}:\n{driver.page_source}")

                # Ambil nama tim/pemain
                try:
                    # Tunggu hingga div.main-score atau div.line2 tersedia
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.main-score, div.line2"))
                    )
                    if sport_type in ["tennis", "baseball"] or "Challenger" in league or "KBO League" in league or "CPBL" in league:
                        # Untuk tenis dan baseball
                        try:
                            team1_elem = content_elem.find_element(By.CSS_SELECTOR, "div.main-score div.team.team1")
                            team1 = team1_elem.text.strip() if team1_elem else "Unknown Team"
                            logger.info(f"{'Pemain' if sport_type == 'tennis' else 'Tim'} 1 untuk match {match_id}: {team1}")
                        except NoSuchElementException:
                            try:
                                team1_elem = content_elem.find_element(By.CSS_SELECTOR, "div.set-stats div.team1 div.name span")
                                team1 = team1_elem.text.strip() if team1_elem else "Unknown Team"
                                logger.info(f"{'Pemain' if sport_type == 'tennis' else 'Tim'} 1 untuk match {match_id} (selector alternatif): {team1}")
                            except NoSuchElementException:
                                logger.warning(f"Tidak dapat menemukan {'pemain' if sport_type == 'tennis' else 'tim'} 1 untuk match {match_id}, menggunakan 'Unknown Team'")
                                logger.debug(f"Page source untuk match {match_id}:\n{driver.page_source}")
                                team1 = "Player 1" if sport_type == "tennis" else "Team 1"

                        try:
                            team2_elem = content_elem.find_element(By.CSS_SELECTOR, "div.main-score div.team.team2")
                            team2 = team2_elem.text.strip() if team2_elem else "Unknown Team"
                            logger.info(f"{'Pemain' if sport_type == 'tennis' else 'Tim'} 2 untuk match {match_id}: {team2}")
                        except NoSuchElementException:
                            try:
                                team2_elem = content_elem.find_element(By.CSS_SELECTOR, "div.set-stats div.team2 div.name span")
                                team2 = team2_elem.text.strip() if team2_elem else "Unknown Team"
                                logger.info(f"{'Pemain' if sport_type == 'tennis' else 'Tim'} 2 untuk match {match_id} (selector alternatif): {team2}")
                            except NoSuchElementException:
                                logger.warning(f"Tidak dapat menemukan {'pemain' if sport_type == 'tennis' else 'tim'} 2 untuk match {match_id}, menggunakan 'Unknown Team'")
                                logger.debug(f"Page source untuk match {match_id}:\n{driver.page_source}")
                                team2 = "Player 2" if sport_type == "tennis" else "Team 2"
                    else:
                        # Untuk olahraga lain (sepak bola, dll.)
                        try:
                            team1_elem = content_elem.find_element(By.CSS_SELECTOR, "div.line2 div.team.team1, div.main-score div.team.team1")
                            team1 = team1_elem.text.strip() if team1_elem else "Unknown Team"
                            logger.info(f"Tim 1 untuk match {match_id}: {team1}")
                        except NoSuchElementException:
                            logger.warning(f"Tidak dapat menemukan tim 1 untuk match {match_id}, menggunakan 'Unknown Team'")
                            logger.debug(f"Page source untuk match {match_id}:\n{driver.page_source}")
                            team1 = "Unknown Team"

                        try:
                            team2_elem = content_elem.find_element(By.CSS_SELECTOR, "div.line2 div.team.team2, div.main-score div.team.team2")
                            team2 = team2_elem.text.strip() if team2_elem else "Unknown Team"
                            logger.info(f"Tim 2 untuk match {match_id}: {team2}")
                        except NoSuchElementException:
                            logger.warning(f"Tidak dapat menemukan tim 2 untuk match {match_id}, menggunakan 'Unknown Team'")
                            logger.debug(f"Page source untuk match {match_id}:\n{driver.page_source}")
                            team2 = "Unknown Team"

                    break
                except TimeoutException:
                    logger.error(f"Elemen main-score atau line2 tidak ditemukan untuk match {match_id} pada percobaan {attempt + 1}")
                    logger.debug(f"Page source untuk match {match_id}:\n{driver.page_source}")
                    if attempt == 1:
                        team1 = "Player 1" if sport_type == "tennis" else "Team 1"
                        team2 = "Player 2" if sport_type == "tennis" else "Team 2"
            except TimeoutException:
                logger.error(f"Elemen content tidak ditemukan untuk match {match_id} pada percobaan {attempt + 1}")
                logger.debug(f"Page source untuk match {match_id}:\n{driver.page_source}")
                if attempt == 1:
                    return {
                        "id": match_id,
                        "league": "Unknown League",
                        "team1": {"name": "Unknown Team"},
                        "team2": {"name": "Unknown Team"},
                        "kickoff_date": "live",
                        "kickoff_time": "live",
                        "match_date": "live",
                        "match_time": "live",
                        "duration": "live",
                        "servers": []
                    }
                time.sleep(2)

        # Cek dan aktifkan live stream
        servers = []
        try:
            is_stream_active = driver.find_elements(By.CSS_SELECTOR, ".stream-switcher div.active .stream-icon.live")
            if not is_stream_active:
                live_stream_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".stream-switcher div:not(.active) .stream-icon.live"))
                )
                driver.execute_script("arguments[0].click();", live_stream_button)
                logger.info(f"Tombol live stream diklik untuk match {match_id}")
                time.sleep(7)
            else:
                logger.info(f"Live stream sudah aktif untuk match {match_id}")

            stream_iframe = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#live-stream iframe"))
            )
            original_url = stream_iframe.get_attribute("src")
            encoded_url = encode_url(original_url)
            servers = [{"url": encoded_url, "label": "CH-NA"}]
            logger.info(f"Live stream URL ditemukan untuk match {match_id}: {original_url}")
        except TimeoutException:
            logger.error(f"Tombol live stream atau iframe tidak ditemukan untuk match {match_id}")
            logger.debug(f"Page source untuk match {match_id}:\n{driver.page_source}")
        except Exception as e:
            logger.error(f"Error saat mencari live stream untuk match {match_id}: {e}")

        return {
            "id": match_id,
            "league": league,
            "team1": {"name": team1},
            "team2": {"name": team2},
            "kickoff_date": "live",
            "kickoff_time": "live",
            "match_date": "live",
            "match_time": "live",
            "duration": "live",
            "servers": servers
        }
    finally:
        driver.quit()

# Main script
def main():
    base_url = "https://demo.inplaynet.com/en/"
    login_url = base_url
    sportsbook_url = base_url + "sportsbook/live#/live/eventview/"
    main_logger = logging.getLogger("main")

    # Setup browser untuk mengumpulkan daftar pertandingan
    driver = setup_browser(headless=True)
    try:
        # Login dan simpan cookies
        if not login(driver, login_url, main_logger):
            main_logger.error("Gagal login, keluar")
            return
        cookies = driver.get_cookies()
        main_logger.info("Cookies login disimpan")

        # Akses halaman eventview
        driver.get(sportsbook_url)
        time.sleep(5)

        # Switch ke iframe sportsbook
        try:
            driver.switch_to.frame("sportsbook_iframe")
            main_logger.info("Berhasil switch ke iframe sportsbook")
        except Exception as e:
            main_logger.error(f"Iframe tidak ditemukan: {e}")
            return

        # Klik icon video untuk filter live streaming
        try:
            video_filter_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.stream"))
            )
            driver.execute_script("arguments[0].click();", video_filter_button)
            main_logger.info("Tombol filter live streaming berhasil diklik")
            time.sleep(5)
        except TimeoutException:
            main_logger.error("Tombol filter live streaming tidak ditemukan")
            main_logger.debug(f"Page source dalam iframe:\n{driver.page_source}")
            return

        # Ambil list match IDs
        match_ids = []
        retries = 3
        for attempt in range(retries):
            try:
                match_elements = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".live-tree-match"))
                )
                for match_elem in match_elements:
                    match_id = match_elem.get_attribute("mid")
                    if match_id:
                        match_ids.append(match_id)
                main_logger.info(f"Berhasil mengumpulkan {len(match_ids)} match IDs")
                break
            except StaleElementReferenceException:
                main_logger.warning(f"Stale element reference pada percobaan {attempt + 1}, mencoba lagi")
                time.sleep(2)
                if attempt == retries - 1:
                    main_logger.error("Gagal mengambil daftar match IDs setelah beberapa percobaan")
                    main_logger.debug(f"Page source:\n{driver.page_source}")
                    return
            except TimeoutException:
                main_logger.error("Gagal menemukan elemen .live-tree-match")
                main_logger.debug(f"Page source:\n{driver.page_source}")
                return

    finally:
        driver.quit()

    # Proses pertandingan secara paralel dengan 4 thread
    matches = []
    seen_match_ids = set()
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(process_match, match_id, base_url, cookies, ["Aralie", "Oline", "Lia", "Ekin", "Icel"][i % 5])
            for i, match_id in enumerate(match_ids)
        ]
        for future in as_completed(futures):
            try:
                result = future.result()
                if result["servers"]:
                    url = result["servers"][0]["url"]
                    match_id_in_url = re.search(r"match_id=(\d+)", url)
                    if match_id_in_url:
                        match_id_url = match_id_in_url.group(1)
                        if match_id_url in seen_match_ids:
                            main_logger.info(f"Melewati match {result['id']} karena duplikat match_id {match_id_url}")
                            continue
                        seen_match_ids.add(match_id_url)
                matches.append(result)
            except Exception as e:
                main_logger.error(f"Error di thread: {e}")

    # Output JSON
    output_json = json.dumps(matches, indent=4)
    main_logger.info("Output JSON:")
    main_logger.info(output_json)

    # Simpan ke file
    with open("output.json", "w") as f:
        f.write(output_json)
        main_logger.info("Output disimpan ke output.json")

if __name__ == "__main__":
    main()