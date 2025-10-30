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

def get_browser_page():
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
    print("Memulai scroll...")
    try:
        for _ in range(5):
            page.evaluate('window.scrollTo(0, document.body.scrollHeight);')
            time.sleep(1) 
        print("Scroll selesai.")
    except Exception as e:
        print(f"Error saat scroll: {e}")

def parse_episode_item(item_soup):
    try:
        episode_num_tag = item_soup.find('span', class_='episode-badge')
        episode_num = episode_num_tag.get_text(strip=True) if episode_num_tag else 'N/A'
        
        # Logika baru untuk mendapatkan URL dari atribut 'onclick'
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
            'episode_url': urljoin(BASE_URL, relative_link), # Menggunakan relative_link yang ditemukan
            'thumbnail_url': thumbnail_url
        }
    except Exception:
        return None

def scrape_anime_details(page, anime_url):
    anime_slug = anime_url.split('/')[-1]
    file_path = os.path.join(DETAILS_DIR, f"{anime_slug}.json")
    
    print(f"Membuka halaman detail: {anime_url}")
    page.goto(anime_url, timeout=90000, wait_until='networkidle')

    episode_list_selector = ".episode-list-container"
    is_list_visible = False
    
    try:
        print(f"Mencoba menemukan '{episode_list_selector}' secara langsung...")
        page.wait_for_selector(episode_list_selector, state='visible', timeout=10000)
        print("Daftar episode ditemukan secara langsung.")
        is_list_visible = True
    except TimeoutError:
        print("Daftar episode tidak ditemukan. Mencari tombol 'Watch Now'...")
        watch_now_button_selector = "a:has-text('Watch Now')"
        try:
            page.click(watch_now_button_selector, timeout=5000)
            print("Tombol 'Watch Now' berhasil diklik. Menunggu daftar episode...")
            page.wait_for_selector(episode_list_selector, state='visible', timeout=60000)
            is_list_visible = True
        except TimeoutError:
            print("Tombol 'Watch Now' juga tidak ditemukan atau daftar episode tetap tidak muncul.")
    
    if not is_list_visible:
        raise TimeoutError("Gagal menemukan daftar episode.")

    print("Selector '.episode-list-container' ditemukan! Halaman berhasil dimuat.")
    
    scroll_to_bottom(page)
    
    html_content = page.content()
    soup = BeautifulSoup(html_content, 'html.parser')

    title_element = soup.select_one('.v-card__title h1.text-h6, .anime-info-card .v-card__title span')
    title = title_element.get_text(strip=True) if title_element else 'N/A'
    
    # =========================================================
    # === MENAMBAHKAN KEMBALI PARSING SYNOPSIS DAN IFRAME ===
    # =========================================================
    # Mencari sinopsis di beberapa tempat yang mungkin
    synopsis_element = soup.select_one('div.text-caption, .v-card__text .text-caption')
    synopsis = synopsis_element.get_text(strip=True) if synopsis_element else 'N/A'
    
    iframe_element = soup.select_one('.player-container iframe.player')
    iframe_url = iframe_element['src'] if iframe_element else 'N/A'
    # =========================================================

    all_episode_items_on_page = soup.find_all('div', class_='episode-item')
    total_episodes_on_page = len(all_episode_items_on_page)
    print(f"Judul ditemukan: '{title}'")
    print(f"Total episode ditemukan: {total_episodes_on_page}")

    episodes = []
    for item in all_episode_items_on_page[:5]:
        ep_data = parse_episode_item(item)
        if ep_data:
            episodes.append(ep_data)

    test_data = {
        'title': title,
        'source_url': anime_url,
        'synopsis': synopsis,          # <-- DITAMBAHKAN
        'current_iframe_url': iframe_url,   # <-- DITAMBAHKAN
        'sampled_episodes': episodes,
        'total_episodes_found': total_episodes_on_page
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)

    return f"File tes untuk '{title}' berhasil disimpan di {file_path}"

if __name__ == '__main__':
    os.makedirs(DETAILS_DIR, exist_ok=True)
    p, browser, page = get_browser_page()
    
    try:
        result_message = scrape_anime_details(page, TEST_ANIME_URL)
        print("\n" + "="*50)
        print(f"✅ TES BERHASIL untuk: {TEST_ANIME_URL}")
        print(result_message)
        print("="*50 + "\n")
    except Exception as e:
        print("\n" + "="*50)
        print(f"❌ TES GAGAL untuk: {TEST_ANIME_URL}")
        print(f"Detail error: {e}")
        print("="*50 + "\n")
        exit(1) # Keluar dengan error code jika gagal
    finally:
        print("Menutup browser...")
        browser.close()
        p.stop()
        print("Tes selesai.")
