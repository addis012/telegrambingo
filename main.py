import os
import asyncio
from app import app
from bot import main as bot_main
from multiprocessing import Process

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=True)

def run_bot():
    asyncio.run(bot_main())

if __name__ == "__main__":
    # Start Flask in a separate process
    flask_process = Process(target=run_flask)
    flask_process.start()

    # Run the bot in the main process
    try:
        run_bot()
    except KeyboardInterrupt:
        flask_process.terminate()
        flask_process.join()