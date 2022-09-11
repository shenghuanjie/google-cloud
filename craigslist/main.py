import argparse
from email.mime.text import MIMEText
import logging
from logging.handlers import TimedRotatingFileHandler
import multiprocessing
import os
import re
import random
import subprocess
import signal
import smtplib
from sys import platform
import time
from urllib.parse import quote

from datetime import datetime
from datetime import time as datetime_time
import pytz
from enum import Enum
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
import yaml
if platform == "win32":
    from win10toast import ToastNotifier


logger = logging.getLogger(__name__)


EXISTING_POST_FILENAME = 'existing_posts.txt'
NEW_POST_FILENAME = 'new_posts.txt'
SLEEPING_TIME = 60
DEBUG_FILENAME = 'debug.html'
DEFAULT_EMAIL = 'drhsheng@gmail.com'
NIGHT_SLEEPING_TIME = 3600
MAX_NUM_EMAIL_PER_DAY = 200
EMAIL_COUNTER_KEY = 'EMAIL_COUNTER'
GECKODRIVER_LOG = 'geckodriver.log'
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


def timeout(seconds):
    if seconds < 0:
        raise ValueError('"seconds" must be non-negative. {seconds} is given.')

    def wrapped_func(func):

        err_msg = f'{func.__name__} timeout.'

        def handler(signum, frame):
            raise TimeoutError(err_msg)

        def new_func(*args, **kwargs):
            if seconds <= 0:
                raise TimeoutError(err_msg)
            old = signal.signal(signal.SIGALRM, handler)
            old_seconds_left = signal.alarm(seconds)
            # continue with time left
            if 0 < old_seconds_left < seconds:
                signal.alarm(old_seconds_left)
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
            finally:
                if old_seconds_left > 0:
                    old_seconds_left -= time.time() - start_time
                    old_seconds_left = max(round(old_seconds_left), 0)
                signal.signal(signal.SIGALRM, old)
                signal.alarm(old_seconds_left)
            return result
        new_func.__name__ = func.__name__
        return new_func
    return wrapped_func


def setup_logging(log_file, debug=False):
    fmt = '%(asctime)s %(levelname)-9s: [%(name)s:%(lineno)s]: %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S(%Z)'
    formatter = logging.Formatter(fmt, datefmt)
    print_fh = logging.StreamHandler()
    print_fh.setLevel(logging.DEBUG)
    print_fh.setFormatter(formatter)

    log_fh = TimedRotatingFileHandler(log_file, when='midnight', backupCount=1, encoding="utf-8")
    if debug:
        log_fh.setLevel(logging.DEBUG)
    else:
        log_fh.setLevel(logging.INFO)
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
        # firefox_profile = webdriver.FirefoxProfile()
        # firefox_profile.set_preference("general.useragent.override", "whatever you want")
        firefox_options = webdriver.FirefoxOptions()
        firefox_options.add_argument("--headless")
        # firefox_options.add_argument("start-maximized")
        # firefox_options.add_argument("disable-infobars")
        # firefox_options.add_argument("--disable-extensions")
        firefox_options.add_argument('--no-sandbox')
        # firefox_options.add_argument('--disable-application-cache')
        firefox_options.add_argument('--disable-gpu')
        # firefox_options.add_argument("--disable-dev-shm-usage")
        # firefox_options.add_argument("user-agent={user_agent}")
        browser = webdriver.Firefox(options=firefox_options)
        # browser = webdriver.Firefox(firefox_profile=firefox_profile, options=firefox_options)
        time.sleep(2)
    else:
        closer_browser = False
    browser.get(url)
    refresh_wait = random.randint(3, 6)
    time.sleep(refresh_wait)
    num_chunks = random.randint(2, 4)
    # window.scrollTo({top: Math.round(document.body.scrollHeight * 2 / 3), behavior: 'smooth'});
    for ichunk in range(1, num_chunks + 1):
        browser.execute_script("window.scrollTo({top: Math.round(document.body.scrollHeight * " + f"{ichunk} / {num_chunks}" + "), behavior: 'smooth'});")
        refresh_wait = random.randint(5 - num_chunks, 7 - num_chunks)
        time.sleep(refresh_wait)
    # return str(browser.page_source)[10:20]
    page_source = browser.page_source
    if closer_browser:
        browser.quit()
        del browser
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
    return in_between(pacific_time.time(), datetime_time(night_start), datetime_time(night_end))


def shuffle_dict(d):
    l = list(d.items())
    random.shuffle(l)
    d = dict(l)
    return d


def shuffle_list(l):
    random.shuffle(l)
    return l


def get_pipeline_result(cmd):
    ps = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = ps.communicate()
    return stdout.decode(), (stderr.decode() if stderr is not None else stderr)


