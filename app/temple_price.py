import math

import discord
import requests
from discord import Client
from discord.ext import tasks
from loguru import logger

from app.bot import update_bot
from app.utils import roundf


class PriceFetchError(Exception):
    ...


def millify(n, precision):
    millnames = ["", "K", "M", "B", "T"]
    n = float(n)
    millidx = max(
        0,
        min(
            len(millnames) - 1, int(math.floor(0 if n == 0 else math.log10(abs(n)) / 3))
        ),
    )

    return "{:.{precision}f}{}".format(
        n / 10 ** (3 * millidx), millnames[millidx], precision=precision
    )


def get_json_data(url, query):
    response = requests.post(url, json={"query": query})

    try:
        data = response.json()
    except:  # noqa: E722
        raise PriceFetchError("Invalid response from API: {response.text}")

    if response.status_code != 200 or "errors" in data:
        raise PriceFetchError(f"Error fetching price {response.text}")

    return data


def get_price():
    query = """query {
          metrics {
            templePrice
            treasuryPriceIndex
          }
    }"""

    url = "https://api.goldsky.com/api/public/project_cmgzm4q1q009c5np2angrczxw/subgraphs/temple-metrics/prod/gn"
    data = get_json_data(url, query)

    metrics = data["data"]["metrics"][0]

    return {
        "spot_price": float(metrics["templePrice"]),
        "tpi": float(metrics["treasuryPriceIndex"]),
    }


def compute_price_premium(spot: float, tpi: float) -> float:
    return spot / tpi


async def refresh_price(client: Client):
    logger.info("Updating TEMPLE price")
    try:
        metrics = get_price()
        price = metrics["spot_price"]
        tpi = metrics["tpi"]
        premium = compute_price_premium(price, tpi)
    except Exception as err:
        logger.exception(f"Error refreshing price {err}")
        nickname = "ERROR"
        tpi = 0
    else:
        nickname = f"${roundf(price, 3)} | {premium:.2f}x TPI"

    activity = f"TPI rise: ${roundf(tpi, 4)}"
    await update_bot(client, nickname, activity)


def create_price_bot():

    PRICE_BOT = discord.Client()

    @PRICE_BOT.event
    async def on_ready():
        logger.info(f"{PRICE_BOT.user} ready")
        update_price.start()

    @tasks.loop(seconds=5 * 60)
    async def update_price():
        try:
            await refresh_price(PRICE_BOT)
        except Exception as err:
            print(f"ERROR: refreshing price {err}")

    return PRICE_BOT
