import argparse
import ssl
import sys
from bs4 import BeautifulSoup
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import os
import urllib.parse
from pathlib import Path
from loguru import logger
import random

# Cấu hình logging
logger.remove()
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

parser = argparse.ArgumentParser(
    description="Scrape full language courses from JapanesePod101."
)
parser.add_argument("-u", "--username", help="Username (email)")
parser.add_argument("-p", "--password", help="Password for the course")
parser.add_argument(
    "--clear",
    action="store_true",
    help="Clear existing course folders before downloading",
)
parser.add_argument(
    "--proxy",
    help="Proxy to use (e.g., http://user:pass@ip:port)",
)

args = parser.parse_args()
SOURCE_URL = "https://www.japanesepod101.com"

# Login and session initialization
USERNAME = args.username or input("Username (email): ")
PASSWORD = args.password or input("Password: ")
LOGIN_URL = f"{SOURCE_URL}/sign-in"

# List of user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
]

# Set up Selenium WebDriver
chrome_options = Options()
prefs = {
    "download.default_directory": os.path.abspath("downloads"),
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True,
    "plugins.always_open_pdf_externally": True,  # option no pdf viewer
}
chrome_options.add_experimental_option("prefs", prefs)
chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")

if args.proxy:
    chrome_options.add_argument(f"--proxy-server={args.proxy}")

driver = webdriver.Chrome(options=chrome_options)


def random_delay(min_seconds=1, max_seconds=5):
    time.sleep(random.uniform(min_seconds, max_seconds))


def simulate_human_scroll(driver):
    total_height = int(driver.execute_script("return document.body.scrollHeight"))
    scroll_positions = sorted(random.sample(range(1, total_height), random.randint(5, 10)))
    for position in scroll_positions:
        driver.execute_script(f"window.scrollTo(0, {position});")
        random_delay(0.1, 0.3)
    random_delay(0.5, 1.5)
    driver.execute_script("window.scrollTo(0, 0);")


def login():
    try:
        logger.info(f"Attempting to login to {SOURCE_URL}")
        driver.get(LOGIN_URL)
        random_delay(2, 4)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "amember_login"))
        )
        username_field = driver.find_element(By.NAME, "amember_login")
        password_field = driver.find_element(By.NAME, "amember_pass")

        username_field.send_keys(USERNAME)
        password_field.send_keys(PASSWORD)

        random_delay(1, 2)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        WebDriverWait(driver, 10).until(EC.url_contains("dashboard"))
        logger.success(f"Successfully logged in as {USERNAME}")
    except Exception as e:
        logger.error(f"Login Failed: {str(e)}")
        driver.quit()
        exit(1)

# open the error file if it exists, otherwise create a new one
# then continue to write the error log to the file
# one error is written per line
# file name: error_log.txt
def save_error(error_log):
    with open("error_log.txt", "a") as f:
        f.write(error_log + "\n")


def download_media(file_url, file_path):
    try:
        logger.info(f"Downloading media: {file_url}")
        extension = file_url.split(".")[-1]

        # Create an SSL context that ignores certificate verification
        context = ssl._create_unverified_context()
        response = urllib.request.urlopen(file_url, context=context)

        with open(file_path, "wb") as f:
            f.write(response.read())

        logger.info(f"Successfully download {extension}: {file_path}")
        random_delay(1, 3)
    except Exception as e:
        logger.error(f"Error downloading media {file_url}: {str(e)}")
        save_error(f"Error downloading media {file_url}: {str(e)}")


