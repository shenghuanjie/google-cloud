import time
import re
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException


PAGE_URL = 'https://www.facebook.com/groups/2621840064559532?sorting_setting=CHRONOLOGICAL'

MY_IMG_LINK = 'https://scontent-sjc3-1.xx.fbcdn.net/v/t1.6435-1/67716435_2340044926083401_8053815337931505664_n.jpg'

def make_html_body(post_link, post, img_pattern=None, txt_pattern=None):
    all_imgs = re.findall(img_pattern, post)
    all_txts = ' '.join(re.findall(txt_pattern, post))
    all_txts_lower = all_txts.lower()
    if all_txts_lower.find('gift') != -1 or all_txts_lower.find('iso') == -1:
        html_body = (
            f"<a href=\"" + post_link + "\"><br>" + all_txts + "<br></a>"
        )
        if all_imgs:
            for img_link in all_imgs:
                if not img_link.startswith(MY_IMG_LINK):
                    html_body += "<a href=\"" + post_link + "\">" + "<img src=\"" + img_link + "\">" + "</a>" + "<br>"
        return html_body
    else:
        return ''


def test():
    pattern = '(?:<img alt=(?:\"\" src=|)\"(.*?)\">|he(ll)o)'
    string = 'hello'
    import re
    pattern_re = re.compile(pattern)
    print(re.findall(pattern, string))


def find_post(existing_post_ids=None):
    existing_post_ids = set()

    with open('test.txt', 'r', encoding='utf-8') as fp:
        page_source = fp.read()

    # + '(<div dir="auto" style="text-align:.*?">.*?</div>)'
    PATTERN = (
        '<a class=".*?" href="(https://www.facebook.com/groups/2621840064559532/posts/\d+)/.*?" role="link" tabindex="0">'
        # "<span>Buy Nothing Fremont, Newark and Union City, CA</span>"
        + ".*?"
        + 'aria-haspopup="menu" aria-label="Actions for this post"'
        + "(.*?)"
        # '(?:<img alt=.*? class=.*? src="(https://.*?)" width="\d+" height="\d+">|<div aria-label="Leave a comment")'
        # + ".*?"
        + 'Write a comment.</div>'
        # + ".*?"
        # + 'Write a comment'
    )
    IMG_PATTERN = '"(https://scontent.*?)"'
    TXT_PATTERN = '<div dir="auto" style="text-align:.*?">(.*?)</div>'
    pattern = re.compile(PATTERN)
    img_pattern = re.compile(IMG_PATTERN)
    txt_pattern = re.compile(TXT_PATTERN)

    all_posts = re.findall(pattern, page_source)
    html_txt = []
    for post in all_posts:
        post_id = post[0].split('/')[-1]
        if post_id not in existing_post_ids:
            html_txt.append(make_html_body(*post, img_pattern=img_pattern, txt_pattern=txt_pattern))
            existing_post_ids.add(post_id)
    html_txt = ''.join(html_txt)
    with open('result.html', 'w', encoding='utf-8') as fp:
        print(html_txt, file=fp)

    # import pdb; pdb.set_trace()


