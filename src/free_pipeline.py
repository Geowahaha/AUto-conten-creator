"""
Auto Content Creator — Free Tier Version
Uses Pollinations.ai (free, no key) + gTTS (free)
Run full pipeline without any API keys.
"""

import json
import os
import sys
import requests
import time
from datetime import datetime
from pathlib import Path

# Config
OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
WIDTH = 1080
HEIGHT = 1920

def log(msg):
    print(f"  {msg}")

# ── Stage 1: Trend Scout ──────────────────────────────
def scout_trends():
    print("\n📡 Stage 1: Scouting trends...")
    topics = []
    
    # Hacker News
    try:
        resp = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10)
        for sid in resp.json()[:8]:
            r = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5)
            story = r.json()
            if story and story.get("title") and story.get("score", 0) > 50:
                topics.append({
                    "title": story["title"],
                    "source": "hackernews",
                    "score": story.get("score", 0),
                    "category": "technology"
                })
        log(f"  Hacker News: {len(topics)} topics")
    except Exception as e:
        log(f"  Hacker News failed: {e}")

    # Google Trends
    try:
        import xml.etree.ElementTree as ET
        resp = requests.get("https://trends.google.com/trending/rss?geo=US", timeout=10)
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            for item in root.findall(".//item")[:5]:
                title = item.find("title")
                if title is not None and title.text:
                    topics.append({
                        "title": title.text.strip(),
                        "source": "google_trends",
                        "score": 100,
                        "category": "trending"
                    })
            log(f"  Google Trends: added")
    except Exception as e:
        log(f"  Google Trends failed: {e}")

    # Sort by score
    topics.sort(key=lambda x: x.get("score", 0), reverse=True)
    log(f"  Total: {len(topics)} trending topics")
    return topics[:3]

