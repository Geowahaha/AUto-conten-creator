import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils.config import load_config
from utils.logger import setup_logger

logger = setup_logger("main")

def run_trending(config):
    from trend_scout.scout import TrendScout
    scout = TrendScout(config)
    topics = scout.discover()
    logger.info(f"Found {len(topics)} trending topics")
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_path = Path(config["output_dir"]) / "topics" / f"{date_str}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(topics, f, indent=2, default=str)
    return topics

def run_script(config, topic=None, topics=None):
    from script_writer.writer import ScriptWriter
    writer = ScriptWriter(config)
    if topic:
        scripts = [writer.generate(topic)]
    elif topics:
        max_scripts = config.get("content", {}).get("max_scripts_per_run", 3)
        scripts = [writer.generate(t) for t in topics[:max_scripts]]
    else:
        logger.error("No topic provided for script generation")
        return []
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir = Path(config["output_dir"]) / "scripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, script in enumerate(scripts):
        script_path = out_dir / f"{date_str}_{i+1:03d}.json"
        with open(script_path, "w") as f:
            json.dump(script, f, indent=2, ensure_ascii=False)
        logger.info(f"Script saved: {script_path}")
    return scripts

def run_media(config, script):
    from media_gen.generator import MediaGenerator
    gen = MediaGenerator(config)
    return gen.generate(script)

def run_voiceover(config, script):
    from voiceover.tts import VoiceoverEngine
    engine = VoiceoverEngine(config)
    return engine.generate(script)

def run_video(config, script, images, audio_path):
    from video_assembly.assembler import VideoAssembler
    assembler = VideoAssembler(config)
    return assembler.assemble(script, images, audio_path)

def run_upload(config, video_path, script):
    from youtube_upload.uploader import YouTubeUploader
    uploader = YouTubeUploader(config)
    return uploader.upload(video_path, script)

def run_full_pipeline(config):
    logger.info("=" * 60)
    logger.info("Starting Auto Content Creator Pipeline")
    logger.info("=" * 60)

    logger.info("\nStage 1: Scanning for trending topics...")
    topics = run_trending(config)
    if not topics:
        logger.warning("No trending topics found. Using fallback topics.")
        topics = [
            {"title": "Mind-blowing AI facts", "category": "technology", "score": 0.9},
            {"title": "Unbelievable science discoveries", "category": "science", "score": 0.85},
            {"title": "Strange facts about the universe", "category": "science", "score": 0.8},
        ]

    logger.info("\nStage 2: Generating scripts...")
    scripts = run_script(config, topics=topics)

    results = []
    for i, script in enumerate(scripts):
        logger.info(f"Processing script {i+1}/{len(scripts)}: {script.get('title', 'Untitled')}")
        try:
            logger.info("Stage 3: Generating scene images...")
            images = run_media(config, script)
            logger.info("Stage 4: Generating voiceover...")
            audio_path = run_voiceover(config, script)
            logger.info("Stage 5: Assembling video...")
            video_path = run_video(config, script, images, audio_path)
            if config.get("upload", {}).get("auto_publish", False):
                logger.info("Stage 6: Uploading to YouTube...")
                result = run_upload(config, video_path, script)
            else:
                logger.info("Skipping upload (auto_publish disabled)")
                result = {"status": "skipped", "video": str(video_path)}
            results.append({"script": script, "video": str(video_path), "upload": result})
            logger.info(f"Completed: {video_path}")
        except Exception as e:
            logger.error(f"Failed on script {i+1}: {e}")
            continue

    logger.info("=" * 60)
    logger.info(f"Pipeline Complete: {len(results)}/{len(scripts)} videos created")
    for r in results:
        logger.info(f"  - {r['script'].get('title', 'Untitled')} -> {r['video']}")
    logger.info("=" * 60)
    return results

def main():
    parser = argparse.ArgumentParser(description="Auto Content Creator")
    parser.add_argument("--stage", choices=["trending", "script", "media", "voice", "video", "upload", "full"], default="full")
    parser.add_argument("--topic", type=str)
    parser.add_argument("--script", type=str)
    parser.add_argument("--video", type=str)
    parser.add_argument("--config", type=str, default="config/config.yaml")
    args = parser.parse_args()
    config = load_config(args.config)

    if args.stage == "full":
        run_full_pipeline(config)
    elif args.stage == "trending":
        run_trending(config)
    elif args.stage == "script":
        run_script(config, topic=args.topic)
    elif args.stage == "media":
        with open(args.script) as f:
            run_media(config, json.load(f))
    elif args.stage == "voice":
        with open(args.script) as f:
            run_voiceover(config, json.load(f))
    elif args.stage == "video":
        with open(args.script) as f:
            script = json.load(f)
        images = run_media(config, script)
        audio = run_voiceover(config, script)
        run_video(config, script, images, audio)
    elif args.stage == "upload":
        with open(args.script) as f:
            run_upload(config, args.video, json.load(f))

if __name__ == "__main__":
    main()
