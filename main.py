import asyncio
import uuid
import json
import time
import logging
from datetime import datetime
from faker import Faker
import aiohttp
from aiohttp_socks import ProxyConnector
import colorlog
import random

# Set up logging with colorlog
handler = colorlog.StreamHandler()
formatter = colorlog.ColoredFormatter(
    "%(log_color)s[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    }
)
handler.setFormatter(formatter)

logger = logging.getLogger("WebSocketClient")
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)  # Set to DEBUG for detailed log output

# Load configuration from settings.json
with open('configs.json', 'r') as f:
    config = json.load(f)

# Get WebSocket URL and User ID from configs.json
url = config["websocket"]["url"]
user_id = config["settings"]["user_id"]
use_proxy = config["settings"]["use_proxy"]

# Read proxies from proxy_list.txt if use_proxy is True
proxies = []
if use_proxy:
    with open(config["network"]["proxy_list"], 'r') as f:
        proxies = [line.strip() for line in f.readlines()]

# Generate a random user agent
fake = Faker()
user_agent = fake.user_agent()

async def send_auth(ws, device_id):
    auth_id = str(uuid.uuid4())
    timestamp = int(time.time())
    auth_message = {
        "id": auth_id,
        "origin_action": "AUTH",
        "result": {
            "browser_id": device_id,
            "user_id": user_id,
            "user_agent": user_agent,
            "timestamp": timestamp,
            "device_type": "extension",
            "version": "4.26.2",
            "extension_id": "ilehaonighjijnmpnagapkhpcdbhclfg"
        }
    }
    await ws.send_str(json.dumps(auth_message))
    logger.info(f"Sent AUTH message: {auth_message}")

async def send_ping(ws):
    while True:
        try:
            ping_message = {
                "id": str(uuid.uuid4()),
                "version": "1.0.0",
                "action": "PING",
                "data": {}
            }
            await ws.send_str(json.dumps(ping_message))
            logger.debug(f"Sent PING message: {ping_message}")
            await asyncio.sleep(random.randint(20,60))
        except aiohttp.ClientError:
            logger.warning("Connection closed during PING, stopping ping task.")
            break

async def handle_messages(ws, device_id):
    try:
        async for message in ws:
            data = json.loads(message.data)
            logger.info(f"Received message: {data}")
            if data.get("action") == "AUTH":
                await send_auth(ws, device_id)
                asyncio.create_task(send_ping(ws))
            elif data.get("action") == "PONG":
                pong_ack = {
                    "id": data["id"],
                    "origin_action": "PONG"
                }
                await ws.send_str(json.dumps(pong_ack))
                logger.debug(f"Sent PONG acknowledgment: {pong_ack}")
    except aiohttp.ClientError:
        logger.warning("Connection closed during message handling, stopping message handler.")

async def connect(proxy=None):
    device_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, proxy if proxy else "local"))
    while True:
        try:
            connector = ProxyConnector.from_url(proxy) if proxy else None
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.ws_connect(url, headers={
                    "Pragma": "no-cache",
                    "Cache-Control": "no-cache",
                    "User-Agent": user_agent,
                    "Origin": "chrome-extension://ilehaonighjijnmpnagapkhpcdbhclfg"
                }) as ws:
                    logger.info(f"Connected to WebSocket server {'with proxy: ' + proxy if proxy else 'without proxy'}")
                    await handle_messages(ws, device_id)

        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            logger.error(f"Connection error on {'proxy ' + proxy if proxy else 'local connection'}: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.critical(f"Unexpected error on {'proxy ' + proxy if proxy else 'local connection'}: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

async def main():
    if use_proxy and proxies:
        tasks = []
        for proxy in proxies:
            tasks.append(asyncio.create_task(connect(proxy)))
            await asyncio.sleep(1)  # Delay 1 detik antara inisialisasi setiap task
        await asyncio.gather(*tasks)
    else:
        # Run a single task without proxy if use_proxy is False or no proxies are available
        await connect()

# Run the WebSocket client
asyncio.run(main())
