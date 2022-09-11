from selenium import webdriver


url = 'https://sfbay.craigslist.org/search/sby/zip?postedToday=1&query=%20supply%20%7C%20everything%7C%20good%20%7C%20grass%20%7C%20new%20%7C%20garden%20%7C%20hula%20%7C%20excellent%20%7C%20cooler%20%7C%20paint%20%7C%20electronics%20%7C%20great%20%7C%20working%20%7C%20tools%20%7Cgravel%20&sort=date&postal=94538&search_distance=25#search=1~gallery~0~0'

ichunk = 2
num_chunks = 3

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
browser.get(url)
browser.execute_script("window.scrollTo({top: Math.round(document.body.scrollHeight * " + f"{ichunk} / {num_chunks}" + "), behavior: 'smooth'});")
page_source = browser.page_source
