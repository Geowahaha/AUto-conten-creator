import os
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime
from utils.logger import setup_logger

logger = setup_logger("video_assembly")

class VideoAssembler:
    def __init__(self, config):
        self.config = config
        self.output_dir = Path(config["output_dir"]) / "video"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.width = config.get("video", {}).get("width", 1080)
        self.height = config.get("video", {}).get("height", 1920)
        self.fps = config.get("video", {}).get("fps", 30)
        self.scene_duration = config.get("video", {}).get("scene_duration", 5)

    def assemble(self, script, image_paths, audio_path):
        title = script.get("title", "untitled")
        scenes = script.get("scenes", [])
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_title = "".join(c for c in title[:30] if c.isalnum() or c in " _-").strip()
        video_path = self.output_dir / f"{date_str}_{safe_title}.mp4"
        logger.info(f"Assembling video: {video_path.name}")
        try:
            return self._assemble_with_moviepy(script, image_paths, audio_path, video_path)
        except ImportError:
            logger.warning("MoviePy not available, falling back to FFmpeg")
            return self._assemble_with_ffmpeg(script, image_paths, audio_path, video_path)

    def _assemble_with_moviepy(self, script, image_paths, audio_path, video_path):
        from moviepy import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont

        scenes = script.get("scenes", [])
        try:
            audio_clip = AudioFileClip(audio_path)
            total_duration = audio_clip.duration
        except:
            audio_clip = None
            total_duration = sum(s.get("duration", self.scene_duration) for s in scenes)

        duration_per_scene = total_duration / max(len(image_paths), 1)
        clips = []
        for i, (img_path, scene) in enumerate(zip(image_paths, scenes)):
            duration = scene.get("duration", duration_per_scene)
            img_clip = ImageClip(img_path).with_duration(duration).resized((self.width, self.height))
            caption = scene.get("caption", "")
            if caption:
                try:
                    cap_img = self._create_caption_image(caption)
                    cap_clip = ImageClip(np.array(cap_img)).with_duration(duration).with_position(("center", self.height - 300))
                    clip = CompositeVideoClip([img_clip, cap_clip])
                except:
                    clip = img_clip
            else:
                clip = img_clip
            clips.append(clip)

        video = concatenate_videoclips(clips, method="compose")
        if audio_clip:
            if audio_clip.duration > video.duration:
                audio_clip = audio_clip.subclipped(0, video.duration)
            video = video.with_audio(audio_clip)

        video.write_videofile(str(video_path), fps=self.fps, codec="libx264", audio_codec="aac", bitrate="8000k", logger=None)
        video.close()
        if audio_clip:
            audio_clip.close()
        logger.info(f"Video assembled: {video_path}")
        return str(video_path)

    def _create_caption_image(self, text):
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGBA", (self.width - 100, 200), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        except:
            font = ImageFont.load_default()
        draw.rounded_rectangle([0, 0, img.width, img.height], radius=20, fill=(0, 0, 0, 180))
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (img.width - (bbox[2] - bbox[0])) // 2
        y = (img.height - (bbox[3] - bbox[1])) // 2
        draw.text((x, y), text, fill="white", font=font)
        return img

    def _assemble_with_ffmpeg(self, script, image_paths, audio_path, video_path):
        scenes = script.get("scenes", [])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            concat_file = f.name
            for i, (img_path, scene) in enumerate(zip(image_paths, scenes)):
                f.write(f"file '{img_path}'\nduration {scene.get('duration', self.scene_duration)}\n")
            if image_paths:
                f.write(f"file '{image_paths[-1]}'\n")
        try:
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-i", audio_path,
                   "-vf", f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2",
                   "-c:v", "libx264", "-c:a", "aac", "-shortest", "-pix_fmt", "yuv420p", "-r", str(self.fps), str(video_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg failed: {result.stderr}")
            logger.info(f"Video assembled with FFmpeg: {video_path}")
            return str(video_path)
        finally:
            os.unlink(concat_file)
