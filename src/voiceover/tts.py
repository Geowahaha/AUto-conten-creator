import os
from pathlib import Path
from datetime import datetime
from utils.logger import setup_logger

logger = setup_logger("voiceover")

class VoiceoverEngine:
    def __init__(self, config):
        self.config = config
        self.output_dir = Path(config["output_dir"]) / "audio"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tts_config = config.get("tts", {})
        self.provider = self.tts_config.get("provider", "openai")

    def generate(self, script):
        scenes = script.get("scenes", [])
        full_text = " ".join(s.get("text", "") for s in scenes if s.get("text"))
        if not full_text:
            full_text = script.get("hook", "Check out this amazing content!")

        date_str = datetime.now().strftime("%Y-%m-%d")
        title = script.get("title", "untitled")
        safe_title = "".join(c for c in title[:30] if c.isalnum() or c in " _-").strip()
        audio_path = self.output_dir / f"{date_str}_{safe_title}.mp3"

        logger.info(f"Generating {self.provider} voiceover ({len(full_text)} chars)")

        if self.provider == "openai":
            return self._generate_openai(full_text, audio_path)
        elif self.provider == "elevenlabs":
            return self._generate_elevenlabs(full_text, audio_path)
        else:
            return self._generate_gtts(full_text, audio_path)

    def _generate_openai(self, text, output_path):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.config["openai"]["api_key"])
            tts = self.tts_config.get("openai", {})
            response = client.audio.speech.create(
                model=tts.get("model", "tts-1-hd"),
                voice=tts.get("voice", "nova"),
                input=text,
                response_format="mp3",
            )
            response.stream_to_file(str(output_path))
            logger.info(f"OpenAI TTS saved: {output_path}")
            return str(output_path)
        except Exception as e:
            logger.error(f"OpenAI TTS failed: {e}")
            return self._generate_gtts(text, output_path)

    def _generate_elevenlabs(self, text, output_path):
        try:
            from elevenlabs import ElevenLabs
            el = self.tts_config.get("elevenlabs", {})
            client = ElevenLabs(api_key=el.get("api_key"))
            audio_gen = client.text_to_speech.convert(
                voice_id=el.get("voice_id", "21m00Tcm4TlvDq8ikWAM"),
                text=text,
                model_id="eleven_multilingual_v2",
            )
            with open(output_path, "wb") as f:
                for chunk in audio_gen:
                    f.write(chunk)
            logger.info(f"ElevenLabs TTS saved: {output_path}")
            return str(output_path)
        except Exception as e:
            logger.error(f"ElevenLabs TTS failed: {e}")
            return self._generate_gtts(text, output_path)

    def _generate_gtts(self, text, output_path):
        try:
            from gtts import gTTS
            lang = self.config.get("content", {}).get("language", "en")
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(str(output_path))
            logger.info(f"gTTS saved: {output_path}")
            return str(output_path)
        except Exception as e:
            logger.error(f"gTTS failed: {e}")
            with open(output_path, "wb") as f:
                f.write(b"")
            return str(output_path)
