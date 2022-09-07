import argparse
from email.mime.text import MIMEText
import os
import re
import random
import smtplib
from sys import platform
import time

from datetime import datetime
from datetime import time as datetime_time
import pytz
import logging
from enum import Enum
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
import yaml
if platform == "win32":
    from win10toast import ToastNotifier


logger = logging.getLogger(__name__)


EXISTING_POST_FILENAME = 'existing_posts.txt'
SLEEPING_TIME = 60
DEBUG_FILENAME = 'debug.html'
DEFAULT_EMAIL = 'drhsheng@gmail.com'
NIGHT_SLEEPING_TIME = 3600
POST_PATTERN = (
    "class=\"cl-search-result cl-search-view-mode-gallery\""
    + ".*?"
    + "<img alt=(?:\"\" src=|)\"(.*?)\">"
    + ".*?"
    + "<a .*? href=\"(https://sfbay.craigslist.org/.*?/zip/\\d+.html?)\" class=\"post-title\">"
    + ".*?"
    + "<time class=\"post-date\" datetime=\"(\\d+-\\d+-.*?:\\d+:\\d+.*?)\">.*?</time>"
    + ".*?"
    + "<span class=\"label\">(.*?)</span></a>"
    + "<div class=\"bottom-row\"><button type=\"button\".*?</button><span class=\"post-hood\">(.*?)</span><span class=\"distance\">(.*?)</span>"
)


class patternName(int, Enum):
    IMG_LINK = 0
    POST_LINK = 1
    TIME = 2
    TITLE = 3
    LOCATION = 4
    DISTANCE = 5


def setup_logging(log_file):
    fmt = '%(asctime)s %(levelname)-9s: [%(name)s:%(lineno)s]: %(message)s'
    datefmt = '%Y-%m-%d %H:M:%S'
    formatter = logging.Formatter(fmt, datefmt)
    print_fh = logging.StreamHandler()
    print_fh.setLevel(logging.DEBUG)
    print_fh.setFormatter(formatter)

    log_fh = logging.FileHandler(log_file, encoding="utf-8")
    log_fh.setLevel(logging.DEBUG)
    log_fh.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(print_fh)
    root_logger.addHandler(log_fh)


def web_loader(url, browser=None):
    # os.environ['PATH'] += f';{firefox_path}'
    # logger.info(os.environ['PATH'])
    # binary = FirefoxBinary(os.path.join(firefox_path, 'firefox.exe'))
    # browser = webdriver.Firefox(firefox_binary=binary)
    if browser is None:
        closer_browser = True
        firefox_profile = webdriver.FirefoxProfile()
        # firefox_profile.set_preference("general.useragent.override", "whatever you want")
        firefox_options = webdriver.FirefoxOptions()
        firefox_options.add_argument("--headless")
        # firefox_options.add_argument("user-agent={user_agent}")
        # fireFoxOptions.add_argument("--start-maximized")
        browser = webdriver.Firefox(firefox_profile=firefox_profile, options=firefox_options)
        time.sleep(1)
    else:
        closer_browser = False
    browser.get(url)
    time.sleep(1)
    browser.execute_script("window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});")
    time.sleep(1)
    # return str(browser.page_source)[10:20]
    page_source = browser.page_source
    if closer_browser:
        browser.close()
    return page_source


def get_pacific_time():
    tz = pytz.timezone('America/Los_Angeles')
    pacific_time = datetime.now(tz)
    return pacific_time


def in_between(now, start, end):
    if start <= end:
        return start <= now < end
    else: # over midnight e.g., 23:30-04:15
        return start <= now or now < end


def is_night(night_start=1, night_end=7):
    pacific_time = get_pacific_time()
    return in_between(pacific_time.time(),
        datetime_time(night_start), datetime_time(night_end))


def shuffle_dict(d):
    l = list(d.items())
    random.shuffle(l)
    d = dict(l)
    return d


def scrap_craigslist(url, post_handle, existing_posts,
                     browser=None, debug_filename=DEBUG_FILENAME):
    page_source = '[NOTHING YET]'
    try:
        page_source = web_loader(url, browser=browser)
    except Exception as exception:
        logger.info(str(exception))
        with open(debug_filename, 'w', encoding='utf-8') as fp:
            print(str(page_source), file=fp)
        return []
    # logger.info(page_source)
    # with open('craigslist.txt', encoding="utf-8") as fp:
    #     page_source = fp.read()
    results = re.findall(POST_PATTERN, page_source)
    # with open('debug.html', 'w') as fp:
    #     print(make_html_body(results[0]), file=fp)
    if results:
        new_results = []
        writing_post_ids = []
        for result in results:
            post_id = result[patternName.TITLE] + '|' + result[patternName.POST_LINK]
            if post_id not in existing_posts:
                new_results.append(result)
                writing_post_ids.append(post_id)
        if new_results:
            existing_posts.update(writing_post_ids)
            logger.info(f'having {len(new_results)} new results.')
            print('\n'.join(writing_post_ids), file=post_handle)
        else:
            logger.info('nothing new')
        return new_results
    else:
        logger.info(f'No result is found. Please check {debug_filename}'
              'for page_source')
        with open(debug_filename, 'w', encoding="utf-8") as debug_fn:
            print(page_source, file=debug_fn)
        return []


def nightly_idle_and_flush(existing_post_filename, post_handle, existing_posts):
    pacific_time = get_pacific_time()
    logger.info(f'Is night now: {pacific_time}. Resetting existing posts.')
    if existing_posts:
        existing_posts.clear()
        post_handle.close()
        post_handle = open(existing_post_filename, 'w', encoding="utf-8")
    return post_handle


