import json
from openai import OpenAI
from utils.logger import setup_logger

logger = setup_logger("script_writer")

SCRIPT_SYSTEM_PROMPT = (
    'You are an expert short-form video script writer for YouTube Shorts.\n'
    'Output STRICT JSON: {"title":"..","hook":"..","scenes":[{"text":"..","duration":5,"image_prompt":"..","caption":".."}],"cta":"..","tags":[".."],"total_duration":45}\n'
    'Rules: 5-8 scenes, each 4-7 seconds, hook in first scene, CTA in last scene. Pure JSON only.'
)

class ScriptWriter:
    def __init__(self, config):
        self.config = config
        self.client = OpenAI(api_key=config["openai"]["api_key"])
        self.model = config["openai"].get("model", "gpt-4o")
        self.style = config.get("content", {}).get("style", "informative")
        self.video_duration = config.get("content", {}).get("video_duration", 45)
        self.language = config.get("content", {}).get("language", "en")

    def generate(self, topic):
        topic_title = topic.get("title", str(topic))
        category = topic.get("category", "general")
        user_prompt = (
            f"Create a YouTube Shorts script about: {topic_title}\n"
            f"Category: {category}\n"
            f"Style: {self.style}\n"
            f"Target: {self.video_duration}s\n"
            f"Language: {self.language}"
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SCRIPT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.8,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            script = json.loads(content)
            script = self._validate_script(script, topic)
            logger.info(
                f"Generated script: '{script.get('title', 'Untitled')}' "
                f"({len(script.get('scenes', []))} scenes)"
            )
            return script
        except Exception as e:
            logger.error(f"Script generation failed: {e}")
            return self._fallback_script(topic)

    def _validate_script(self, script, topic):
        script.setdefault("title", topic.get("title", "Untitled"))
        script.setdefault("hook", "Check this out!")
        script.setdefault("scenes", [])
        script.setdefault("cta", "Follow for more amazing content!")
        script.setdefault("tags", ["shorts", "trending", "facts"])
        script.setdefault("total_duration", self.video_duration)
        for i, scene in enumerate(script["scenes"]):
            scene.setdefault("text", "")
            scene.setdefault("duration", 5)
            scene.setdefault("image_prompt", f"Scene {i+1} for video about {script['title']}")
            scene.setdefault("caption", "")
        return script

    def _fallback_script(self, topic):
        title = topic.get("title", "Amazing Facts")
        return {
            "title": title,
            "hook": f"Did you know this about {title}?",
            "scenes": [
                {
                    "text": f"Did you know this about {title}? You won't believe what we found.",
                    "duration": 5,
                    "image_prompt": f"Dramatic cinematic image related to {title}",
                    "caption": "DID YOU KNOW?",
                },
                {
                    "text": f"Here's something incredible about {title}.",
                    "duration": 6,
                    "image_prompt": f"Eye-catching visual of {title}",
                    "caption": "Here's the truth...",
                },
                {
                    "text": "And that's just the beginning.",
                    "duration": 5,
                    "image_prompt": f"Mind-blowing reveal for {title}",
                    "caption": "It gets crazier",
                },
            ],
            "cta": "Follow for more mind-blowing content!",
            "tags": ["shorts", "facts", "mindblowing"],
            "total_duration": 20,
        }
