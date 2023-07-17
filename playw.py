from playwright.sync_api import sync_playwright
import tempfile
from twocaptcha import TwoCaptcha
from bs4 import BeautifulSoup as bs
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from dotenv import load_dotenv
import os
load_dotenv()

solver = TwoCaptcha(os.environ.get('2CAPTCHA_KEY'))


def get_email_from_cer(file_cer):
    with open(file_cer, 'rb') as file:
        cert_data = file.read()
        # Розкодування сертифікату
        cert = x509.load_der_x509_certificate(cert_data, default_backend())
        # Отримання компоненти subject з сертифікату
        subject = cert.subject
        # Пошук електронної адреси в компоненті subject
        email = None
        for attr in subject:
            if attr.oid.dotted_string == '1.2.840.113549.1.9.1':  # OID для email
                email = attr.value
        # Виведення електронної адреси
        return email

def resolve_captcha(img):
    result = solver.normal(img, caseSensitive=1)
    print(result)
    return result

def get_link_from_table(html):
        soup = bs(html, 'lxml')
        table = soup.find(id="resultados:tablaCert:tbtn")
        if table:
            rows = table.find_all('tr')  # Знайти всі рядки таблиці
            for row in rows:
                if 'FIEL' in row.text:
                    first_column = row.find('td')  # Отримати перший стовпець
                    if first_column:
                        link = first_column.find('a')  # Знайти посилання в першому стовпціp
                        if link:
                            return link['href']  # Повернути посилання

        return None  # Якщо не знайдено відпові

def process_page(page):
    temp_file_path = tempfile.mktemp(suffix='.png')  # Create tempfile to save captcha image
    attempts = 3
    captcha = True
    while captcha:
        page.get_by_role("img").nth(1).screenshot(path=temp_file_path)  # find and save screenshot captcha
        result = resolve_captcha(temp_file_path)  # save to result captcha answer
        page.get_by_alt_text("Valor del Captcha").fill(result.get('code'))  # find and fill captcha
        page.get_by_role("button", name="Aceptar").click()  # find and click button form
        page.wait_for_load_state()  # Wait for load event
        bad_captcha = page.locator('strong', has_text="¡Ocurrió un error durante su solicitud!").is_visible()
        good_captcha = page.locator("div", has_text='Recuperación por RFC').nth(3).is_visible()
        if bad_captcha:
            solver.report(result.get('captchaId'), False)
            btn = page.get_by_role("button", name="Regresar")
            if btn.is_visible():
                btn.click()
                page.wait_for_load_state()
            else:
                print('dont see btn')
        if good_captcha:
            print('success')
            solver.report(result.get('captchaId'), True)
            # captcha = False
            page.fill('input[name="consultaCertificados:entradaRFC"]', 'CCC210128ER7')  # Enter text data to input
            # find captcha and save screenshot
            while captcha:
                page.get_by_role("img").nth(1).screenshot(path=temp_file_path)
                # resolve captcha
                result = resolve_captcha(temp_file_path)
                # find input and enter captcha
                page.get_by_alt_text("Valor del Captcha").fill(result.get('code'))
                # find button to send form and click
                page.locator("[id=\"consultaCertificados\\:botonRFC\"]").click()
                page.wait_for_load_state()  # Wait for load event
                bad_captcha = page.locator("div", has_text='Recuperación por RFC').nth(3).is_visible()
                if not bad_captcha:
                    solver.report(result.get('captchaId'), True)
                    # if page.get_by_role("cell", name="FIEL", exact=True):
                    captcha = False
                    page.wait_for_load_state()
                    print('goodcaptcha')
                    download_link = get_link_from_table(page.content())
                    print('link', download_link)
                    page.on("download", lambda download: print(download.path()))
                    with page.expect_download() as download_file:
                        page.locator(f'[href*="{download_link}"]').click()
                    download = download_file.value
                    email = get_email_from_cer(download.path())
                    with open('email.txt', 'w') as f:
                        f.write(email)
                    # download_file(download_link)
                else:
                    solver.report(result.get('captchaId'), False)
                    print('bad captcha')
        else:
            print('Something wrong')

def process_pages(pages):
    for page in pages:
        process_page(page)

