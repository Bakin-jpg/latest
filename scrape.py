from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin
import time
import os

BASE_URL = 'https://kickass-anime.ru'
DETAILS_DIR = 'details'
# Batas cicilan diatur menjadi 10 episode per eksekusi
MAX_EPISODES_PER_RUN = 10

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
        for _ in range(10): # Batasi scroll maksimal 10 kali untuk mencegah loop tak terbatas
            page.evaluate('window.scrollTo(0, document.body.scrollHeight);')
            time.sleep(2) # Jeda untuk memuat konten
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
    """Scrape detail anime dengan logika update dan cicilan yang disempurnakan."""
    anime_slug = anime_url.split('/')[-1]
    file_path = os.path.join(DETAILS_DIR, f"{anime_slug}.json")
    
    existing_data = None
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            print(f"File lama ditemukan untuk {anime_slug}. Memeriksa pembaruan...")
        except json.JSONDecodeError:
            print(f"File {file_path} rusak. Akan di-scrape ulang.")
            existing_data = None

    print(f"Membuka halaman detail: {anime_url}")
    page.goto(anime_url, timeout=90000, wait_until='domcontentloaded')
    page.wait_for_selector('.episode-list-container', timeout=60000)
    
    scroll_to_bottom(page)
    
    html_content = page.content()
    soup = BeautifulSoup(html_content, 'html.parser')

    all_episode_items_on_page = soup.find_all('div', class_='episode-item')
    total_episodes_on_page = len(all_episode_items_on_page)
    print(f"Total episode di halaman: {total_episodes_on_page}")
    
    num_existing_episodes = len(existing_data['episodes']) if existing_data and 'episodes' in existing_data else 0

    if existing_data and num_existing_episodes == total_episodes_on_page:
        print("Data sudah lengkap dan tidak ada episode baru. Melewati.")
        return None

    title = soup.find('h1', class_='text-h6').get_text(strip=True) if soup.find('h1', class_='text-h6') else 'N/A'
    synopsis = soup.select_one('.v-card__text .text-caption').get_text(strip=True) if soup.select_one('.v-card__text .text-caption') else 'N/A'
    iframe = soup.select_one('.player-container iframe.player')
    iframe_url = iframe['src'] if iframe else 'N/A'
    
    final_data = existing_data if existing_data else {
        'title': title, 'source_url': anime_url, 'synopsis': synopsis,
        'episodes': [], 'total_episodes_on_page': 0
    }
    final_data.update({'title': title, 'synopsis': synopsis, 'current_episode_iframe': iframe_url, 'total_episodes_on_page': total_episodes_on_page})

    episodes_to_scrape_html = []
    
    if existing_data and total_episodes_on_page > num_existing_episodes:
        num_new_episodes = total_episodes_on_page - num_existing_episodes
        print(f"Mode UPDATE: Ditemukan {num_new_episodes} episode baru.")
        episodes_to_scrape_html = all_episode_items_on_page[:num_new_episodes]
    
    elif not existing_data or num_existing_episodes < total_episodes_on_page:
        start_index = num_existing_episodes
        end_index = min(start_index + MAX_EPISODES_PER_RUN, total_episodes_on_page)
        print(f"Mode CICILAN: Mengambil episode dari index {start_index} hingga {end_index-1}.")
        episodes_from_web_reversed = list(reversed(all_episode_items_on_page))
        episodes_to_scrape_html = episodes_from_web_reversed[start_index:end_index]

    newly_scraped_episodes = []
    for item in episodes_to_scrape_html:
        ep_data = parse_episode_item(item)
        if ep_data:
            newly_scraped_episodes.append(ep_data)

    if not (existing_data and total_episodes_on_page > num_existing_episodes):
        newly_scraped_episodes.reverse()

    final_data['episodes'] = newly_scraped_episodes + final_data.get('episodes', [])
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    return f"Detail untuk '{title}' disimpan/diperbarui. Total episode tersimpan: {len(final_data['episodes'])}/{total_episodes_on_page}"

def scrape_homepage(page):
    print(f"Membuka halaman utama: {BASE_URL}/")
    page.goto(f"{BASE_URL}/", timeout=90000, wait_until='domcontentloaded')
    page.wait_for_selector('.latest-update .show-item', timeout=60000)
    scroll_to_bottom(page)
    
    html_content = page.content()
    soup = BeautifulSoup(html_content, 'html.parser')
    latest_update_div = soup.find('div', class_='latest-update')

    results = []
    if latest_update_div:
        show_items = latest_update_div.find_all('div', class_='show-item')
        print(f"Ditemukan {len(show_items)} item di halaman utama.")
        for item in show_items:
            try:
                title_element = item.find('h2', class_='show-title').find('a')
                title = title_element.get_text(strip=True)
                relative_link = title_element['href']
                show_link = urljoin(BASE_URL, relative_link)
                # Di homepage kita hanya butuh ini
                results.append({'title': title, 'detail_page_url': show_link})
            except Exception: continue
    return results

if __name__ == '__main__':
    os.makedirs(DETAILS_DIR, exist_ok=True)
    
    p, browser, page = get_browser_page()

    try:
        homepage_data = scrape_homepage(page)
        
        with open('homepage.json', 'w', encoding='utf-8') as f:
            json.dump(homepage_data, f, ensure_ascii=False, indent=2)
        print(f"Homepage berhasil di-scrape, {len(homepage_data)} anime ditemukan.")
        
        for anime in homepage_data:
            try:
                result_message = scrape_anime_details(page, anime['detail_page_url'])
                if result_message:
                    print(result_message)
            except Exception as e:
                print(f"Gagal memproses detail untuk {anime['title']}: {e}")

    finally:
        browser.close()
        p.stop()
        print("Proses selesai.")
