import database as db
import email_engine as engine
import config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("send_daily")

def run():
    logger.info("Starting daily batch from PythonAnywhere Scheduled Task...")
    # Send all 62 emails for the day in one go, slowly.
    # PythonAnywhere gives us 2 hours for a script, which is plenty for 62 emails (takes ~1.5 hours)
    db.initialize_db()
    engine.download_resume()
    
    # We send the DAILY_LIMIT in one batch since this runs once a day
    engine.send_batch_sync(config.DAILY_LIMIT)
    logger.info("Daily batch finished.")

if __name__ == "__main__":
    run()
