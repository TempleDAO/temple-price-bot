import datetime
from typing import Literal, TypedDict

import discord
from discord.ext import tasks
from eth_typing import ChecksumAddress
from loguru import logger
from web3 import Web3
from web3.contract import Contract

from app.bot import update_bot
from app.utils import roundf


class SpiceAuctionConfig(TypedDict):
    ticker: str
    address: ChecksumAddress
    provider_url: str


class CurrentEpochData(TypedDict):
    price: float
    id: int
    end_date: datetime.datetime
    start_date: datetime.datetime


# Dummy ABI for the getAuctionConfig method
SPICE_AUCTION_ABI = [
    {
        "inputs": [],
        "name": "currentEpoch",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "uint256", "name": "epochId", "type": "uint256"}],
        "name": "getEpochInfo",
        "outputs": [
            {
                "components": [
                    {"internalType": "uint128", "name": "startTime", "type": "uint128"},
                    {"internalType": "uint128", "name": "endTime", "type": "uint128"},
                    {
                        "internalType": "uint256",
                        "name": "totalBidTokenAmount",
                        "type": "uint256",
                    },
                    {
                        "internalType": "uint256",
                        "name": "totalAuctionTokenAmount",
                        "type": "uint256",
                    },
                ],
                "internalType": "struct EpochInfo",
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


def get_current_epoch_data(auction: SpiceAuctionConfig) -> CurrentEpochData:
    w3 = Web3(Web3.HTTPProvider(auction["provider_url"]))
    contract: Contract = w3.eth.contract(
        address=auction["address"], abi=SPICE_AUCTION_ABI
    )

    current_epoch_id: int = contract.functions.currentEpoch().call()

    epoch = contract.functions.getEpochInfo(current_epoch_id).call()
    bid_token_amount = epoch[2]
    auction_token_amount = epoch[3]
    price: float = (
        bid_token_amount / auction_token_amount if auction_token_amount != 0 else 0
    )

    details = CurrentEpochData(
        price=price,
        id=current_epoch_id,
        start_date=datetime.datetime.fromtimestamp(epoch[0]),
        end_date=datetime.datetime.fromtimestamp(epoch[1]),
    )

    return details


async def _update_spice_bot(bot: discord.Client, auction: SpiceAuctionConfig):
    logger.info("Updating spice bot")
    try:
        epoch = get_current_epoch_data(auction)
        nickname = f"{roundf(epoch['price'], 4)} {auction['ticker']}"

        activity = f"Epoch {epoch['id']}"
        now = datetime.datetime.now()
        end_delta_days = (epoch["end_date"] - now).total_seconds() / (24 * 60 * 60)
        start_delta_days = (epoch["start_date"] - now).total_seconds() / (24 * 60 * 60)
        if start_delta_days > 0:
            activity += f" starts in {roundf(start_delta_days, 1)} days"
        else:
            activity += (
                f" ends in {roundf(end_delta_days, 1)} days"
                if end_delta_days > 0
                else f" ended {roundf(abs(end_delta_days), 1)} days ago"
            )
        await update_bot(bot, nickname, activity)

    except Exception as err:
        await update_bot(bot, auction["ticker"], "ERROR")
        print(f"Error refereshing spice auction data {err}")


def create_spice_bot(auction: SpiceAuctionConfig):
    SPICE_BOT = discord.Client()

    @SPICE_BOT.event
    async def on_ready():
        logger.info("Spice bot ready")
        update_spice_info.start()

    @tasks.loop(seconds=5 * 60)
    async def update_spice_info():
        return await _update_spice_bot(SPICE_BOT, auction)

    return SPICE_BOT
