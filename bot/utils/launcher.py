import os
import glob
import json
import asyncio
import argparse
from itertools import cycle

from pyrogram import Client
from better_proxy import Proxy
from fake_useragent import UserAgent

from bot.config import settings
from bot.utils import logger
from bot.core.tapper import run_tapper
from bot.core.registrator import register_sessions

start_text = """

███╗   ██╗ ██████╗ ████████╗██████╗ ██╗██╗  ██╗███████╗██╗
████╗  ██║██╔═══██╗╚══██╔══╝██╔══██╗██║╚██╗██╔╝██╔════╝██║
██╔██╗ ██║██║   ██║   ██║   ██████╔╝██║ ╚███╔╝ █████╗  ██║
██║╚██╗██║██║   ██║   ██║   ██╔═══╝ ██║ ██╔██╗ ██╔══╝  ██║
██║ ╚████║╚██████╔╝   ██║   ██║     ██║██╔╝ ██╗███████╗███████╗
╚═╝  ╚═══╝ ╚═════╝    ╚═╝   ╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝

🎨️Github - https://github.com/YarmolenkoD/notpixel

My other bots:

💩Boinkers - https://github.com/YarmolenkoD/boinkers
🚀Moonbix - https://github.com/YarmolenkoD/moonbix [GAME IS NOT WORKING]

Select an action:

    1. Start drawing 🎨️
    2. Create a session 👨‍🎨
    3. Get actual templates list 🖼
"""

global tg_clients


def get_session_names() -> list[str]:
    session_names = sorted(glob.glob("sessions/*.session"))
    session_names = [
        os.path.splitext(os.path.basename(file))[0] for file in session_names
    ]

    return session_names


def get_proxies() -> list[Proxy]:
    if settings.USE_PROXY_FROM_FILE:
        with open(file="bot/config/proxies.txt", encoding="utf-8") as file:
            proxies = [Proxy.from_str(proxy=row.strip()).as_url for row in file]
    else:
        proxies = []

    return proxies

def get_session_data(sessions: list) -> dict:
	data_file = 'session_data.json'
	data = {}
	if os.path.exists(data_file):
		try:
			with open(file=data_file, encoding='utf-8') as file:
				data = json.load(file)
		except Exception as error:
			logger.error(f"Error when loading session data: {error}")
	
	all_data_exists = True if all(session in data for session in sessions) else False
	if not all_data_exists:
		ua = UserAgent(os=['android'])
		proxies = get_proxies()
		proxies_cycle = cycle(proxies) if proxies else cycle([None])
		for session in sessions:
			if not session in data:
				useragent = ua.random
				proxy = next(proxies_cycle)
				data[session] = {'ua': useragent, 'proxy': proxy}
		
		with open(data_file, 'w', encoding='utf-8') as file:
			json.dump(data, file, ensure_ascii=False, indent=4)
	
	return data

async def get_tg_clients() -> tuple[list[Client], dict]:
    global tg_clients

    session_names = get_session_names()
    session_data = get_session_data(session_names)
    
    if not session_names:
        raise FileNotFoundError("Not found session files")

    if not settings.API_ID or not settings.API_HASH:
        raise ValueError("API_ID and API_HASH not found in the .env file.")

    tg_clients = []
    for session_name in session_names:
        proxy = {
			"scheme": settings.PROXY_TYPE,
			"hostname": session_data[session_name]["proxy"].split(":")[1].split("@")[1],
			"port": int(session_data[session_name]["proxy"].split(":")[2]),
			"username": session_data[session_name]["proxy"].split(":")[0],
			"password": session_data[session_name]["proxy"].split(":")[1].split("@")[0]
		} if session_data[session_name]["proxy"] else None

        tg_clients.append(Client(
			name=session_name,
			api_id=settings.API_ID,
			api_hash=settings.API_HASH,
			workdir='sessions/',
			plugins=dict(root='bot/plugins'),
			proxy=proxy
		))

    return tg_clients, session_data

async def process() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--action", type=int, help="Action to perform")

    logger.info(f"Detected {len(get_session_names())} sessions | {len(get_proxies())} proxies")

    action = parser.parse_args().action

    if not action:
        print(start_text)

        while True:
            action = input("> ")

            if not action.isdigit():
                logger.warning("Action must be number")
            elif action not in ["1", "2", "3"]:
                logger.warning("Action must be 1, 2 or 3")
            else:
                action = int(action)
                break

    if action == 1:
        await register_sessions()

    elif action == 2:
        tg_clients, session_data = await get_tg_clients()
    
        await run_tasks(tg_clients=tg_clients, session_data=session_data)
    elif action == 3:
        settings.SHOW_TEMPLATES_LIST = True
        tg_clients, session_data = await get_tg_clients()

        await run_tasks(tg_clients=[tg_clients[0]], session_data=session_data[tg_clients[0].name])

async def run_tasks(tg_clients: list[Client], session_data: dict):
    tasks = [
        asyncio.create_task(
            run_tapper(
                tg_client=tg_client,
                data=session_data[tg_client.name]
            )
        )
        for tg_client in tg_clients
    ]

    await asyncio.gather(*tasks)
