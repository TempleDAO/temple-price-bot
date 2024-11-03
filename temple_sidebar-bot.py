from loguru import logger
import requests
import discord
from discord.ext import tasks
import os
from dotenv import load_dotenv
import math
from web3 import Web3

load_dotenv()


TOKEN = os.getenv("DISCORD_TOKEN")
REFRESH_RATE_S = int(os.getenv("REFRESH_RATE_S", 90))
PROVIDER_URL = os.getenv("MAINNET_PROVIDER_URL")
client = discord.Client()


class PriceFetchError(Exception):
    ...


def millify(n, precision):
    millnames = ["", "K", "M", "B", "T"]
    n = float(n)
    millidx = max(
        0,
        min(
            len(millnames) - 1,
            int(math.floor(0 if n == 0 else math.log10(abs(n)) / 3))
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


def get_tvl():

    query = """query MyQuery {
  treasuryReservesVaults {
    principalUSD
    benchmarkedEquityUSD
  }
}
"""

    url = "https://subgraph.satsuma-prod.com/a912521dd162/templedao/temple-v2-balances/api"

    data = get_json_data(url, query)
    metrics = data["data"]["treasuryReservesVaults"][0]
    tvl = float(metrics["principalUSD"]) + float(metrics["benchmarkedEquityUSD"])
    return tvl


def get_spot_price():
    query = """query {
          metrics {
            spotPrice
          }
    }"""

    url = "https://subgraph.satsuma-prod.com/a912521dd162/templedao/temple-ramos/api"
    data = get_json_data(url, query)

    metrics = data["data"]["metrics"][0]

    return float(metrics["spotPrice"])


@client.event
async def on_ready():
    logger.info(f"{client.user} has connected to Discord!")
    refresh_price.start()


def fetch_tpi():
    address = "0x6008C7D33bC509A6849D6cf3196F38d693d3Ae6A"
    abi = '[{"inputs":[],"name":"treasuryPriceIndex","outputs":[{"internalType":"uint96","name":"","type":"uint96"}],"stateMutability":"view","type":"function"}]'

    w3 = Web3(Web3.HTTPProvider(PROVIDER_URL))
    contract = w3.eth.contract(address, abi=abi)

    tpi = contract.functions.treasuryPriceIndex().call()

    return tpi / 1e18


def compute_price_premium(spot: float, tpi: float) -> float:
    return (spot / tpi) - 1


async def _refresh_price():
    logger.info("Refreshing price")
    try:
        price = get_spot_price()
        tpi = fetch_tpi()
        premium = compute_price_premium(price, tpi)
    except Exception as err:
        logger.exception(f"Error refreshing price {err}")
        nickname = "ERROR"
    else:
        nickname = f"${roundf(price, 3)} | {premium*100:+.0f}% TPI"

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