def get_url(url_template, setting_dict=None):
    if setting_dict is not None:
        fill_str = '?' + '&'.join(f'{k}={v}' for k, v in setting_dict.items())
    else:
        fill_str = ''
    return url_template.format(fill_str)

def make_html_body(post):
    html_body = (
        "<a href=\"" + post[patternName.POST_LINK] + "\">" + post[patternName.TITLE] + "</a>"
        + "<br>" + post[patternName.LOCATION] + " in " + post[patternName.DISTANCE] + "mi at " + post[patternName.TIME] + "<br>"
    )
    if post[patternName.IMG_LINK]:
        html_body += "<a href=\"" + post[patternName.POST_LINK] + "\">" + "<img src=\"" + post[patternName.IMG_LINK] + "\">" + "</a>" + "<br>"
    return html_body


def _send_email(html_body, title, email_address, is_bug=True):
    email_cmd = f'echo "{html_body}" | mail -s "{title}\nContent-Type: text/html" {email_address}'
    if is_bug:
        logger.info(f'Sending bug report to {email_address}.')
    else:
        logger.info(f'Sending email to {email_address}.')
    error_code = os.system(email_cmd)
    if error_code:
        logger.info(email_cmd)


def send_email(posts, emails, **kwargs):
    if not posts:
        return
    title = 'Multiple New Posts Found' if len(posts) > 1 else 'New Post Found'
    html_body = '\\n'.join(make_html_body(post) for post in posts)
    for email_address in emails:
        _send_email(html_body, title, email_address)


def send_notification(posts, toast=None, duration=20, **kwargs):
    if not posts:
        return
    title = 'Multiple New Posts Found' if len(posts) > 1 else 'New Post Found'
    body = posts[0][patternName.TITLE] + ': (' + posts[0][patternName.LOCATION] + ' in ' + posts[0][patternName.DISTANCE] + 'mi at ' + posts[0][patternName.TIME] + ')'
    toast.show_toast(
        title, body,
        duration=duration,
        threaded=True,
    )


def notify(**kwargs):
    if platform == 'win32':
        send_notification(**kwargs)
    else:
        send_email(**kwargs)


def get_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--setting-file', default='settings.yaml', type=str,
        help='setting file path'
    )
    parser.add_argument(
        '--log-file', default='execution.log', type=str,
        help='log file path'
    )
    parser.add_argument(
        '--sleep-time', default=SLEEPING_TIME, type=int,
        help='sleeping time between searches'
    )
    parser.add_argument(
        '--existing-post-file', default=EXISTING_POST_FILENAME, type=str,
        help='existing posts file'
    )
    parser.add_argument(
        '--debug-file', default=DEBUG_FILENAME, type=str,
        help='debug file'
    )
    parser.add_argument(
        '--night-time', default=(0, 7), type=int, nargs=2,
        help='night start/end time'
    )
    parser.add_argument(
        '--email-addresses', default=(DEFAULT_EMAIL, ), nargs='+',
        help='Email addresses to send notification to.'
    )
    args = parser.parse_args(args=argv)
    setup_logging(args.log_file)
    return args


def _main(argv=None):
    args = get_args(argv=argv)

    url_template = 'https://sfbay.craigslist.org/search/sby/zip{}#search=1~gallery~0~0'
    url = 'https://sfbay.craigslist.org/search/sby/zip?postal=94538&postedToday=1&search_distance=25&sort=date#search=1~gallery~0~0'

    if os.path.exists(args.setting_file):
        with open(args.setting_file) as fp:
            setting_dict = yaml.safe_load(fp)
    else:
        setting_dict = None

    notify_kwargs = {}
    if platform == "linux" or platform == "linux2":
        # linux
        notify_kwargs['emails'] = args.email_addresses
    elif platform == "darwin":
        raise OSError(f'OS {platform} not supported.')
    elif platform == "win32":
        notify_kwargs['toast'] = ToastNotifier()

    """Return a friendly HTTP greeting."""
    existing_post_filename = args.existing_post_file
    default_sleep_time = args.sleep_time
    sleep_time = default_sleep_time
    nightly_flush_done = False

    if os.path.exists(existing_post_filename):
        with open(existing_post_filename, encoding="utf-8") as fp:
            existing_posts = set(ln.strip() for ln in fp.readlines())
        post_handle = open(existing_post_filename, 'a', encoding="utf-8")
    else:
        existing_posts = set()
        post_handle = open(existing_post_filename, 'w', encoding="utf-8")
    exception = None

    try:
        browser = webdriver.Firefox()
        time.sleep(1)
    except WebDriverException:
        browser = None

    while True:
        if is_night(*args.night_time):
            post_handle = nightly_idle_and_flush(
                existing_post_filename, post_handle, existing_posts)
            # once we detect it's night time, we sleep longer
            sleep_time = NIGHT_SLEEPING_TIME
        else:
            if setting_dict is not None:
                setting_dict = shuffle_dict(setting_dict)
            url = get_url(url_template, setting_dict=setting_dict)
            logger.info(f'Searching URL: {url}')
            # a new day, reset sleep_time to default
            sleep_time = default_sleep_time
            new_posts = scrap_craigslist(url, post_handle, existing_posts, browser=browser)
            notify(posts=new_posts, **notify_kwargs)
        logger.info(f'Processing done. Sleep for {sleep_time} seconds.')
        time.sleep(sleep_time)
    post_handle.close()
    if browser is not None:
        browser.close()

def main(argv=None):
    try:
        _main(argv=None)
    except Exception as e:
        exception_txt = str(e)
        _send_email(exception_txt, 'BUG reported', DEFAULT_EMAIL, is_bug=True)


if __name__ == '__main__':
    main()
