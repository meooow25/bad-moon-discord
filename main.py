import asyncio
import logging
import os
import tarfile
import time
from os import environ
from typing import Literal

import discord
from discord import app_commands
from PIL import Image
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bits_to_moon = {
    (0,0,0,0): "🌑",
    (0,0,0,1): "🌒",
    (0,0,1,0): "🌒",
    (0,0,1,1): "🌓",
    (0,1,0,0): "🌘",
    (0,1,0,1): "🌓",
    (0,1,1,0): "🌕",
    (0,1,1,1): "🌔",
    (1,0,0,0): "🌘",
    (1,0,0,1): "🌑",
    (1,0,1,0): "🌗",
    (1,0,1,1): "🌓",
    (1,1,0,0): "🌗",
    (1,1,0,1): "🌗",
    (1,1,1,0): "🌖",
    (1,1,1,1): "🌕",
}

def frame_to_moon(im):
    w, h = im.size
    assert w % 4 == 0
    r = []
    for y in range(h):
        for x in range(0, w, 4):
            s = tuple(int(im.getpixel((x+d, y)) > 0) for d in range(4))
            r.append(bits_to_moon[s])
        r.append('\n')
    return ''.join(r)

def load_frames(tarf):
    with tarfile.open(tarf) as tf:
        names = tf.getnames()
        assert all(name.endswith('.bmp') for name in names)
        names.sort()
        frames = []
        for name in tqdm(names):
            with tf.extractfile(name) as f:
                im = Image.open(f)
                frames.append(frame_to_moon(im))
        return frames

SMALL_FRAMES = load_frames('frames_16_12.tar')
logger.info('Loaded small')

BIG_FRAMES = load_frames('frames_48_36.tar')
logger.info('Loaded big')

# Best steady frame rate I can get without being rate-limited by Discord
SEC_PER_FRAME = 6

# Try again in case there is an error sending a frame
NUM_TRIES = 3
TRY_WAIT_SEC = 1

class Bot:
    def __init__(self, token):
        self.token = token
        self.client = discord.Client(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(
            self.client,
            allowed_contexts=app_commands.AppCommandContext(guild=True)
        )

        # allow only one playback per guild
        self.active_guilds = {}

        @self.tree.command(name='stop')
        async def stop(interaction: discord.Interaction):
            if self.active_guilds.get(interaction.guild_id, False):
                logger.info('Stopping')
                self.active_guilds[interaction.guild_id] = False
                await interaction.response.send_message('Stopped')
            else:
                await interaction.response.send_message('Not running!', delete_after=30)

        @self.tree.command(name='badapple', description='Bad Apple!!')
        async def bad_apple(interaction: discord.Interaction, size: Literal['small','big']):
            if interaction.guild_id in self.active_guilds:
                await interaction.response.send_message('Already running!', delete_after=30)
                return

            if size == 'small':
                total_frames = len(SMALL_FRAMES)
                def get_frame(i):
                    return SMALL_FRAMES[i] + f'-# {i+1}/{total_frames}'
            else:
                total_frames = len(BIG_FRAMES)
                # discord seems to have a cap of ~199 emojis per message, more
                # than that and they are present in the message but not shown.
                # this issue is bypassed by using a code block.
                def get_frame(i):
                    return '```\n' + BIG_FRAMES[i] + '```\n' + f'-# {i+1}/{total_frames}'

            message = None
            last_send_time = None

            async def send_frame(i):
                nonlocal last_send_time
                content = get_frame(i)
                last_send_time = time.time()
                logger.info(f'Frame {i+1} at {int(last_send_time) % 100000}')
                # bypass the interaction method and its 15 minute time limit
                await super(discord.InteractionMessage, message).edit(content=content)

            async def try_send_frame(i):
                wait = last_send_time + SEC_PER_FRAME - time.time()
                if wait > 0.2:
                    await asyncio.sleep(wait)

                for j in range(NUM_TRIES):
                    if not self.active_guilds[interaction.guild_id]:
                        break
                    if j == NUM_TRIES - 1:
                        await send_frame(i)
                        break
                    try:
                        await send_frame(i)
                        break
                    except Exception:
                        logger.exception('!!!')
                        await asyncio.sleep(TRY_WAIT_SEC)

            async def update_task():
                for i in range(1, total_frames):
                    await try_send_frame(i)
                    if not self.active_guilds[interaction.guild_id]:
                        break

                logger.info('Stopped')
                del self.active_guilds[interaction.guild_id]

            # whether to keep running
            self.active_guilds[interaction.guild_id] = True
            content = get_frame(0)
            last_send_time = time.time()
            await interaction.response.send_message(content=content)
            message = await interaction.original_response()

            asyncio.create_task(update_task())

        @self.client.event
        async def on_ready():
            logger.info(f'Logged in as {self.client.user}')
            await self.tree.sync()
            logger.info('Command sync done')

    def run(self):
        self.client.run(self.token)

def main():
    token = environ.get('BOT_TOKEN')
    Bot(token).run()

if __name__ == '__main__':
    main()
