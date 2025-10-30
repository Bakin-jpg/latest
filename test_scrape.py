from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin
import time
import os

# --- KONFIGURASI UNTUK TES ---
TEST_ANIME_URL = 'https://kickass-anime.ru/one-piece-0948'
BASE_URL = 'https://kickass-anime.ru'
DETAILS_DIR = 'details_test'
SCREENSHOT_FILE = 'debug_screenshot.png'

def get_browser_page():
    p = sync_playwright().start()
    print("Meluncurkan browser Chromium...")
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080}
    )
    page = context.new_page()
    return p, browser, page

def scrape_anime_details(page, anime_url):
    anime_slug = anime_url.split('/')[-1]
    file_path = os.path.join(DETAILS_DIR, f"{anime_slug}.json")
    
    print(f"Membuka halaman detail: {anime_url}")
    page.goto(anime_url, timeout=90000, wait_until='networkidle')

    try:
        print("Mencari tombol 'Watch Now'...")
        page.click("a:has-text('Watch Now')", timeout=10000)
        print("Tombol 'Watch Now' diklik. Memberi jeda 5 detik agar konten dinamis mulai memuat...")
        # Beri jeda statis setelah klik untuk memberi waktu JavaScript memulai pemuatan
        time.sleep(5)
    except TimeoutError:
        print("Tombol 'Watch Now' tidak ditemukan. Melanjutkan...")

    print("Mengekstrak data dari variabel JavaScript 'window.KAA'...")
    kaa_data = page.evaluate('() => window.KAA')
    
    if not kaa_data:
        raise Exception("Gagal mendapatkan objek 'window.KAA' dari halaman.")

    print("Ekstraksi data JavaScript berhasil.")

    show_info = kaa_data.get('data', [{}])[0].get('show', {})
    title = show_info.get('title_en') or show_info.get('title')
    synopsis = show_info.get('synopsis')
    
    # --- PENDEKATAN BARU UNTUK IFRAME ---
    iframe_url = "N/A"
    try:
        print("Mencoba menemukan iframe dengan menunggu locator...")
        # Tunggu locator iframe menjadi visible
        iframe_locator = page.locator('.player-container iframe.player')
        iframe_locator.wait_for(state="visible", timeout=20000)
        iframe_url = iframe_locator.get_attribute('src')
        print("URL Iframe ditemukan melalui locator.")
    except TimeoutError:
        print("Tidak dapat menemukan iframe dengan menunggu locator. Halaman mungkin tidak memuatnya.")
        page.screenshot(path=SCREENSHOT_FILE, full_page=True)
        print(f"Screenshot kegagalan iframe disimpan sebagai {SCREENSHOT_FILE}")


    html_content = page.content()
    soup = BeautifulSoup(html_content, 'html.parser')
    
    all_episode_items = soup.find_all('div', class_='episode-item')
    total_episodes_found = len(all_episode_items)

    sampled_episodes = []
    for item_soup in all_episode_items[:5]:
        episode_num = item_soup.find('span', class_='episode-badge').get_text(strip=True) if item_soup.find('span', class_='episode-badge') else 'N/A'
        
        card_link_tag = item_soup.find('div', class_='v-card--link')
        relative_link = 'N/A'
        if card_link_tag and 'onclick' in card_link_tag.attrs:
            match = re.search(r"this\.\$router\.push\('(.+?)'\)", card_link_tag['onclick'])
            if match:
                relative_link = match.group(1)
        
        thumbnail_div = item_soup.find('div', class_='v-image__image')
        thumbnail_url = 'N/A'
        if thumbnail_div and 'style' in thumbnail_div.attrs:
            match = re.search(r'url\("?(.+?)"?\)', thumbnail_div['style'])
            if match:
                thumbnail_url = match.group(1)

        sampled_episodes.append({
            'episode_number': episode_num,
            'episode_url': urljoin(BASE_URL, relative_link),
            'thumbnail_url': thumbnail_url
        })

    final_json = {
        'title': title,
        'source_url': anime_url,
        'synopsis': synopsis,
        'current_iframe_url': iframe_url,
        'sampled_episodes': sampled_episodes,
        'total_episodes_found': total_episodes_found
    }

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    return f"File tes untuk '{title}' berhasil disimpan."

# Bagian utama untuk menjalankan skrip (if __name__ == '__main__':)
if __name__ == '__main__':
    os.makedirs(DETAILS_DIR, exist_ok=True)
    p, browser, page = get_browser_page()
    
    try:
        result_message = scrape_anime_details(page, TEST_ANIME_URL)
        print("\n" + "="*50)
        print(f"✅ TES SELESAI: {result_message}")
        print("="*50 + "\n")
    except Exception as e:
        print("\n" + "="*50)
        print(f"❌ TES GAGAL.")
        print(f"Detail error: {e}")
        print("="*50 + "\n")
        exit(1)
    finally:
        print("Menutup browser...")
        browser.close()
        p.stop()
        print("Tes selesai.")
