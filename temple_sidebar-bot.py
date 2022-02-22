import requests
import discord
from discord.ext import tasks, commands
from discord.ext.commands import Bot
import os
from dotenv import load_dotenv
import math
from loguru import logger


class PriceFetchError(Exception):
    ...


def millify(n):
    millnames = ['', 'K', 'M', 'B', 'T']
    n = float(n)
    millidx = max(0, min(len(millnames)-1,
                         int(math.floor(0 if n == 0 else math.log10(abs(n))/3))))

    return '{:.0f}{}'.format(n / 10**(3 * millidx), millnames[millidx])


def get_data():
    query = """query {                                                                  
      dayProtocolMetrics(first: 2, orderBy: timestamp, orderDirection: desc) {          
        templePrice                                                                     
        ogTemplePrice
        ogTempleSupply
        ogTempleRatio                                                                   
        marketCap                                                                       
        templeCirculatingSupply
        farmEarnings                                                                  
      }                                                                                 
    }"""

    url = "https://api.thegraph.com/subgraphs/name/templedao/templedao-metrics"
    response = requests.post(url, json={'query': query})

    try:
        data = response.json()
    except:
        raise PriceFetchError("Invalid response from API: {response.text}")


    if response.status_code != 200 or 'errors' in data:
        raise PriceFetchError(f"Error fetching price {response.text}")


    metrics = data['data']['dayProtocolMetrics'][0]
    prev_metrics = data['data']['dayProtocolMetrics'][1]

    data_dict = {
        'ogTemplePrice': metrics['ogTemplePrice'][:4],
        'ogTempleSupply': metrics['ogTempleSupply'][:12],
        'ogTempleRatio': metrics['ogTempleRatio'][:4],
        'templePrice': metrics['templePrice'][:4],
        'marketCap': metrics['marketCap'][:12],
        'templeCirculatingSupply': metrics['templeCirculatingSupply'][:12],
        'farmRewards_today': metrics['farmEarnings'][:12],
        'farmRewards_yesterday': prev_metrics['farmEarnings'][:12]
    }

    return data_dict


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
REFRESH_RATE_S = int(os.getenv('REFRESH_RATE_S', 60))
client = discord.Client()


@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')
    refresh_price.start()


async def _refresh_price():
    print("Refreshing price")
    try:
        data = get_data()
    except Exception as err:
        print(err)
        nickname = 'ERROR'
        activity = 'ERROR'
    else:
        templeprice = data['templePrice']
        ogtprice = data['ogTemplePrice']
        marketcap = millify(float(data['marketCap']))
        ogTempleSupply = float(data['ogTempleSupply'])
        ogTempleRatio = float(data['ogTempleRatio'])
        templeCirculatingSupply = float(data['templeCirculatingSupply'])
        perc_staked = "{0:.0%}".format((ogTempleSupply * ogTempleRatio / templeCirculatingSupply)
        dailyFarmEarnings = millify(float(data['farmRewards_today']))

        nickname = f'T ${templeprice} | OG ${ogtprice}'
        activity = f'Rwrds ${dailyFarmEarnings} | Stkd {perc_staked}'

    print(f"New stats {nickname} || {activity}")
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