def load_update_existing_posts(existing_post_filename):
    if os.path.exists(existing_post_filename):
        with open(existing_post_filename, encoding="utf-8") as fp:
            existing_posts = set(ln.strip() for ln in fp.readlines())
        post_handle = open(existing_post_filename, 'a', encoding="utf-8")
    else:
        existing_posts = set()
        post_handle = open(existing_post_filename, 'w', encoding="utf-8")
    return post_handle, existing_posts


def scrap_craigslist(url, existing_post_filename, new_post_filename, skipping_dict=None,
                     browser=None, debug_filename=DEBUG_FILENAME,
                     debug=False):
    page_source = '[NOTHING YET]'
    try:
        page_source = web_loader(url, browser=browser)
        if debug:
            logger.info(page_source)
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
        if debug:
            logger.info('skipping_dict: ', skipping_dict)
        with open(new_post_filename, 'w', encoding="utf-8") as fp:
            print('\n'.join(result[patternName.TITLE] + '|' + result[patternName.POST_LINK]
                            for result in results), file=fp)

        stdout, stderr = get_pipeline_result(f'grep -F -x -v -f {existing_post_filename} {new_post_filename}')
        if stderr is not None:
            raise ValueError(str(stderr))
        existing_posts = set(stdout.split('\n'))
        for result in results:
            post_id = result[patternName.TITLE] + '|' + result[patternName.POST_LINK]
            if post_id not in existing_posts:
                skip_result = ''
                if skipping_dict:
                    for result_key, skip_values in skipping_dict.items():
                        if skip_result:
                            break
                        result_value = result[patternName[result_key]].lower()
                        for skip_value in skip_values:
                            if result_value.find(skip_value.lower()) != -1:
                                skip_result = f'{result_key}: {skip_value}'
                                break
                if not skip_result:
                    new_results.append(result)
                    writing_post_ids.append(post_id)
                else:
                    if debug:
                        logger.info(f'{post_id} skipped due to skip_value found: {skip_result}')
        if new_results:
            existing_posts.update(writing_post_ids)
            logger.info(f'having {len(new_results)} new results.')
            with open(existing_post_filename, 'a', encoding="utf-8") as fp:
                print('\n'.join(writing_post_ids), file=fp)
        else:
            logger.info('nothing new')
        return new_results
    else:
        logger.info(f'No result is found. Please check {debug_filename}'
              'for page_source')
        with open(debug_filename, 'w', encoding="utf-8") as debug_fn:
            print(page_source, file=debug_fn)
        return []


def nightly_idle_and_flush(existing_post_filename):
    pacific_time = get_pacific_time()
    logger.info(f'It is night now: {pacific_time}. Resetting existing posts.')
    os.system(f'rm -f {existing_post_filename}')
    os.system(f'touch {existing_post_filename}')


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


def _send_email(html_body, title, emails, is_bug=False):
    if not isinstance(emails, str):
        emails = ' '.join(emails)
    email_cmd = f'echo "{html_body}" | mail -s "{title}\nContent-Type: text/html" -aFrom:{DEFAULT_EMAIL} {emails}'
    if is_bug:
        logger.info(f'Sending bug report to {emails}.')
    else:
        logger.info(f'Sending email to {emails}.')
    error_code = os.system(email_cmd)
    if error_code:
        logger.info(email_cmd)
    else:
        # update email counter
        os.environ[EMAIL_COUNTER_KEY] = str(int(os.environ[EMAIL_COUNTER_KEY]) + 1)


def send_email(posts, emails, email_quota=0, **kwargs):
    if not posts:
        return
    email_counter = int(os.environ[EMAIL_COUNTER_KEY])
    if email_quota and email_counter >= email_quota:
        logger.info('max quota reached.  Skipping sending email.')
        return
    if email_quota and email_counter >= email_quota - 2:
        # we need to leave 2 emails here, one for this notification and
        # one for the posts update
        _send_email(f'{email_counter} emails has been sent today and the limit is {MAX_NUM_EMAIL_PER_DAY}.',
                    'Email Quota Reached in Free Stuff Found on Craigslist',
                    DEFAULT_EMAIL, is_bug=True)
    title = 'Multiple Free Stuff Found on Craigslist' if len(posts) > 1 else 'New Free Stuff Found on Craigslist'
    html_body = '\\n'.join(make_html_body(post) for post in posts)
    _send_email(html_body, title, emails)


def send_notification(posts, toast=None, duration=20, **kwargs):
    if not posts:
        return
    title = 'Multiple Free Stuff Found on Craigslist' if len(posts) > 1 else 'New Free Stuff Found on Craigslist'
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
        '--new-post-file', default=NEW_POST_FILENAME, type=str,
        help='temporary new posts file'
    )
    parser.add_argument(
        '--debug-file', default=DEBUG_FILENAME, type=str,
        help='debug file'
    )
    parser.add_argument(
        '--debug', action='store_true',
        help='debug mode'
    )
    parser.add_argument(
        '--night-time', default=(0, 7), type=int, nargs=2,
        help='night start/end time'
    )
    parser.add_argument(
        '--email-addresses', default=(DEFAULT_EMAIL, ), nargs='+',
        help='Email addresses to send notification to.'
    )
    parser.add_argument(
        '--email-quota', default=MAX_NUM_EMAIL_PER_DAY, type=int,
        help='Naximum number of emails allowed to send per day.'
             '0 means unlimited.'
    )
    args = parser.parse_args(args=argv)
    setup_logging(args.log_file, args.debug)
    return args


