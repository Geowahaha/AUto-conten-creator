import requests
import json
from datetime import datetime
from utils.logger import setup_logger

logger = setup_logger("trend_scout")

class TrendScout:
    def __init__(self, config):
        self.config = config.get("trends", {})
        self.sources = self.config.get("sources", ["reddit", "google_trends", "news"])

    def discover(self):
        all_topics = []
        if "reddit" in self.sources:
            all_topics.extend(self._scout_reddit())
        if "google_trends" in self.sources:
            all_topics.extend(self._scout_google_trends())
        if "news" in self.sources:
            all_topics.extend(self._scout_news())
        topics = self._rank_and_deduplicate(all_topics)
        logger.info(f"Discovered {len(topics)} unique trending topics")
        return topics

    def _scout_reddit(self):
        topics = []
        reddit_config = self.config.get("reddit", {})
        subreddits = reddit_config.get("subreddits", ["technology", "science", "worldnews"])
        headers = {"User-Agent": reddit_config.get("user_agent", "AutoContentCreator/1.0")}
        for sub in subreddits:
            try:
                url = f"https://www.reddit.com/r/{sub}/hot.json?limit=10"
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    for post in data.get("data", {}).get("children", []):
                        p = post.get("data", {})
                        if not p.get("stickied") and p.get("score", 0) > 100:
                            topics.append({
                                "title": p.get("title", ""),
                                "source": "reddit",
                                "subreddit": sub,
                                "score": min(p.get("score", 0) / 10000, 1.0),
                                "url": f"https://reddit.com{p.get("permalink", "")}",
                                "category": sub,
                            })
                logger.info(f"Reddit r/{sub}: found {len([t for t in topics if t.get("subreddit") == sub])} topics")
            except Exception as e:
                logger.warning(f"Reddit r/{sub} failed: {e}")
        return topics

    def _scout_google_trends(self):
        topics = []
        try:
            geo = self.config.get("google_trends", {}).get("geo", "US")
            url = f"https://trends.google.com/trending/rss?geo={geo}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(resp.text)
                for item in root.findall(".//item")[:20]:
                    title = item.find("title")
                    if title is not None and title.text:
                        topics.append({
                            "title": title.text.strip(),
                            "source": "google_trends",
                            "score": 0.8,
                            "category": "trending",
                            "geo": geo,
                        })
                logger.info(f"Google Trends: found {len(topics)} topics")
        except Exception as e:
            logger.warning(f"Google Trends failed: {e}")
        return topics

    def _scout_news(self):
        topics = []
        try:
            url = "https://hacker-news.firebaseio.com/v0/topstories.json"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                story_ids = resp.json()[:15]
                for sid in story_ids:
                    try:
                        story_resp = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5)
                        if story_resp.status_code == 200:
                            story = story_resp.json()
                            if story and story.get("title"):
                                topics.append({
                                    "title": story["title"],
                                    "source": "hackernews",
                                    "score": min(story.get("score", 0) / 500, 1.0),
                                    "url": story.get("url", ""),
                                    "category": "technology",
                                })
                    except Exception:
                        continue
                logger.info(f"Hacker News: found {len(topics)} topics")
        except Exception as e:
            logger.warning(f"News scouting failed: {e}")
        return topics

    def _rank_and_deduplicate(self, topics):
        blacklist = []
        filtered = [t for t in topics if not any(bl.lower() in t.get("title", "").lower() for bl in blacklist)]
        seen = set()
        unique = []
        for t in filtered:
            key = t["title"].lower()[:50]
            if key not in seen:
                seen.add(key)
                unique.append(t)
        unique.sort(key=lambda x: x.get("score", 0), reverse=True)
        return unique[:20]