def download_file(driver, file_url, file_path):
    try:
        logger.info(f"Attempting to download: {file_url}")

        desired_file_name = os.path.basename(file_path)

        driver.get(file_url)
        random_delay(2, 4)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        random_delay(1, 3)

        download_dir = os.path.abspath("downloads")
        downloaded_files = [
            f
            for f in os.listdir(download_dir)
            if os.path.isfile(os.path.join(download_dir, f))
        ]

        if downloaded_files:
            latest_file = max(
                [os.path.join(download_dir, f) for f in downloaded_files],
                key=os.path.getctime,
            )

            new_file_path = os.path.join(download_dir, desired_file_name)
            os.rename(latest_file, new_file_path)

            Path(new_file_path).replace(file_path)

            logger.info(f"Successfully downloaded and renamed: {new_file_path}")
        else:
            logger.error(
                f"No file found in download directory after attempting to download {file_url} in {file_path}"
            )
            save_error(
                f"No file found in download directory after attempting to download {file_url} in {file_path}"
            )

    except Exception as e:
        logger.error(f"Error downloading {file_url}: {str(e)}")
        save_error(f"Error downloading {file_url}: {str(e)}")


def get_courses_from_category(category_url):
    driver.get(category_url)
    random_delay(2, 4)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "list"))
    )
    simulate_human_scroll(driver)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    course_list = soup.find("div", class_="list")
    if not course_list:
        logger.warning(f"No courses found in {category_url}")
        return []
    courses = []
    for course in course_list.find_all("a", class_="ll-collection-all"):
        course_url = course["href"]
        course_title = course.find("div", class_="title").text.strip()
        courses.append({"title": course_title, "url": SOURCE_URL + course_url})
    return courses


def get_lessons_from_course(course_url):
    logger.info(f"Fetching lessons from {course_url}")
    driver.get(course_url)
    random_delay(2, 4)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "main"))
    )
    simulate_human_scroll(driver)

    soup = BeautifulSoup(driver.page_source, "html.parser")
    lessons = []

    for lesson in soup.find_all("div", class_=lambda x: x and x.startswith("_row_")):
        lesson_data = {}

        position = lesson.find("div", class_=lambda x: x and x.startswith("_circle_"))
        if not position:
            logger.warning("No position found")
        lesson_data["position"] = position.text.strip() if position else ""

        title_elem = lesson.find(
            "h2",
            class_=lambda x: x
            and x.startswith("_lesson__title_")
            or x.startswith("_assignment__title_"),
        )
        type_elem = lesson.find(
            "div",
            class_=lambda x: x
            and x.startswith("_lesson__type_")
            or x.startswith("_assignment__type_"),
        )
        if title_elem:
            lesson_data["title"] = title_elem.text.strip()
        else:
            logger.warning("No title found")
            lesson_data["title"] = lesson_data.get("position", "Lesson") + " - Untitled"

        if type_elem:
            lesson_data["type"] = type_elem.text.strip()
        else:
            logger.warning("No type found")
            lesson_data["type"] = "Unknown"

        lesson_link = lesson.find("a", href=True)
        if lesson_link:
            lesson_data["url"] = SOURCE_URL + lesson_link["href"]

        if lesson_data:
            lessons.append(lesson_data)

    return lessons