def main():
    # url = 'https://sfbay.craigslist.org/search/sby/zip?postedToday=1&query=%20supply%20%7C%20everything%7C%20good%20%7C%20grass%20%7C%20new%20%7C%20garden%20%7C%20hula%20%7C%20excellent%20%7C%20cooler%20%7C%20paint%20%7C%20electronics%20%7C%20great%20%7C%20working%20%7C%20tools%20%7Cgravel%20&sort=date&postal=94538&search_distance=25#search=1~gallery~0~0'
    page_url = 'https://www.facebook.com/groups/2621840064559532?sorting_setting=CHRONOLOGICAL'
    login_url = "https://www.facebook.com/login/device-based/regular/login/?login_attempt=1&next=https%3A%2F%2Fwww.facebook.com%2Fgroups%2F2621840064559532%3Fsorting_setting%3DCHRONOLOGICAL"
    ichunk = 2
    num_chunks = 3

    # firefox_profile = webdriver.FirefoxProfile()
    # firefox_profile.set_preference("general.useragent.override", "whatever you want")
    firefox_options = webdriver.FirefoxOptions()
    # firefox_options.add_argument("--headless")
    # firefox_options.add_argument("start-maximized")
    # firefox_options.add_argument("disable-infobars")
    # firefox_options.add_argument("--disable-extensions")
    firefox_options.add_argument('--no-sandbox')
    # firefox_options.add_argument('--disable-application-cache')
    firefox_options.add_argument('--disable-gpu')
    # firefox_options.add_argument("--disable-dev-shm-usage")
    # firefox_options.add_argument("user-agent={user_agent}")
    browser = webdriver.Firefox(options=firefox_options)
    browser.get(login_url)
    email_field = browser.find_element_by_css_selector("input[name='email'][type='text']")
    password_field = browser.find_element_by_css_selector("input[name='pass'][type='password']")
    login_field = browser.find_element_by_css_selector("button[name='login'][type='submit']")

    with open(login_filename, 'rt', encoding='utf-8') as fp:
        username = fp.readline().strip()
        password = fp.readline().strip()
    email_field.send_keys(username)
    password_field.send_keys(password)
    login_field.click()

    # wait for 2-step
    try:
        receive_code = browser.find_element_by_css_selector("input[aria-label='Login code'][type='text']")
    except NoSuchElementException:
        # maybe the page has not been loaded yet.
        receive_code = True
    while receive_code is not None:
        print('Log in not authorized yet, wait for 5 seconds.')
        time.sleep(5)
        # <input type="text" class="inputtext" id="approvals_code" name="approvals_code" tabindex="1" autocomplete="off" placeholder="Login code" aria-label="Login code">
        try:
            receive_code = browser.find_element_by_css_selector("input[aria-label='Login code'][type='text']")
        except NoSuchElementException:
            print('Log in authorized yet, proceed to posts.')
            break

    browser.get(page_url)
    time.sleep(0.5)
    for _ in range(10):
        browser.execute_script("window.scrollTo({top: Math.round(document.body.scrollHeight), behavior: 'smooth'});")
        time.sleep(0.5)
    page_source = browser.page_source
    with open('test.txt', 'w', encoding='utf-8') as fp:
        print(page_source, file=fp)

    # + '(<div dir="auto" style="text-align:.*?">.*?</div>)'
    PATTERN = (
        '<a class=".*?" href="(https://www.facebook.com/groups/2621840064559532/posts/\d+)/.*?" role="link" tabindex="0">'
        # "<span>Buy Nothing Fremont, Newark and Union City, CA</span>"
        + ".*?"
        + 'aria-haspopup="menu" aria-label="Actions for this post"'
        + "(.*?)"
        # '(?:<img alt=.*? class=.*? src="(https://.*?)" width="\d+" height="\d+">|<div aria-label="Leave a comment")'
        # + ".*?"
        + 'Write a comment.</div>'
        # + ".*?"
        # + 'Write a comment'
    )
    IMG_PATTERN = '"(https://scontent.*?)"'
    TXT_PATTERN = '<div dir="auto" style="text-align:.*?">(.*?)</div>'
    pattern = re.compile(PATTERN)
    img_pattern = re.compile(IMG_PATTERN)
    txt_pattern = re.compile(TXT_PATTERN)

    all_posts = re.findall(pattern, page_source)
    html_txt = []
    for post in all_posts:
        post_id = post[0].split('/')[-1]
        if post_id not in existing_post_ids:
            html_txt.append(make_html_body(*post, img_pattern=img_pattern, txt_pattern=txt_pattern))
            existing_post_ids.add(post_id)
    html_txt = ''.join(html_txt)


if __name__ == '__main__':
    find_post()