# ── Stage 2: Script Writer (Pollinations.ai FREE) ────
def generate_script(topic):
    print(f"\n✍️ Stage 2: Writing script for: {topic['title'][:60]}...")
    
    prompt = f"""Create a YouTube Shorts script about: {topic['title']}
Category: {topic.get('category', 'general')}

Output STRICT JSON with this exact structure:
{{
  "title": "Video title (catchy, under 60 chars)",
  "hook": "Opening line that stops the scroll",
  "scenes": [
    {{"text": "Narration text", "duration": 5, "image_prompt": "Detailed vivid image prompt for vertical video", "caption": "On-screen text overlay"}}
  ],
  "cta": "Call to action",
  "tags": ["shorts", "relevant", "tags"],
  "total_duration": 45
}}

Rules: 5-6 scenes, each 4-7 seconds. Hook in first scene. CTA in last scene. Make image prompts vivid and specific for vertical (9:16) images. Output ONLY JSON."""

    try:
        url = "https://text.pollinations.ai/"
        payload = {
            "messages": [
                {"role": "system", "content": "You are an expert YouTube Shorts script writer. Output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "model": "openai",
            "jsonMode": True,
            "temperature": 0.8
        }
        resp = requests.post(url, json=payload, timeout=60)
        text = resp.text.strip()
        
        # Parse JSON - multiple strategies
        script = None
        
        # 1. Direct parse
        try:
            raw = json.loads(text)
            # If it has scenes array, use it directly
            if isinstance(raw, dict) and "scenes" in raw and isinstance(raw.get("scenes"), list) and len(raw["scenes"]) > 0:
                script = raw
            # If it has reasoning_content, extract JSON from it
            elif isinstance(raw, dict) and "reasoning_content" in raw:
                reasoning = raw["reasoning_content"]
                # Find JSON in reasoning
                start = reasoning.find("{")
                end = reasoning.rfind("}")
                if start >= 0 and end > start:
                    script = json.loads(reasoning[start:end+1])
            # Otherwise try the raw dict
            elif isinstance(raw, dict) and "title" in raw:
                script = raw
        except json.JSONDecodeError:
            pass
        
        # 2. Extract from markdown code blocks
        if script is None:
            for marker in ["```json\n", "```json", "```"]:
                if marker in text:
                    parts = text.split(marker, 1)
                    if len(parts) > 1:
                        chunk = parts[1].split("```")[0].strip()
                        try:
                            script = json.loads(chunk)
                            break
                        except:
                            pass
        
        # 3. Find first { to last } in raw text
        if script is None:
            # Look for JSON objects with "scenes" key
            import re
            json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
            for match in json_matches:
                try:
                    candidate = json.loads(match)
                    if "scenes" in candidate and isinstance(candidate.get("scenes"), list) and len(candidate["scenes"]) > 0:
                        script = candidate
                        break
                except:
                    pass
        
        # 4. Last resort: find any JSON
        if script is None:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    script = json.loads(text[start:end+1])
                except:
                    pass
        
        if script is None:
            raise ValueError("Could not parse JSON from response")
        
        script = _validate_script(script, topic)
        log(f"  Title: {script.get('title', 'Untitled')}")
        log(f"  Scenes: {len(script.get('scenes', []))}")
        log(f"  Duration: ~{script.get('total_duration', 0)}s")
        return script
    except Exception as e:
        log(f"  Script generation failed: {e}")
        log("  Using fallback script")
        return fallback_script(topic)

def _validate_script(script, topic):
    """Ensure script has all required fields."""
    script.setdefault("title", topic.get("title", "Untitled"))
    script.setdefault("hook", "Check this out!")
    script.setdefault("scenes", [])
    script.setdefault("cta", "Follow for more amazing content!")
    script.setdefault("tags", ["shorts", "trending", "facts"])
    script.setdefault("total_duration", 45)
    for i, scene in enumerate(script["scenes"]):
        scene.setdefault("text", "")
        scene.setdefault("duration", 5)
        scene.setdefault("image_prompt", f"Scene {i+1} for video about {script['title']}")
        scene.setdefault("caption", "")
    return script

def fallback_script(topic):
    title = topic.get("title", "Amazing Facts")
    return {
        "title": title[:60],
        "hook": f"Did you know this? {title[:40]}",
        "scenes": [
            {"text": f"Here's something incredible about {title[:50]}. You won't believe this.", "duration": 5, "image_prompt": f"dramatic cinematic scene, {title[:40]}, vibrant colors, vertical", "caption": "DID YOU KNOW?"},
            {"text": "The details behind this are even more fascinating.", "duration": 6, "image_prompt": f"eye-catching visual representation, {title[:40]}, detailed", "caption": "Here's the truth..."},
            {"text": "And this is just the beginning of the story.", "duration": 5, "image_prompt": f"mind-blowing reveal scene, dramatic lighting, {title[:30]}", "caption": "It gets crazier!"},
            {"text": "Follow for more mind-blowing content every day!", "duration": 4, "image_prompt": "vibrant subscribe button, social media icons, bright neon", "caption": "FOLLOW FOR MORE!"},
        ],
        "cta": "Follow for more!",
        "tags": ["shorts", "facts", "trending"],
        "total_duration": 20,
    }

# ── Stage 3: Media Generator (Pollinations.ai FREE) ──
def generate_images(script):
    print("\n🎨 Stage 3: Generating images...")
    date_str = datetime.now().strftime("%Y-%m-%d")
    title = script.get("title", "untitled")
    safe_title = "".join(c for c in title[:30] if c.isalnum() or c in " _-").strip()
    img_dir = OUTPUT_DIR / "images" / f"{date_str}_{safe_title}"
    img_dir.mkdir(parents=True, exist_ok=True)
    
    image_paths = []
    scenes = script.get("scenes", [])
    
    for i, scene in enumerate(scenes):
        prompt = scene.get("image_prompt", f"Scene {i+1}")
        # Enhance prompt for vertical video
        enhanced = f"{prompt}, cinematic, high contrast, vibrant colors, 9:16 vertical composition, no text"
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(enhanced)}?width=1080&height=1920&nologo=true&seed={i*42}"
        
        try:
            log(f"  Generating scene {i+1}/{len(scenes)}...")
            resp = requests.get(url, timeout=60)
            if resp.status_code == 200 and len(resp.content) > 1000:
                path = img_dir / f"scene_{i+1:02d}.jpg"
                with open(path, "wb") as f:
                    f.write(resp.content)
                image_paths.append(str(path))
                log(f"    Saved: {path.name} ({len(resp.content)//1024}KB)")
            else:
                log(f"    Failed: HTTP {resp.status_code}")
                path = create_gradient_image(img_dir, i, scene.get("caption", ""))
                image_paths.append(str(path))
        except Exception as e:
            log(f"    Failed: {e}")
            path = create_gradient_image(img_dir, i, scene.get("caption", ""))
            image_paths.append(str(path))
        
        time.sleep(1)  # Be nice to free API
    
    return image_paths

def create_gradient_image(output_dir, index, text=""):
    """Create gradient fallback image."""
    from PIL import Image, ImageDraw, ImageFont
    
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    
    palettes = [
        [(30, 0, 50), (100, 0, 150), (200, 0, 100)],
        [(0, 20, 50), (0, 80, 150), (0, 150, 200)],
        [(20, 0, 0), (100, 30, 0), (200, 80, 0)],
        [(0, 30, 0), (0, 100, 50), (0, 180, 100)],
    ]
    colors = palettes[index % len(palettes)]
    
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        if ratio < 0.5:
            r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * ratio * 2)
            g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * ratio * 2)
            b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * ratio * 2)
        else:
            r = int(colors[1][0] + (colors[2][0] - colors[1][0]) * (ratio - 0.5) * 2)
            g = int(colors[1][1] + (colors[2][1] - colors[1][1]) * (ratio - 0.5) * 2)
            b = int(colors[1][2] + (colors[2][2] - colors[1][2]) * (ratio - 0.5) * 2)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))
    
    if text:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
        except:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 56)
            except:
                font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        y = (HEIGHT - (bbox[3] - bbox[1])) // 2
        draw.text((x+3, y+3), text, fill=(0, 0, 0), font=font)
        draw.text((x, y), text, fill=(255, 255, 255), font=font)
    
    path = output_dir / f"scene_{index+1:02d}.png"
    img.save(path, "PNG")
    return path

