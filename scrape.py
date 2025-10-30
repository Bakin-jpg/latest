from playwright.sync_api import sync_playwright, TimeoutError
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin
import time

def parse_html_with_bs4(html_content, base_url):
    """
    Fungsi terpisah untuk mem-parsing HTML menggunakan BeautifulSoup.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    latest_update_div = soup.find('div', class_='latest-update')

    if not latest_update_div:
        print("Error: Div 'latest-update' tidak ditemukan.")
        return []

    results = []
    show_items = latest_update_div.find_all('div', class_='show-item')
    print(f"Ditemukan {len(show_items)} item anime untuk di-parse.")

    for item in show_items:
        try:
            title_element = item.find('h2', class_='show-title').find('a')
            title = title_element.get_text(strip=True) if title_element else 'N/A'
            
            relative_link = title_element['href'] if title_element and 'href' in title_element.attrs else ''
            show_link = urljoin(base_url, relative_link)

            image_div = item.find('div', class_='v-image__image')
            image_url = 'N/A'
            if image_div and 'style' in image_div.attrs:
                style_attr = image_div['style']
                match = re.search(r'url\("?(.+?)"?\)', style_attr)
                if match:
                    image_url = match.group(1)
            
            details_container = item.find('div', class_='d-flex')
            details = []
            if details_container:
                chips = details_container.find_all('span', class_='v-chip__content')
                details = [span.get_text(strip=True) for span in chips]

            show_data = {
                'title': title,
                'show_link': show_link,
                'cover_image': image_url,
                'details': details
            }
            results.append(show_data)
        except AttributeError:
            continue
    
    return results

def scrape_with_playwright():
    """
    Menjalankan browser headless, melakukan scroll untuk memuat semua gambar,
    lalu mem-parsing hasilnya.
    """
    base_url = 'https://kickass-anime.ru/'
    results = []
    
    with sync_playwright() as p:
        print("Meluncurkan browser Chromium...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36',
            # Meniru ukuran layar desktop untuk memastikan semua elemen terlihat
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        try:
            print(f"Membuka halaman: {base_url}")
            page.goto(base_url, timeout=90000, wait_until='domcontentloaded')
            
            print("Menunggu elemen pertama muncul...")
            page.wait_for_selector('.latest-update .show-item', timeout=60000)
            
            # --- SOLUSI LAZY LOADING: MENSIMULASIKAN SCROLL ---
            print("Memulai scroll untuk memicu lazy loading gambar...")
            last_height = page.evaluate('document.body.scrollHeight')
            while True:
                # Scroll ke bagian bawah halaman
                page.evaluate('window.scrollTo(0, document.body.scrollHeight);')
                # Tunggu sebentar agar gambar sempat termuat
                time.sleep(2)
                # Cek apakah tinggi halaman sudah tidak bertambah (sudah di paling bawah)
                new_height = page.evaluate('document.body.scrollHeight')
                if new_height == last_height:
                    break
                last_height = new_height
            print("Scroll selesai.")
            # --- AKHIR SOLUSI ---
            
            print("Mengambil konten HTML final setelah scroll...")
            html_content = page.content()
            
            # (Opsional) Simpan HTML untuk debug
            # with open('debug_playwright_scrolled.html', 'w', encoding='utf-8') as f:
            #     f.write(html_content)

            results = parse_html_with_bs4(html_content, base_url)

        except TimeoutError:
            print("Timeout saat menunggu elemen. Mungkin situs lambat atau struktur berubah.")
        except Exception as e:
            print(f"Terjadi kesalahan saat menggunakan Playwright: {e}")
            page.screenshot(path='error_screenshot.png')
        finally:
            print("Menutup browser...")
            browser.close()
            
    return results

if __name__ == '__main__':
    latest_updates = scrape_with_playwright()

    with open('latest_updates.json', 'w', encoding='utf-8') as f:
        json.dump(latest_updates, f, ensure_ascii=False, indent=2)

    print(f"Scraping selesai. {len(latest_updates)} data disimpan di latest_updates.json")