def get_lesson_content(
    driver, lesson_url, category, course_title, lesson_title, lesson_position
):
    random_delay(2, 4)
    driver.get(lesson_url)

    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "[class$='-pathway-context']"))
    )
    simulate_human_scroll(driver)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    folder_path = os.path.join(
        category, course_title, f"{lesson_position}_{lesson_title}"
    )
    os.makedirs(folder_path, exist_ok=True)
    logger.info(f"Created folder: {folder_path}")

    content = {}

    logger.info("Downloading PDF content...")
    try:
        pdf_section = soup.find("div", id="pdfs")
        if not pdf_section:
            logger.warning("No PDF section found")

        if pdf_section:
            pdf_list = pdf_section.find_next("ul")
            if pdf_list:
                for item in pdf_list.find_all("li"):
                    link = item.find("a")
                    
                    # if text of link variable is include "checklist"
                    if link.text.strip().lower() == "checklist":
                        logger.warning(f"Skipping PDF: {link.text.strip()}")
                        continue
                    
                    if link and link.get("href"):
                        pdf_url = link["href"]
                        if not pdf_url.startswith("http"):
                            pdf_url = urllib.parse.urljoin(SOURCE_URL, pdf_url)
                        pdf_name = f"{lesson_title}_{link.text.strip()}.pdf"
                        pdf_path = os.path.join(folder_path, pdf_name)
                        download_file(driver, pdf_url, pdf_path)
                        content.setdefault("pdf", []).append(pdf_path)
                    random_delay(1, 3)
    except Exception as e:
        logger.error(
            f"Error downloading PDF content for lesson {lesson_title}: {str(e)}"
        )
        save_error(f"Error downloading PDF content for lesson {lesson_title}: {str(e)}")

    logger.info("Downloading audio/video content...")
    try:
        download_section = soup.find("div", id="download-center")
        if not download_section:
            logger.warning("No download section found")

        if download_section:
            download_list = download_section.find_next("ul")
            logger.info(
                f"Found download list: length {len(download_list)} in {lesson_title}"
            )
            if download_list:
                for item in download_list.find_all("li"):
                    link = item.find("a")
                    if link and link.get("href"):
                        file_url = link["href"]
                        file_type = file_url.split(".")[-1]
                        file_name = f"{lesson_title}_{link.text.strip()}.{file_type}"
                        file_path = os.path.join(folder_path, file_name)
                        download_media(file_url, file_path)
                        content.setdefault(file_type, []).append(file_path)
                        logger.info(f"Saved {file_type}: {file_path}")
                    random_delay(1, 3)
    except Exception as e:
        logger.error(
            f"Error downloading audio/video content for lesson {lesson_title}: {str(e)}"
        )
        save_error(
            f"Error downloading audio/video content for lesson {lesson_title}: {str(e)}"
        )

    dialogue = soup.find("div", class_="dialogue-content")
    if dialogue:
        dialogue_text = dialogue.get_text(strip=True)
        file_name = f"{lesson_title}_dialogue.txt"
        file_path = os.path.join(folder_path, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(dialogue_text)
        content["dialogue"] = file_path
        logger.info(f"Saved dialogue: {file_path}")

    logger.success(f"Successfully processed lesson: {lesson_title}")
    return content


def main():
    login()

    categories = [
        "absolute-beginner",
        "beginner",
        "intermediate",
        "upper-intermediate",
        "advanced",
        "bonus",
    ]

    all_data = {}

    for category in categories:
        category_url = f"{SOURCE_URL}/lesson-library/{category}"
        logger.info(f"Fetching courses from {category}...")
        courses = get_courses_from_category(category_url)
        all_data[category] = []

        for course in courses:
            logger.info(f"Processing course: {course['title']}")
            course_folder = os.path.join(category, course["title"])

            if os.path.exists(course_folder) and not args.clear:
                logger.info(
                    f"Course folder {course_folder} already exists. Skipping..."
                )
                continue

            if args.clear and os.path.exists(course_folder):
                import shutil

                shutil.rmtree(course_folder)
                logger.info(f"Cleared existing course folder: {course_folder}")

            lessons = get_lessons_from_course(course["url"])
            course_data = {
                "title": course["title"],
                "url": course["url"],
                "lessons": [],
            }

            for lesson in lessons:
                try:
                    logger.info(f"Processing lesson: {lesson['title']}")
                    if lesson["type"].lower() in ["multiple-choice", "hand-graded"]:
                        logger.warning(f"Skipping lesson: {lesson['title']} because it is a {lesson['type']}")
                        continue
                    lesson_content = get_lesson_content(
                        driver,
                        lesson["url"],
                        category,
                        course["title"],
                        lesson["title"],
                        lesson["position"],
                    )
                    lesson.update(lesson_content)
                    course_data["lessons"].append(lesson)
                    time.sleep(random.uniform(2, 4))
                except Exception as e:
                    logger.error(
                        f"Error in main loop for lesson {lesson['title']}: {str(e)}"
                    )
                    save_error(
                        f"Error in main loop for lesson {lesson['title']}: {str(e)}"
                    )

            all_data[category].append(course_data)

        logger.success(f"Completed processing {len(courses)} courses in {category}")

    with open("japanese_courses_data.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    logger.success("All data has been saved to japanese_courses_data.json")

    driver.quit()


if __name__ == "__main__":
    main()
