import os
import requests
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from utils.logger import setup_logger

logger = setup_logger("media_gen")

class MediaGenerator:
    def __init__(self, config):
        self.config = config
        self.output_dir = Path(config["output_dir"]) / "images"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.width = config.get("video", {}).get("width", 1080)
        self.height = config.get("video", {}).get("height", 1920)
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=config["openai"]["api_key"])
            self.image_model = config["openai"].get("image_model", "dall-e-3")
            self.use_ai = True
        except Exception:
            self.use_ai = False
            logger.warning("OpenAI not configured, using gradient fallback")

    def generate(self, script):
        title = script.get("title", "untitled")
        scenes = script.get("scenes", [])
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_title = "".join(c for c in title[:30] if c.isalnum() or c in " _-").strip()
        video_dir = self.output_dir / f"{date_str}_{safe_title}"
        video_dir.mkdir(parents=True, exist_ok=True)
        image_paths = []
        for i, scene in enumerate(scenes):
            prompt = scene.get("image_prompt", f"Scene {i+1}")
            caption = scene.get("caption", "")
            try:
                if self.use_ai:
                    path = self._generate_ai_image(prompt, video_dir, i)
                else:
                    path = self._generate_gradient_image(caption or prompt, video_dir, i)
            except Exception as e:
                logger.warning(f"AI image failed for scene {i+1}, using fallback: {e}")
                path = self._generate_gradient_image(caption or prompt, video_dir, i)
            image_paths.append(str(path))
            logger.info(f"  Scene {i+1}/{len(scenes)}: {path.name}")
        return image_paths

    def _generate_ai_image(self, prompt, output_dir, index):
        enhanced = f"{prompt}. Style: vibrant, cinematic, high contrast, vertical video (9:16), no text"
        response = self.client.images.generate(model=self.image_model, prompt=enhanced, size="1024x1792", quality="standard", n=1)
        img_data = requests.get(response.data[0].url, timeout=30).content
        path = output_dir / f"scene_{index+1:02d}.png"
        with open(path, "wb") as f:
            f.write(img_data)
        img = Image.open(path).resize((self.width, self.height), Image.LANCZOS)
        img.save(path, "PNG")
        return path

    def _generate_gradient_image(self, text, output_dir, index):
        img = Image.new("RGB", (self.width, self.height))
        draw = ImageDraw.Draw(img)
        palettes = [[(30,0,50),(100,0,150),(200,0,100)],[(0,20,50),(0,80,150),(0,150,200)],[(20,0,0),(100,30,0),(200,80,0)],[(0,30,0),(0,100,50),(0,180,100)],[(40,0,60),(80,0,120),(150,50,200)]]
        colors = palettes[index % len(palettes)]
        for y in range(self.height):
            ratio = y / self.height
            if ratio < 0.5:
                r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * ratio * 2)
                g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * ratio * 2)
                b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * ratio * 2)
            else:
                r = int(colors[1][0] + (colors[2][0] - colors[1][0]) * (ratio - 0.5) * 2)
                g = int(colors[1][1] + (colors[2][1] - colors[1][1]) * (ratio - 0.5) * 2)
                b = int(colors[1][2] + (colors[2][2] - colors[1][2]) * (ratio - 0.5) * 2)
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))
        if text:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 56)
            except:
                font = ImageFont.load_default()
            words = text.split()
            lines, cur = [], ""
            for w in words:
                test = f"{cur} {w}".strip()
                bbox = draw.textbbox((0,0), test, font=font)
                if bbox[2]-bbox[0] > self.width-100:
                    lines.append(cur)
                    cur = w
                else:
                    cur = test
            if cur: lines.append(cur)
            y0 = (self.height - len(lines)*70) // 2
            for i, line in enumerate(lines):
                bbox = draw.textbbox((0,0), line, font=font)
                x = (self.width - (bbox[2]-bbox[0])) // 2
                y = y0 + i*70
                draw.text((x+3,y+3), line, fill=(0,0,0), font=font)
                draw.text((x,y), line, fill=(255,255,255), font=font)
        path = output_dir / f"scene_{index+1:02d}.png"
        img.save(path, "PNG")
        return path
