from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin
import time
import os

BASE_URL = 'https://kickass-anime.ru'

def get_browser_page():
    """Membuka browser dan halaman baru, lalu mengembalikannya."""
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
    """Mensimulasikan scroll ke bawah untuk memuat semua konten lazy load."""
    print("Memulai scroll untuk memicu lazy loading...")
    last_height = page.evaluate('document.body.scrollHeight')
    while True:
        page.evaluate('window.scrollTo(0, document.body.scrollHeight);')
        time.sleep(2)
        new_height = page.evaluate('document.body.scrollHeight')
        if new_height == last_height:
            break
        last_height = new_height
    print("Scroll selesai.")

def scrape_homepage(page):
    """Scrape daftar anime terbaru dari halaman utama."""
    print(f"Membuka halaman utama: {BASE_URL}/")
    page.goto(f"{BASE_URL}/", timeout=90000, wait_until='domcontentloaded')
    page.wait_for_selector('.latest-update .show-item', timeout=60000)
    
    scroll_to_bottom(page)
    
    html_content = page.content()
    soup = BeautifulSoup(html_content, 'html.parser')
    latest_update_div = soup.find('div', class_='latest-update')

    if not latest_update_div:
        return []

    results = []
    show_items = latest_update_div.find_all('div', class_='show-item')
    print(f"Ditemukan {len(show_items)} item di halaman utama.")

    for item in show_items:
        try:
            title_element = item.find('h2', class_='show-title').find('a')
            title = title_element.get_text(strip=True)
            relative_link = title_element['href']
            show_link = urljoin(BASE_URL, relative_link)
            
            image_div = item.find('div', class_='v-image__image')
            style_attr = image_div['style']
            match = re.search(r'url\("?(.+?)"?\)', style_attr)
            cover_image = match.group(1) if match else 'N/A'

            results.append({
                'title': title,
                'detail_page_url': show_link,
                'cover_image': cover_image
            })
        except Exception:
            continue
            
    return results

def scrape_anime_details(page, anime_url):
    """Scrape detail dari satu halaman anime."""
    print(f"Membuka halaman detail: {anime_url}")
    page.goto(anime_url, timeout=90000, wait_until='domcontentloaded')
    
    # Tunggu elemen kunci dari halaman detail
    page.wait_for_selector('.episode-list-container', timeout=60000)
    scroll_to_bottom(page)

    html_content = page.content()
    soup = BeautifulSoup(html_content, 'html.parser')

    # Ekstrak data
    title = soup.find('h1', class_='text-h6').get_text(strip=True) if soup.find('h1', class_='text-h6') else 'N/A'
    synopsis = soup.select_one('.v-card__text .text-caption').get_text(strip=True) if soup.select_one('.v-card__text .text-caption') else 'N/A'
    
    # URL Iframe Video untuk episode yang sedang aktif
    iframe = soup.select_one('.player-container iframe.player')
    iframe_url = iframe['src'] if iframe else 'N/A'
    
    # Daftar Episode
    episodes = []
    episode_items = soup.find_all('div', class_='episode-item')
    print(f"Ditemukan {len(episode_items)} episode.")

    for item in episode_items:
        try:
            # Tautan episode perlu dibangun dari card itu sendiri karena tidak ada tag <a>
            card_link_tag = item.find('div', class_='v-card--link')
            link_js = card_link_tag['onclick'] if card_link_tag and 'onclick' in card_link_tag.attrs else ''
            relative_link = link_js.split("'")[1] if "'" in link_js else ''
            
            episode_num_tag = item.find('span', class_='episode-badge')
            episode_num = episode_num_tag.get_text(strip=True) if episode_num_tag else 'N/A'

            thumbnail_div = item.find('div', class_='v-image__image')
            thumbnail_url = 'N/A'
            if thumbnail_div and 'style' in thumbnail_div.attrs:
                style_attr = thumbnail_div['style']
                match = re.search(r'url\("?(.+?)"?\)', style_attr)
                thumbnail_url = match.group(1) if match else 'N/A'

            episodes.append({
                'episode_number': episode_num,
                'episode_url': urljoin(BASE_URL, relative_link),
                'thumbnail_url': thumbnail_url
            })
        except Exception:
            continue

    return {
        'title': title,
        'source_url': anime_url,
        'synopsis': synopsis,
        'current_episode_iframe': iframe_url,
        'total_episodes': len(episodes),
        'episodes': episodes
    }

if __name__ == '__main__':
    # Pastikan direktori 'details' ada
    os.makedirs('details', exist_ok=True)
    
    p, browser, page = get_browser_page()

    try:
        # 1. Scrape halaman utama
        homepage_data = scrape_homepage(page)
        with open('homepage.json', 'w', encoding='utf-8') as f:
            json.dump(homepage_data, f, ensure_ascii=False, indent=2)
        print(f"Halaman utama berhasil di-scrape, {len(homepage_data)} anime ditemukan dan disimpan di homepage.json")

        # 2. Scrape detail untuk setiap anime
        for anime in homepage_data:
            anime_slug = anime['detail_page_url'].split('/')[-1]
            file_path = f"details/{anime_slug}.json"
            
            try:
                details = scrape_anime_details(page, anime['detail_page_url'])
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(details, f, ensure_ascii=False, indent=2)
                print(f"Detail untuk '{anime['title']}' berhasil disimpan di {file_path}")
            except Exception as e:
                print(f"Gagal memproses detail untuk {anime['title']}: {e}")
                # Jika gagal, buat file kosong atau error
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump({"error": str(e), "url": anime['detail_page_url']}, f, indent=2)

    finally:
        browser.close()
        p.stop()
        print("Proses selesai.")