def main():

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)#Launch chromium
        context = browser.new_context()
        page = context.new_page()#Create new page
        page.goto("https://portalsat.plataforma.sat.gob.mx/RecuperacionDeCertificados/")#Go to Site
        additional_pages = [context.new_page() for _ in range(3)]  # Example: process 3 additional pages
        process_pages(additional_pages)

# from bs4 import BeautifulSoup as bs
# from urllib3.util import create_urllib3_context
# from urllib3 import PoolManager
# from requests.adapters import HTTPAdapter
# from requests import Session
# from PIL import Image
# from io import BytesIO
# from fake_useragent import UserAgent
# import tempfile
# from twocaptcha import TwoCaptcha
#
#
# class AddedCipherAdapter(HTTPAdapter):
#   def init_poolmanager(self, connections, maxsize, block=False):
#     ctx = create_urllib3_context(ciphers=":HIGH:!DH:!aNULL")
#     self.poolmanager = PoolManager(
#       num_pools=connections,
#       maxsize=maxsize,
#       block=block,
#       ssl_context=ctx
#     )
#
#
# def main():
#     ua = UserAgent()
#     base_url = 'https://portalsat.plataforma.sat.gob.mx'
#     url = 'https://portalsat.plataforma.sat.gob.mx/RecuperacionDeCertificados'
#     session = Session()
#     session.mount(base_url, AddedCipherAdapter())
#     response = session.get(url)
#     cookies = response.cookies
#     print(cookies)
#     if response.status_code == 200:
#         soup = bs(response.text, 'lxml')
#         img = soup.find_all('img')
#         hide_input = soup.find('input', {'type':'hidden' , 'name': 'javax.faces.ViewState'})
#         img = [i.get('src') for i in img if i.get('height') == '50']
#         response = session.get(f'{base_url}{img[0]}')
#         temp_file_path = tempfile.mktemp(suffix='.jpg')
#         image = Image.open(BytesIO(response.content))
#         image = image.convert('RGB')
#         image.save('TEST.jpg', 'JPEG')
#         image.save(temp_file_path, 'JPEG')
#         solver = TwoCaptcha('b881cd06fb0b03e34cd95e4bb7a6f55f')
#         result = solver.normal(temp_file_path, caseSensitive=1)
#         form_post = '/RecuperacionDeCertificados/faces/index.xhtml'
#         print(result)
#         data = {
#             'form': 'form',
#             'form: verTexto': result.get('code'),
#             'form: j_idt21': 'Aceptar',
#             'javax.faces.ViewState': hide_input.get('value'),
#         }
#         print(result.get('code'))
#         headers = {
#             'user-agent': ua.random,
#             "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
#             "accept-language": "en-US,en;q=0.9,uk-UA;q=0.8,uk;q=0.7,pl;q=0.6",
#             "cache-control": "max-age=0",
#             "content-type": "application/x-www-form-urlencoded",
#             "sec-ch-ua": "Not.A/Brand;v=8, Chromium;v=114, Google Chrome;v=114",
#             "sec-ch-ua-mobile": "?0",
#             "sec-ch-ua-platform": "Windows",
#             "Referer" : 'https://portalsat.plataforma.sat.gob.mx/RecuperacionDeCertificados/faces/index.xhtml'
#         }
#         response = session.post(f'{base_url}{form_post}', data=data, headers=headers, cookies=cookies)
#         print(response.content)
#
#         if response.status_code == 200:
#             print('Форма успішно відправлена!')
#             print(response.history)
#             if 'Recuperación por RFC:' in response:
#                 solver.report(result.get('captchaId'), True)
#                 print("Відбулося перенаправлення")
#                 # Отримання остаточного URL після перенаправлення
#                 final_url = response.url
#                 print("Остаточний URL:", final_url)
#             if '¡Ocurrió un error durante su solicitud!' in response:
#                 print("Перенаправлення не відбулося")
#                 final_url = response.url
#                 print("Остаточний URL:", final_url)
#                 solver.report(result.get('captchaId'), False)
#             else:
#                 print('fail')
#         else:
#             print('Помилка при відправці форми.')

if __name__ == '__main__':
    main()
    # with open('Recuperación de Certificados.html','r') as f:
    #     html = f.read()
    #     print(get_link_from_table(html))
    # get_emain_with_cer()