# ── Stage 4: Voiceover (gTTS FREE) ───────────────────
def generate_voiceover(script):
    print("\n🎙️ Stage 4: Generating voiceover...")
    from gtts import gTTS
    
    scenes = script.get("scenes", [])
    full_text = " ".join(s.get("text", "") for s in scenes if s.get("text"))
    if not full_text:
        full_text = script.get("hook", "Check this out!")
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    title = script.get("title", "untitled")
    safe_title = "".join(c for c in title[:30] if c.isalnum() or c in " _-").strip()
    audio_dir = OUTPUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / f"{date_str}_{safe_title}.mp3"
    
    tts = gTTS(text=full_text, lang="en", slow=False)
    tts.save(str(audio_path))
    log(f"  Saved: {audio_path.name} ({os.path.getsize(audio_path)//1024}KB)")
    return str(audio_path)

# ── Stage 5: Video Assembly (FFmpeg) ──────────────────
def assemble_video(script, image_paths, audio_path):
    print("\n🎬 Stage 5: Assembling video...")
    import subprocess
    import tempfile
    
    date_str = datetime.now().strftime("%Y-%m-%d")
    title = script.get("title", "untitled")
    safe_title = "".join(c for c in title[:30] if c.isalnum() or c in " _-").strip()
    video_dir = OUTPUT_DIR / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    video_path = video_dir / f"{date_str}_{safe_title}.mp4"
    
    scenes = script.get("scenes", [])
    
    # Create concat file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        concat_file = f.name
        for i, (img_path, scene) in enumerate(zip(image_paths, scenes)):
            duration = scene.get("duration", 5)
            f.write(f"file '{os.path.abspath(img_path)}'\n")
            f.write(f"duration {duration}\n")
        if image_paths:
            f.write(f"file '{os.path.abspath(image_paths[-1])}'\n")
    
    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-i", audio_path,
            "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            "-pix_fmt", "yuv420p",
            "-r", "30",
            str(video_path),
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            log(f"  FFmpeg error: {result.stderr[:300]}")
            raise RuntimeError(f"FFmpeg failed")
        
        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        log(f"  Video assembled: {video_path.name} ({size_mb:.1f}MB)")
        return str(video_path)
    finally:
        os.unlink(concat_file)

# ── Main Pipeline ─────────────────────────────────────
def main():
    print("=" * 60)
    print("🚀 AUTO CONTENT CREATOR — FREE TIER PIPELINE")
    print("=" * 60)
    
    # Stage 1: Trends
    topics = scout_trends()
    if not topics:
        topics = [{"title": "Mind-blowing AI facts", "category": "technology", "score": 100}]
    
    # Pick top topic
    topic = topics[0]
    print(f"\n📌 Selected topic: {topic['title']}")
    
    # Stage 2: Script
    script = generate_script(topic)
    
    # Save script
    script_dir = OUTPUT_DIR / "scripts"
    script_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
    script_path = script_dir / f"{date_str}.json"
    with open(script_path, "w") as f:
        json.dump(script, f, indent=2, ensure_ascii=False)
    log(f"Script saved: {script_path}")
    
    # Stage 3: Images
    image_paths = generate_images(script)
    
    # Stage 4: Voiceover
    audio_path = generate_voiceover(script)
    
    # Stage 5: Video
    video_path = assemble_video(script, image_paths, audio_path)
    
    # Summary
    print("\n" + "=" * 60)
    print("🏁 PIPELINE COMPLETE!")
    print(f"  📝 Script: {script_path}")
    print(f"  🖼️  Images: {len(image_paths)} files")
    print(f"  🔊 Audio: {audio_path}")
    print(f"  🎬 Video: {video_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
