from playwright.sync_api import sync_playwright, TimeoutError
from playwright_stealth import stealth_sync # <-- IMPORT BARU YANG PENTING
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

def get_browser_page():
    p = sync_playwright().start()
    print("Meluncurkan browser Chromium...")
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080}
    )
    page = context.new_page()
    
    # =======================================================
    # === INI ADALAH KUNCI UTAMANYA: AKTIFKAN STEALTH MODE ===
    print("Mengaktifkan mode stealth untuk menghindari deteksi bot...")
    stealth_sync(page)
    # =======================================================
    
    return p, browser, page

def scrape_anime_details(page, anime_url):
    anime_slug = anime_url.split('/')[-1]
    file_path = os.path.join(DETAILS_DIR, f"{anime_slug}.json")
    
    print(f"Membuka halaman detail: {anime_url}")
    page.goto(anime_url, timeout=90000, wait_until='networkidle')

    try:
        print("Mencari tombol 'Watch Now'...")
        page.click("a:has-text('Watch Now')", timeout=10000)
        print("Tombol 'Watch Now' diklik. Menunggu konten video...")
        
        # Setelah klik, kita tunggu elemen pentingnya
        print("Menunggu iframe video player muncul...")
        page.wait_for_selector('.player-container iframe.player', timeout=30000)
        
        print("Menunggu item episode pertama muncul...")
        page.wait_for_selector('.episode-list-container .episode-item', timeout=30000)
        print("Konten dinamis berhasil dimuat!")

    except TimeoutError:
        print("Peringatan: Tombol 'Watch Now' tidak ada atau konten gagal dimuat setelah diklik.")

    html_content = page.content()
    soup = BeautifulSoup(html_content, 'html.parser')

    title_element = soup.select_one('.v-card__title h1.text-h6, .anime-info-card .v-card__title span')
    title = title_element.get_text(strip=True) if title_element else 'N/A'
    
    synopsis_element = soup.select_one('div.text-caption, .v-card__text .text-caption')
    synopsis = synopsis_element.get_text(strip=True) if synopsis_element else 'N/A'
    
    iframe_element = soup.select_one('.player-container iframe.player')
    iframe_url = iframe_element['src'] if iframe_element else 'N/A'

    all_episode_items_on_page = soup.find_all('div', class_='episode-item')
    total_episodes_on_page = len(all_episode_items_on_page)
    
    sampled_episodes = []
    for item in all_episode_items_on_page[:5]:
        ep_num = item.find('span', class_='episode-badge').get_text(strip=True) if item.find('span', class_='episode-badge') else 'N/A'
        
        relative_link = 'N/A'
        card_link = item.find('div', class_='v-card--link')
        if card_link and 'onclick' in card_link.attrs:
            match = re.search(r"this\.\$router\.push\('(.+?)'\)", card_link['onclick'])
            if match:
                relative_link = match.group(1)
        
        thumb_url = 'N/A'
        thumb_div = item.find('div', class_='v-image__image')
        if thumb_div and 'style' in thumb_div.attrs:
            match = re.search(r'url\("?(.+?)"?\)', thumb_div['style'])
            if match:
                thumb_url = match.group(1)

        sampled_episodes.append({
            'episode_number': ep_num,
            'episode_url': urljoin(BASE_URL, relative_link),
            'thumbnail_url': thumb_url
        })
        
    final_json = {
        'title': title,
        'source_url': anime_url,
        'synopsis': synopsis,
        'current_iframe_url': iframe_url,
        'sampled_episodes': sampled_episodes,
        'total_episodes_found': total_episodes_on_page
    }

    # Jika data penting masih kosong setelah semua usaha, anggap gagal
    if iframe_url == "N/A" or not sampled_episodes or sampled_episodes[0]['episode_url'].endswith('N/A'):
        raise Exception("Scraping berhasil tapi data penting (iframe/episode url) kosong. Kemungkinan deteksi bot aktif.")

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(final_json, f, ensure_ascii=False, indent=2)

    return f"File tes untuk '{title}' berhasil disimpan dengan mode STEALTH."

if __name__ == '__main__':
    os.makedirs(DETAILS_DIR, exist_ok=True)
    p, browser, page = get_browser_page()
    
    try:
        result_message = scrape_anime_details(page, TEST_ANIME_URL)
        print("\n" + "="*50)
        print(f"✅ TES BERHASIL: {result_message}")
        print("="*50 + "\n")
    except Exception as e:
        print("\n" + "="*50)
        print(f"❌ TES GAGAL.")
        page.screenshot(path="debug_screenshot.png", full_page=True)
        print("Screenshot kegagalan disimpan sebagai debug_screenshot.png")
        print(f"Detail error: {e}")
        print("="*50 + "\n")
        exit(1)
    finally:
        print("Menutup browser...")
        browser.close()
        p.stop()
        print("Tes selesai.")
