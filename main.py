import time
import requests
from bs4 import BeautifulSoup as Soup
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import os


ANTICAPTCHA_API_URL = os.environ["ANTICAPTCHA_API_URL"]
CLIENT_KEY = os.environ["ANTICAPTCHA_CLIENT_KEY"]
PROXY_URL = os.environ["PROXY_URL"]  # Example: http://username:pwd@domain:port
GMAIL_USERNAME = os.environ["GMAIL_USERNAME"]
GMAIL_PASSWORD = os.environ["GMAIL_PASSWORD"]


def create_task(task_data: dict) -> str:
    url = f"{ANTICAPTCHA_API_URL}/createTask"
    data = {
        "clientKey": CLIENT_KEY,
        "task": {**task_data},
        "softId": 0,
    }
    res = requests.post(url, json=data)
    result: dict = res.json()
    error_code = result.get("errorCode")
    if error_code:
        raise RuntimeError("Failed to create anti-captcha task, error code: %s" % error_code)
    return result.get("taskId")


def get_solution(task_id: int):
    url = f"{ANTICAPTCHA_API_URL}/getTaskResult"
    data = {"clientKey": CLIENT_KEY, "taskId": task_id}
    i = 0
    while i < 10:
        print("Waiting.")
        time.sleep(5)
        res = requests.post(url, json=data)
        result = res.json()
        error_code = result.get("errorCode")
        if error_code:
            print(result)
            raise RuntimeError("Anti-captcha failed to solve task, error code %s" % str(error_code))
        if result.get("status") == "ready":
            return result.get("solution")
        i += 1

    print("Failed to get solution.")
    raise RuntimeError("Captcha solution took too long.")


def get_proxies():
    """You can also ignore proxy at all."""
    return {"http": PROXY_URL, "https": PROXY_URL}


def send_email(subject, body, sender, recipients, password):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    smtp_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    smtp_server.login(sender, password)
    smtp_server.sendmail(sender, recipients, msg.as_string())
    smtp_server.quit()

tries = 0
max_tries = 4
while tries < max_tries:
    try:
        tries += 1
        url = "https://service2.diplo.de/rktermin/extern/appointment_showMonth.do?locationCode=kara&realmId=773&categoryId=1999"
        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "accept-language": "en-US,en;q=0.9",
            "sec-ch-ua": "\"Chromium\";v=\"109\", \"Not_A Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Linux\"",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"

        }
        resp = requests.get(url, headers=headers, proxies=get_proxies())
        cookies = resp.cookies.get_dict()
        f = open("response.html", "w")
        f.write(resp.text)

        soup = Soup(resp.text)
        style_txt = soup.select_one("captcha").select_one("div").get("style")
        styles_lst = style_txt.split(" ")
        start_str = "url('data:image/jpg;base64,"
        end_str = "')"
        image_style = [s for s in styles_lst if s.startswith(start_str)][0]
        image_txt = image_style[len(start_str): len(image_style) - len(end_str)]
        print(image_txt)
        task_data = {
            "type": "ImageToTextTask",
            "body": image_txt,
        }
        task_id = create_task(task_data)
        solution = get_solution(task_id)["text"]
        # solution = input("Solution? ")
        print(solution)
        submit_url = f"https://service2.diplo.de/rktermin/extern/appointment_showMonth.do;jsessionid={cookies.get('JSESSIONID')}"
        data = {
            "captchaText": solution,
            "rebooking": False,
            "token": "",
            "lastname": "",
            "firstname": "",
            "email": "",
            "locationCode": "kara",
            "realmId": 773,
            "categoryId": 1999,
            "openingPeriodId": "",
            "date": "",
            "dateStr": "",
            "action:appointment_showMonth": "Continue"
        }

        headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "max-age=0",
            "content-type": "application/x-www-form-urlencoded",
            "sec-ch-ua": "\"Chromium\";v=\"109\", \"Not_A Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Linux\"",
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            # "cookie": "JSESSIONID=12FDF6552591A8EC76C6FD383C71A95D; KEKS=TERMIN344",
            "Referer": "https://service2.diplo.de/rktermin/extern/appointment_showMonth.do",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
        }
        print(cookies)
        resp = requests.post(submit_url, data=data, cookies=cookies, headers=headers, proxies=get_proxies())

        f = open("response.html", "w")
        f.write(resp.text)
        f.close()

        if resp.status_code != 200:
            raise RuntimeError("Failed to submit captcha response.")
        
        if "The entered text was wrong" in resp.text:
            continue

        not_available_msg = "Unfortunately, there are no appointments available at this time."

        if not_available_msg in resp.text:
            exit()

        filename = f"post_response_success_{datetime.now().isoformat()}.html"
        f = open(filename, "w")
        f.write(resp.text)
        f.close()
        subject = "Important: Visa Appointment Update"
        body = "Hi, appointments may be available at the German Consulate Karachi. Hurry up and reserve your slot!"
        sender = GMAIL_USERNAME
        recipients = [GMAIL_USERNAME]
        password = GMAIL_PASSWORD
        send_email(subject, body, sender, recipients, password)
        
        exit()
    
    except Exception as ex:
        print(ex)