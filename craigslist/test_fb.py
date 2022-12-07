import re
from enum import Enum


EXISTING_POST_FILENAME = 'existing_posts_fb.txt'
NEW_POST_FILENAME = 'new_posts_fb.txt'
LOGIN_FILENAME = 'login_fb.txt'
SETTING_FILENAME = 'settings_fb.yaml'
EXECUTION_LOG_FILENAME = 'execution_fb.log'
SLEEPING_TIME = 60
DEBUG_FILENAME = 'debug_fb.html'
DEFAULT_EMAIL = 'drhsheng@gmail.com'
NIGHT_SLEEPING_TIME = 3600
MAX_NUM_EMAIL_PER_DAY = 200
EMAIL_COUNTER_KEY = 'EMAIL_COUNTER'
GECKODRIVER_LOG = 'geckodriver.log'

PAGE_URL = 'https://www.facebook.com/groups/2621840064559532?sorting_setting=CHRONOLOGICAL'
LOGIN_URL = "https://www.facebook.com/login/device-based/regular/login/?login_attempt=1&next=https%3A%2F%2Fwww.facebook.com%2Fgroups%2F2621840064559532%3Fsorting_setting%3DCHRONOLOGICAL"
MY_IMG_LINK = 'https://scontent-sjc3-1.xx.fbcdn.net/v/t1.6435-1/67716435_2340044926083401_8053815337931505664_n.jpg'

POST_PATTERN = (
    '<a class=".*?" href="'
    + '(https://www.facebook.com/groups/2621840064559532/posts/\d+)/.*?" role="link"'
    + ".*?"
    + 'aria-haspopup="menu" aria-label="Actions for this post"'
    + "(.*?)"
    + 'Write (?:a comment|an answer).{1,3}</div>'
)
IMG_PATTERN = '"(https://scontent.*?)"'
TXT_PATTERN = '<div dir="auto" style="text-align:.*?">(.*?)</div>'
POST_PATTERN = re.compile(POST_PATTERN)
IMG_PATTERN = re.compile(IMG_PATTERN)
TXT_PATTERN = re.compile(TXT_PATTERN)


# post_id, post_link, all_txts, all_imgs
class patternName(int, Enum):
    POST_ID = 0
    POST_LINK = 1
    TXT = 2
    IMG_LINK = 3


def make_html_body(post_tuple):
    # post_id = post_tuple[patternName.POST_ID]
    all_txts = post_tuple[patternName.TXT]
    post_link = post_tuple[patternName.POST_LINK]
    all_imgs = post_tuple[patternName.IMG_LINK]
    all_txts_lower = all_txts.lower()
    if all_txts_lower.find('gift') != -1 or all_txts_lower.find('iso') == -1:
        html_body = (
            f"<a href=\"" + post_link + "\"><br>" + all_txts + "<br></a>"
        )
        if all_imgs:
            for img_link in all_imgs:
                html_body += "<a href=\"" + post_link + "\">" + "<img src=\"" + img_link + "\">" + "</a>" + "<br>"
        return html_body
    else:
        return ''


def work_find(page_source):
    post_pattern = POST_PATTERN
    all_posts = re.findall(post_pattern, page_source)
    print(all_posts)
    results = []
    if all_posts:
        img_pattern = IMG_PATTERN
        txt_pattern = TXT_PATTERN
        for post in all_posts:
            post_link = post[0]
            post_content = post[1]
            post_id = post_link.split('/')[-1]
            all_imgs = re.findall(img_pattern, post_content)
            if all_imgs:
                all_imgs = [img_link for img_link in all_imgs if not img_link.startswith(MY_IMG_LINK)]
            else:
                all_imgs = []
            all_txts = re.findall(txt_pattern, post_content)
            if all_txts:
                all_txts = ' '.join(all_txts)
            else:
                all_txts = ''
            all_txts_lower = all_txts.lower()
            if all_txts_lower.find('gift') != -1 or all_txts_lower.find('iso') == -1:
                results.append((post_id, post_link, all_txts, all_imgs))
    return results


def main():
    with open('debug.html', 'rt') as fp:
        page_source = fp.read()
        print(work_find(page_source))


if __name__ == '__main__':
    main()
