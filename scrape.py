import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin

def scrape_latest_updates():
    """
    Fungsi untuk melakukan scraping data update anime terbaru dari kickass-anime.ru.
    """
    base_url = 'https://kickass-anime.ru/'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        latest_update_div = soup.find('div', class_='latest-update')

        if not latest_update_div:
            print("Error: Div 'latest-update' tidak ditemukan.")
            return []

        results = []
        show_items = latest_update_div.find_all('div', class_='show-item')

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

    except requests.exceptions.RequestException as e:
        print(f"Error saat mengambil halaman web: {e}")
        return []
    except Exception as e:
        print(f"Error saat parsing: {e}")
        return []

if __name__ == '__main__':
    # Jalankan fungsi scraping
    latest_updates = scrape_latest_updates()

    # Simpan hasil ke file JSON
    # 'indent=2' membuat file JSON lebih mudah dibaca
    with open('latest_updates.json', 'w', encoding='utf-8') as f:
        json.dump(latest_updates, f, ensure_ascii=False, indent=2)

    print("Scraping selesai. Data disimpan di latest_updates.json")
