import requests
import discord
from discord.ext import tasks, commands
from discord.ext.commands import Bot
import os
from dotenv import load_dotenv
import math


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
      dayProtocolMetrics(first: 1, orderBy: timestamp, orderDirection: desc) {          
        templePrice                                                                     
        ogTemplePrice                                                                   
        marketCap                                                                       
        riskFreeValue                                                                   
        intrinsicValue                                                                  
      }                                                                                 
    }"""

    url = "https://api.thegraph.com/subgraphs/name/templedao/templedao-balances"
    response = requests.post(url, json={'query': query})

    try:
        data = response.json()
    except:
        raise PriceFetchError("Invalid response from API: {response.text}")


    if response.status_code != 200 or 'errors' in data:
        raise PriceFetchError(f"Error fetching price {response.text}")


    metrics = data['data']['dayProtocolMetrics'][0]

    data_dict = {
        'ogTemplePrice': metrics['ogTemplePrice'][:4],
        'templePrice': metrics['templePrice'][:4],
        'marketCap': metrics['marketCap'][:12],
        'riskFreeValue': metrics['riskFreeValue'][:4]
    }

    return data_dict


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
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
        rfv = data['riskFreeValue']
        nickname = f'T ${templeprice} | RFV ${rfv}'
        activity = f'MktC. ${marketcap} | OG ${ogtprice}'
    print(f"New stats {nickname} || {activity}")
    await client.change_presence(activity=discord.Game(name=activity))
    for guild in client.guilds:
        await guild.me.edit(nick=nickname)

@tasks.loop(seconds=float(60))
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
