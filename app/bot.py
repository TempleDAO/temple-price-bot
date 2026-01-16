#!/usr/bin/env python3
import discord
from loguru import logger

from discord import Client


async def update_bot(client: Client, nickname: str, activity: str):

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
