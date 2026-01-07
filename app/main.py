import os
import asyncio
from dotenv import load_dotenv
from web3 import Web3
from app.spice import SpiceAuctionConfig, create_spice_bot
from app.temple_price import create_price_bot


load_dotenv()


SPICE_BOT_TOKEN = os.getenv("SPICE_BOT_TOKEN")
TEMPLE_PRICE_BOT_TOKEN = os.getenv("TEMPLE_PRICE_BOT_TOKEN")
MAINNET_RPC_URL = os.getenv("MAINNET_RPC_URL")


async def main():
    tasks = []
    if not MAINNET_RPC_URL:
        raise ValueError("MAINNET_RPC_URL not set")

    if TEMPLE_PRICE_BOT_TOKEN:
        PRICE_BOT = create_price_bot()
        tasks.append(
            PRICE_BOT.start(TEMPLE_PRICE_BOT_TOKEN),
        )

    if SPICE_BOT_TOKEN:
        ENA_SPICE_AUCTION = SpiceAuctionConfig(
            address=Web3.to_checksum_address(
                "0xa68e1a9a93223f812191f35d102a4b2fb16b60f4"
            ),
            ticker="TGLD/$ENA",
            provider_url=MAINNET_RPC_URL,
        )
        SPICE_BOT = create_spice_bot(ENA_SPICE_AUCTION)
        tasks.append(SPICE_BOT.start(SPICE_BOT_TOKEN))

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
