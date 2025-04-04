from loguru import logger
import requests
import discord
from discord.ext import tasks
import os
from dotenv import load_dotenv
import math

load_dotenv()


TOKEN = os.getenv("DISCORD_TOKEN")
REFRESH_RATE_S = int(os.getenv("REFRESH_RATE_S", 90))
client = discord.Client()


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


def roundf(n, precision):
    return "{:.{precision}f}".format(float(n), precision=precision)


def get_json_data(url, query):
    response = requests.post(url, json={"query": query})

    try:
        data = response.json()
    except:  # noqa: E722
        raise PriceFetchError("Invalid response from API: {response.text}")

    if response.status_code != 200 or "errors" in data:
        raise PriceFetchError(f"Error fetching price {response.text}")

    return data


def get_tpi():
    query = """query {
          treasuryReservesVaults {
            treasuryPriceIndex
          }
    }"""

    url = (
        "https://subgraph.satsuma-prod.com/a912521dd162/templedao/temple-v2-mainnet/api"
    )
    data = get_json_data(url, query)

    metrics = data["data"]["treasuryReservesVaults"][0]

    return {
        "tpi": float(metrics["treasuryPriceIndex"]),
    }


def get_price():
    req = requests.get(
        "https://coins.llama.fi/prices/current/ethereum:0x470EBf5f030Ed85Fc1ed4C2d36B9DD02e77CF1b7"
    )
    return float(
        req.json()["coins"]["ethereum:0x470EBf5f030Ed85Fc1ed4C2d36B9DD02e77CF1b7"][
            "price"
        ]
    )


@client.event
async def on_ready():
    logger.info(f"{client.user} has connected to Discord!")
    refresh_price.start()


def compute_price_premium(spot: float, tpi: float) -> float:
    return spot / tpi


async def _refresh_price():
    logger.info("Refreshing price")
    try:
        metrics = get_tpi()
        price = get_price()
        tpi = metrics["tpi"]
        premium = compute_price_premium(price, tpi)
    except Exception as err:
        logger.exception(f"Error refreshing price {err}")
        nickname = "ERROR"
        tpi = 0
    else:
        nickname = f"${roundf(price, 3)} | {premium:.2f}x TPI"

    activity = f"TPI rise: ${roundf(tpi, 4)}"

    logger.info(
        "New stats {nickname} || {activity}", nickname=nickname, activity=activity
    )

    await client.change_presence(
        activity=discord.Activity(name=activity, type=discord.ActivityType.watching)
    )
    for guild in client.guilds:
        try:
            await guild.me.edit(nick=nickname)
        except Exception as err:
            logger.info(f"ERROR: {err} in guild {guild.id} {guild.name}")


@tasks.loop(seconds=REFRESH_RATE_S)
async def refresh_price():
    try:
        await _refresh_price()
    except Exception as err:
        print(f"ERROR: refreshing price {err}")


# text commands
@client.event
async def on_message(message):
    if message.author == client.user:
        return


client.run(TOKEN)
