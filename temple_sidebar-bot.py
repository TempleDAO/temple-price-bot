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
      dayProtocolMetrics(first: 2, orderBy: timestamp, orderDirection: desc) {
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
    prev_metrics = data['data']['dayProtocolMetrics'][1]

    data_dict = {
        'ogTemplePrice': round2d(metrics['ogTemplePrice']),
        'ogTempleSupply': round2d(metrics['ogTempleSupply']),
        'ogTempleRatio': round2d(metrics['ogTempleRatio']),
        'templePrice': round2d(metrics['templePrice']),
        'marketCap': round2d(metrics['marketCap']),
        'templeCirculatingSupply': round2d(metrics['templeCirculatingSupply']),
        'farmRewards_today': round2d(metrics['farmEarnings']),
        'farmRewards_yesterday': round2d(prev_metrics['farmEarnings'])
    }

    return data_dict


def get_vault_data(vault_group, days):
    query = f"""query {{
      dayProtocolMetrics(first: {days}, orderBy: timestamp, orderDirection: desc) {{
          totalFarmEarnings
        }}
    }}"""

    url = "https://api.thegraph.com/subgraphs/name/templedao/templedao-metrics"
    data = get_json_data(url, query)

    first_day_earnings = float(data['data']['dayProtocolMetrics'][-1]['totalFarmEarnings'])
    last_day_earnings = float(data['data']['dayProtocolMetrics'][0]['totalFarmEarnings'])
    daily_avg_ernings = (last_day_earnings - first_day_earnings) / days;

    query = f"""query {{
      vaultGroup(id: "{vault_group}") {{
          tvlUSD
        }}
    }}"""

    url = "https://api.thegraph.com/subgraphs/name/templedao/templedao-core"
    data = get_json_data(url, query)

    tvl = float(data['data']['vaultGroup']['tvlUSD'])
    apr = (daily_avg_ernings / tvl) * 365 * 100;
    apy = ((1 + (apr / 100) / 12) ** 12 - 1) * 100;

    data_dict = {
        'tvl': round2d(tvl),
        'apr': round2d(apr),
        'apy': round2d(apy)
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
        vault_data = get_vault_data(vault_group='1m-core', days=14)
    except Exception as err:
        logger.exception('Error refreshing price')
        nickname = 'ERROR'
        activity = 'ERROR'
    else:
        templeprice = metrics_data['templePrice']
        ogtprice = metrics_data['ogTemplePrice']
        marketcap = millify(metrics_data['marketCap'])
        ogTempleSupply = metrics_data['ogTempleSupply']
        ogTempleRatio = metrics_data['ogTempleRatio']
        templeCirculatingSupply = metrics_data['templeCirculatingSupply']
        perc_staked = '{0:.0%}'.format((ogTempleSupply * ogTempleRatio / templeCirculatingSupply))
        dailyFarmEarnings = millify(metrics_data['farmRewards_today'])
        vault_tvl = millify(vault_data['tvl'])
        vault_apy = vault_data['apy']

        nickname = f'T ${templeprice} | TVL ${vault_tvl}'
        activity = f'Farmed ${dailyFarmEarnings} | APY {vault_apy}%'
    
    logger.info("New stats {nickname} || {activity}", nickname=nickname, activity=activity)

    await client.change_presence(activity=discord.Game(name=activity))
    for guild in client.guilds:
        await guild.me.edit(nick=nickname)

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