def _scrapper(url_template, setting_filename, existing_post_filename, new_post_filename, browser, sleep_time, default_sleep_time, debug):
    if os.path.exists(setting_filename):
        with open(setting_filename) as fp:
            setting_dict = yaml.safe_load(fp)
        if 'query' in setting_dict:
            setting_dict['query'] = '|'.join(shuffle_list(setting_dict['query'].split('|')))
        skipping_dict = setting_dict.get('skipping', {})
        setting_dict = {k: quote(f'{v}') for k, v in setting_dict.items() if not isinstance(v, dict)}
    if setting_dict is not None:
        setting_dict = shuffle_dict(setting_dict)
    url = get_url(url_template, setting_dict=setting_dict)
    if debug:
        logger.info(f'Searching URL: {url}')
    # a new day, reset sleep_time to default
    try:
        new_posts = scrap_craigslist(
            url, existing_post_filename, new_post_filename, skipping_dict=skipping_dict,
            browser=browser, debug=debug)
    except Exception as e:
        exception_txt = f'error in scrap_craigslist: {e}'
        _send_email(exception_txt, 'BUG Reported from Free Stuff Found on Craigslist',
                    DEFAULT_EMAIL, is_bug=True)
    # no notification the first search per day
    if sleep_time == default_sleep_time:
        notify(posts=new_posts, **notify_kwargs)


def scrapper(*args):
    try:
        _scrapper(*args)
    except Exception as e:
        exception_txt = f'error in scrapper: {e}'
        logger.error(exception_txt)
        _send_email(exception_txt, 'BUG Reported from Free Stuff Found on Craigslist',
                    DEFAULT_EMAIL, is_bug=True)


def _main(argv=None):
    args = get_args(argv=argv)

    url_template = 'https://sfbay.craigslist.org/search/sby/zip{}#search=1~gallery~0~0'
    url = 'https://sfbay.craigslist.org/search/sby/zip?postal=94538&postedToday=1&search_distance=25&sort=date#search=1~gallery~0~0'

    if os.path.exists(args.setting_file):
        with open(args.setting_file) as fp:
            setting_dict = yaml.safe_load(fp)
        if 'query' in setting_dict:
            setting_dict['query'] = '|'.join(shuffle_list(setting_dict['query'].split('|')))
        skipping_dict = setting_dict.get('skipping', {})
        setting_dict = {k: quote(f'{v}') for k, v in setting_dict.items() if not isinstance(v, dict)}
    else:
        setting_dict = None

    notify_kwargs = {}
    if platform == "linux" or platform == "linux2":
        # linux
        notify_kwargs['emails'] = args.email_addresses
        notify_kwargs['email_quota'] = args.email_quota
    elif platform == "darwin":
        raise OSError(f'OS {platform} not supported.')
    elif platform == "win32":
        notify_kwargs['toast'] = ToastNotifier()

    """Return a friendly HTTP greeting."""
    existing_post_filename = args.existing_post_file
    new_post_filename = args.new_post_file
    setting_filename = args.setting_file
    default_sleep_time = args.sleep_time
    debug = args.debug
    sleep_time = default_sleep_time
    nightly_flush_done = False

    exception = None

    try:
        browser = webdriver.Firefox()
        refresh_wait = random.randint(3, 6)
        time.sleep(refresh_wait)
    except WebDriverException:
        browser = None
    finally:
        browser = None

    if EMAIL_COUNTER_KEY not in os.environ:
        os.environ[EMAIL_COUNTER_KEY] = str(0)

    if not os.path.exists(existing_post_filename):
        os.system(f'touch {existing_post_filename}')

    while True:
        if is_night(*args.night_time):
            nightly_idle_and_flush(existing_post_filename)
            # once we detect it's night time, we sleep longer
            sleep_time = NIGHT_SLEEPING_TIME
            os.environ[EMAIL_COUNTER_KEY] = str(0)
            if os.path.isfile(GECKODRIVER_LOG):
                os.remove(GECKODRIVER_LOG)
        else:
            scrapper_args = (url_template, setting_filename, existing_post_filename, new_post_filename, sleep_time, default_sleep_time, browser, debug)
            if browser is None:
                scrapper(*scrapper_args)
            else:
                proc = multiprocessing.Process(target=scrapper, args=scrapper_args)
                proc.start()
                proc.join()
            sleep_time = default_sleep_time
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
        logger.error(exception_txt)
        _send_email(exception_txt, 'BUG Reported from Free Stuff Found on Craigslist',
                    DEFAULT_EMAIL, is_bug=True)


if __name__ == '__main__':
    main()
