from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin
import time
import os

# --- KONFIGURASI UNTUK TES ---
# Ganti URL ini dengan URL anime lain jika perlu untuk testing
TEST_ANIME_URL = 'https://kickass-anime.ru/one-piece-0948' 
BASE_URL = 'https://kickass-anime.ru'
DETAILS_DIR = 'details_test' # Menggunakan folder terpisah agar tidak mengganggu data asli

# ===================================================================
# DI BAWAH INI ADALAH FUNGSI-FUNGSI DARI SKRIP ASLI ANDA
# (Dengan perbaikan `wait_until='networkidle'`)
# ===================================================================

def get_browser_page():
    """Membuka browser dan halaman baru."""
    p = sync_playwright().start()
    print("Meluncurkan browser Chromium...")
    browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36',
        viewport={'width': 1920, 'height': 1080}
    )
    page = context.new_page()
    return p, browser, page

def scroll_to_bottom(page):
    """Mensimulasikan scroll ke bawah untuk memuat semua konten."""
    print("Memulai scroll...")
    try:
        last_height = page.evaluate('document.body.scrollHeight')
        for _ in range(10): 
            page.evaluate('window.scrollTo(0, document.body.scrollHeight);')
            time.sleep(2) 
            new_height = page.evaluate('document.body.scrollHeight')
            if new_height == last_height:
                break
            last_height = new_height
        print("Scroll selesai.")
    except Exception as e:
        print(f"Error saat scroll: {e}")

def parse_episode_item(item_soup):
    """Mendapatkan data dari satu item episode."""
    try:
        episode_num_tag = item_soup.find('span', class_='episode-badge')
        episode_num = episode_num_tag.get_text(strip=True) if episode_num_tag else 'N/A'
        card_link_tag = item_soup.find('div', class_='v-card--link')
        relative_link = ''
        if card_link_tag and 'onclick' in card_link_tag.attrs:
            onclick_attr = card_link_tag['onclick']
            match = re.search(r"this\.\$router\.push\('(.+?)'\)", onclick_attr)
            if match:
                relative_link = match.group(1)
        thumbnail_div = item_soup.find('div', class_='v-image__image')
        thumbnail_url = 'N/A'
        if thumbnail_div and 'style' in thumbnail_div.attrs:
            style_attr = thumbnail_div['style']
            match = re.search(r'url\("?(.+?)"?\)', style_attr)
            thumbnail_url = match.group(1) if match else 'N/A'
        return {
            'episode_number': episode_num,
            'episode_url': urljoin(BASE_URL, relative_link),
            'thumbnail_url': thumbnail_url
        }
    except Exception:
        return None

def scrape_anime_details(page, anime_url):
    """Scrape detail anime (versi sederhana untuk tes)."""
    anime_slug = anime_url.split('/')[-1]
    file_path = os.path.join(DETAILS_DIR, f"{anime_slug}.json")
    
    print(f"Membuka halaman detail: {anime_url}")
    # ==================================================
    # === INI ADALAH PERBAIKAN UTAMANYA ===
    # Mengubah 'domcontentloaded' menjadi 'networkidle'
    page.goto(anime_url, timeout=90000, wait_until='networkidle')
    # ==================================================

    print("Menunggu selector '.episode-list-container' muncul...")
    page.wait_for_selector('.episode-list-container', timeout=60000)
    print("Selector ditemukan! Halaman berhasil dimuat.")
    
    scroll_to_bottom(page)
    
    html_content = page.content()
    soup = BeautifulSoup(html_content, 'html.parser')

    title = soup.find('h1', class_='text-h6').get_text(strip=True) if soup.find('h1', class_='text-h6') else 'N/A'
    all_episode_items_on_page = soup.find_all('div', class_='episode-item')
    total_episodes_on_page = len(all_episode_items_on_page)
    print(f"Total episode ditemukan di halaman: {total_episodes_on_page}")

    episodes = []
    for item in all_episode_items_on_page[:5]: # Kita ambil 5 episode saja sebagai sampel
        ep_data = parse_episode_item(item)
        if ep_data:
            episodes.append(ep_data)

    test_data = {
        'title': title,
        'source_url': anime_url,
        'sampled_episodes': episodes,
        'total_episodes_found': total_episodes_on_page
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)

    return f"File tes untuk '{title}' berhasil disimpan di {file_path}"

# ===================================================================
# BAGIAN UTAMA UNTUK MENJALANKAN TES
# ===================================================================

if __name__ == '__main__':
    print(f"--- MEMULAI TES SCRAPER UNTUK SATU ANIME ---")
    print(f"URL Target: {TEST_ANIME_URL}")
    
    os.makedirs(DETAILS_DIR, exist_ok=True)
    p, browser, page = get_browser_page()
    
    try:
        result_message = scrape_anime_details(page, TEST_ANIME_URL)
        print("\n" + "="*50)
        print("✅ ✅ ✅ TES BERHASIL! ✅ ✅ ✅")
        print(result_message)
        print("="*50 + "\n")

    except TimeoutError as e:
        print("\n" + "="*50)
        print("❌ ❌ ❌ TES GAGAL! ❌ ❌ ❌")
        print("Penyebab: Timeout. Halaman atau elemen tidak dapat dimuat tepat waktu.")
        print(f"Detail error: {e}")
        print("="*50 + "\n")
        # Melempar kembali error agar jika dijalankan di Actions, prosesnya tetap gagal
        raise e 
        
    except Exception as e:
        print("\n" + "="*50)
        print("❌ ❌ ❌ TES GAGAL! ❌ ❌ ❌")
        print(f"Terjadi error yang tidak terduga: {e}")
        print("="*50 + "\n")
        raise e

    finally:
        print("Menutup browser...")
        browser.close()
        p.stop()
        print("Tes selesai.")
