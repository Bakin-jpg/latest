from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin
import time

def parse_html_with_bs4(html_content, base_url):
    """
    Fungsi terpisah untuk mem-parsing HTML menggunakan BeautifulSoup.
    Ini dipanggil setelah Playwright mendapatkan konten halaman yang sudah dirender.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    latest_update_div = soup.find('div', class_='latest-update')

    if not latest_update_div:
        print("Error: Div 'latest-update' tidak ditemukan bahkan setelah render JS.")
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
    Menjalankan browser headless untuk membuka halaman, menunggu konten dinamis,
    lalu mem-parsing hasilnya.
    """
    base_url = 'https://kickass-anime.ru/'
    results = []
    
    with sync_playwright() as p:
        print("Meluncurkan browser Chromium...")
        browser = p.chromium.launch(headless=True)
        
        # Meniru browser Chrome di Windows 10
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36'
        )
        page = context.new_page()

        try:
            print(f"Membuka halaman: {base_url}")
            # Menambah timeout agar tidak gagal di koneksi lambat
            page.goto(base_url, timeout=90000) # Timeout 90 detik
            
            print("Menunggu selector '.latest-update .show-item' muncul...")
            # Ini adalah langkah kunci: menunggu elemen yang dibuat oleh JS muncul
            page.wait_for_selector('.latest-update .show-item', timeout=60000) # Timeout 60 detik
            
            print("Elemen ditemukan. Memberi waktu sejenak untuk render penuh...")
            time.sleep(5) # Jeda 5 detik untuk memastikan semua gambar/data termuat

            print("Mengambil konten HTML halaman...")
            html_content = page.content()
            
            # Simpan HTML untuk debug jika diperlukan
            with open('debug_playwright.html', 'w', encoding='utf-8') as f:
                f.write(html_content)

            # Memanggil fungsi parsing
            results = parse_html_with_bs4(html_content, base_url)

        except Exception as e:
            print(f"Terjadi kesalahan saat menggunakan Playwright: {e}")
            # Jika error, coba ambil screenshot untuk diagnosis
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
