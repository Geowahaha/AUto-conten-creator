import time
import schedule
from datetime import datetime
from main import run_full_pipeline
from utils.config import load_config
from utils.logger import setup_logger

logger = setup_logger("scheduler")

def run_pipeline():
    logger.info(f"Scheduled run triggered at {datetime.now().isoformat()}")
    try:
        config = load_config()
        results = run_full_pipeline(config)
        logger.info(f"Scheduled run complete: {len(results)} videos produced")
    except Exception as e:
        logger.error(f"Scheduled run failed: {e}")

def main():
    config = load_config()
    upload_config = config.get("upload", {})
    hour1 = upload_config.get("schedule_hour", 10)
    hour2 = upload_config.get("schedule_hour2", 18)
    logger.info("Auto Content Creator Scheduler Started")
    logger.info(f"  Slot 1: {hour1:02d}:00")
    logger.info(f"  Slot 2: {hour2:02d}:00")
    schedule.every().day.at(f"{hour1:02d}:00").do(run_pipeline)
    schedule.every().day.at(f"{hour2:02d}:00").do(run_pipeline)
    logger.info("Running initial pipeline...")
    run_pipeline()
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
