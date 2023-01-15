import requests
import discord
from discord.ext import tasks, commands
from discord.ext.commands import Bot
import os
from dotenv import load_dotenv
import math
load_dotenv()
from loguru import logger
import sys


TOKEN = os.getenv('DISCORD_TOKEN')
REFRESH_RATE_S = int(os.getenv('REFRESH_RATE_S', 60))
client = discord.Client()



class PriceFetchError(Exception):
    ...


def millify(n):
    millnames = ['', 'K', 'M', 'B', 'T']
    n = float(n)
    millidx = max(0, min(len(millnames)-1,
                         int(math.floor(0 if n == 0 else math.log10(abs(n))/3))))

    return '{:.0f}{}'.format(n / 10**(3 * millidx), millnames[millidx])


def round2d(n):
    return round(float(n), 2)


def get_json_data(url, query):
    response = requests.post(url, json={'query': query})

    try:
        data = response.json()
    except:
        raise PriceFetchError("Invalid response from API: {response.text}")


    if response.status_code != 200 or 'errors' in data:
        raise PriceFetchError(f"Error fetching price {response.text}")

    return data


def get_metrics_data():
    query = """query {
      dayProtocolMetrics(first: 1, orderBy: timestamp, orderDirection: desc) {
        templePrice
        ogTemplePrice
        ogTempleSupply
        ogTempleRatio
        marketCap
        templeCirculatingSupply
        farmEarnings
        totalFarmEarnings
      }
    }"""

    url = "https://api.thegraph.com/subgraphs/name/templedao/templedao-metrics"
    data = get_json_data(url, query)

    metrics = data['data']['dayProtocolMetrics'][0]

    data_dict = {
        'templePrice': round(float(metrics['templePrice']), 3),
        'marketCap': round2d(metrics['marketCap']),
        'templeCirculatingSupply': round2d(metrics['templeCirculatingSupply']),
    }

    return data_dict


@client.event
async def on_ready():
    logger.info(f'{client.user} has connected to Discord!')
    refresh_price.start()


async def _refresh_price():
    logger.info("Refreshing price")
    try:
        metrics_data = get_metrics_data()
    except Exception as err:
        logger.exception('Error refreshing price')
        nickname = 'ERROR'
    else:
        templeprice = metrics_data['templePrice']

        nickname = f'${templeprice}'
    activity = f'TPI rise'

    logger.info("New stats {nickname} || {activity}", nickname=nickname, activity=activity)

    await client.change_presence(activity=discord.Activity(name=activity, type=discord.ActivityType.watching))
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
