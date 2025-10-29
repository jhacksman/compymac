"""
Selenium WebDriver utilities for Ground.news scraper.
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def create_headless_driver():
    """
    Create a headless Chrome WebDriver with anti-detection settings.
    
    Returns:
        webdriver.Chrome: Configured Chrome WebDriver instance
    """
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    driver = webdriver.Chrome(options=options)
    
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver


def dismiss_overlays(driver, timeout=5):
    """
    Dismiss any subscription modals or cookie overlays on Ground.news.
    
    Args:
        driver: Selenium WebDriver instance
        timeout: Maximum time to wait for overlays (seconds)
    """
    try:
        wait = WebDriverWait(driver, timeout)
        proceed_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Ground News homepage')]"))
        )
        proceed_button.click()
        time.sleep(1)
    except (TimeoutException, NoSuchElementException):
        pass
    
    try:
        close_button = driver.find_element(By.XPATH, "//button[contains(@aria-label, 'Close') or contains(text(), 'Close')]")
        close_button.click()
        time.sleep(1)
    except NoSuchElementException:
        pass


def wait_for_page_load(driver, timeout=10):
    """
    Wait for page to fully load.
    
    Args:
        driver: Selenium WebDriver instance
        timeout: Maximum time to wait (seconds)
    """
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def wait_for_stories(driver, min_count=5, timeout=10):
    """
    Wait for story cards to load on homepage.
    
    Args:
        driver: Selenium WebDriver instance
        min_count: Minimum number of story links to wait for
        timeout: Maximum time to wait (seconds)
    
    Returns:
        bool: True if stories loaded, False otherwise
    """
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "a[href^='/article/']")) >= min_count
        )
        return True
    except TimeoutException:
        return False


def wait_for_story_detail(driver, timeout=15):
    """
    Wait for story detail page to load.
    
    Args:
        driver: Selenium WebDriver instance
        timeout: Maximum time to wait (seconds)
    
    Returns:
        bool: True if story detail loaded, False otherwise
    """
    try:
        wait = WebDriverWait(driver, timeout)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        time.sleep(2)
        return True
    except TimeoutException:
        return False


def polite_sleep(min_seconds=2.0, max_seconds=3.5):
    """
    Sleep for a random duration to be polite to the server.
    
    Args:
        min_seconds: Minimum sleep duration
        max_seconds: Maximum sleep duration
    """
    import random
    duration = random.uniform(min_seconds, max_seconds)
    time.sleep(duration)
