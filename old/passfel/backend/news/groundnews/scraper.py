"""
Ground.news web scraper implementation.
"""

import re
from typing import List, Optional
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By

from .driver import (
    create_headless_driver,
    dismiss_overlays,
    wait_for_page_load,
    wait_for_stories,
    wait_for_story_detail,
    polite_sleep,
)
from .models import (
    StorySummary,
    StoryDetail,
    BiasDistribution,
    Article,
)


def scrape_homepage(base_url="https://ground.news", max_stories=5) -> List[StorySummary]:
    """
    Scrape the Ground.news homepage for top stories.
    
    Args:
        base_url: Base URL for Ground.news
        max_stories: Maximum number of stories to collect
    
    Returns:
        List of StorySummary objects
    """
    driver = create_headless_driver()
    stories = []
    
    try:
        driver.get(base_url)
        wait_for_page_load(driver)
        dismiss_overlays(driver)
        
        if not wait_for_stories(driver, min_count=min(5, max_stories)):
            print(f"Warning: Could not find {max_stories} stories on homepage")
        
        story_links = driver.find_elements(By.CSS_SELECTOR, "a[href^='/article/']")
        
        seen_urls = set()
        for link in story_links:
            if len(stories) >= max_stories:
                break
            
            href = link.get_attribute("href")
            if href and href not in seen_urls:
                seen_urls.add(href)
                
                story_id_match = re.search(r'/article/([^/]+)', href)
                story_id = story_id_match.group(1) if story_id_match else href
                
                title = link.text.strip() or "Unknown Title"
                
                stories.append(StorySummary(
                    story_id=story_id,
                    title=title,
                    url=href if href.startswith('http') else base_url + href,
                ))
        
        return stories
    
    finally:
        driver.quit()


def scrape_story_detail(url: str) -> Optional[StoryDetail]:
    """
    Scrape detailed information for a specific story.
    
    Args:
        url: Full URL to the story detail page
    
    Returns:
        StoryDetail object or None if scraping failed
    """
    driver = create_headless_driver()
    
    try:
        driver.get(url)
        wait_for_page_load(driver)
        dismiss_overlays(driver)
        
        if not wait_for_story_detail(driver):
            print(f"Warning: Story detail page did not load properly: {url}")
            return None
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        story_id_match = re.search(r'/article/([^/]+)', url)
        story_id = story_id_match.group(1) if story_id_match else url
        
        title_elem = soup.find('h1')
        title = title_elem.get_text(strip=True) if title_elem else "Unknown Title"
        
        summary_elem = soup.find('h2')
        if not summary_elem:
            summary_elem = soup.find('p')
        summary = summary_elem.get_text(strip=True) if summary_elem else ""
        
        total_sources = 0
        articles_header = soup.find(string=re.compile(r'\d+\s+Articles?'))
        if articles_header:
            match = re.search(r'(\d+)\s+Articles?', articles_header)
            if match:
                total_sources = int(match.group(1))
        
        bias_dist = _extract_bias_distribution(soup, driver)
        
        articles = _extract_articles(soup)
        
        topics = _extract_topics(soup)
        
        return StoryDetail(
            story_id=story_id,
            title=title,
            summary=summary,
            url=url,
            total_sources=total_sources,
            bias_distribution=bias_dist,
            articles=articles,
            topics=topics,
        )
    
    finally:
        driver.quit()


def _extract_bias_distribution(soup: BeautifulSoup, driver) -> BiasDistribution:
    """
    Extract political bias distribution from the page.
    
    Args:
        soup: BeautifulSoup object of the page
        driver: Selenium WebDriver instance
    
    Returns:
        BiasDistribution object
    """
    left = 0
    center = 0
    right = 0
    left_percent = None
    center_percent = None
    right_percent = None
    
    try:
        bias_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Left') or contains(text(), 'Center') or contains(text(), 'Right')]")
        
        for elem in bias_elements:
            text = elem.text.strip()
            
            left_match = re.search(r'Left\s*(\d+)', text, re.IGNORECASE)
            if left_match:
                left = max(left, int(left_match.group(1)))
            
            center_match = re.search(r'Center\s*(\d+)', text, re.IGNORECASE)
            if center_match:
                center = max(center, int(center_match.group(1)))
            
            right_match = re.search(r'Right\s*(\d+)', text, re.IGNORECASE)
            if right_match:
                right = max(right, int(right_match.group(1)))
    except Exception as e:
        print(f"Warning: Could not extract bias counts from buttons: {e}")
    
    page_text = soup.get_text()
    percent_match = re.search(
        r'(?:Left|L)\s*(\d+)%.*?(?:Center|C)\s*(\d+)%.*?(?:Right|R)\s*(\d+)%',
        page_text,
        re.IGNORECASE
    )
    if percent_match:
        left_percent = int(percent_match.group(1))
        center_percent = int(percent_match.group(2))
        right_percent = int(percent_match.group(3))
    
    return BiasDistribution(
        left=left,
        center=center,
        right=right,
        left_percent=left_percent,
        center_percent=center_percent,
        right_percent=right_percent,
    )


def _extract_articles(soup: BeautifulSoup) -> List[Article]:
    """
    Extract individual article listings from the page.
    
    Args:
        soup: BeautifulSoup object of the page
    
    Returns:
        List of Article objects
    """
    articles = []
    
    outlet_links = soup.find_all('a', href=re.compile(r'/interest/'))
    
    for outlet_link in outlet_links[:50]:  # Limit to first 50 to avoid over-scraping
        try:
            source = outlet_link.get_text(strip=True)
            if not source:
                continue
            
            bias = "Unknown"
            parent = outlet_link.find_parent()
            if parent:
                bias_link = parent.find('a', href=re.compile(r'#bias-ratings'))
                if bias_link:
                    bias = bias_link.get_text(strip=True)
            
            headline = "Unknown Headline"
            article_url = ""
            if parent:
                external_link = parent.find('a', href=re.compile(r'^https?://'))
                if external_link:
                    headline = external_link.get_text(strip=True)
                    article_url = external_link.get('href', '')
            
            published = None
            if parent:
                time_elem = parent.find('time')
                if time_elem:
                    published = time_elem.get('datetime') or time_elem.get_text(strip=True)
            
            location = None
            if parent:
                parent_text = parent.get_text()
                location_match = re.search(r'·\s*([^·]+(?:,\s*[^·]+)?)\s*$', parent_text)
                if location_match:
                    location = location_match.group(1).strip()
            
            if source and headline != "Unknown Headline":
                articles.append(Article(
                    source=source,
                    bias=bias,
                    headline=headline,
                    url=article_url,
                    published=published,
                    location=location,
                ))
        
        except Exception as e:
            print(f"Warning: Could not extract article info: {e}")
            continue
    
    return articles


def _extract_topics(soup: BeautifulSoup) -> List[str]:
    """
    Extract topic tags from the page.
    
    Args:
        soup: BeautifulSoup object of the page
    
    Returns:
        List of topic strings
    """
    topics = []
    
    
    topic_links = soup.find_all('a', href=re.compile(r'/topic/'))
    for link in topic_links:
        topic = link.get_text(strip=True)
        if topic and topic not in topics:
            topics.append(topic)
    
    return topics
