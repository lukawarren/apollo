import logging
from typing import Optional

import openai
from discord import AllowedMentions
from discord.ext import commands
from discord.ext.commands import Bot, Context

from cogs.commands.openaiadmin import is_author_banned_openai
from config import CONFIG
from utils.utils import split_into_messages

LONG_HELP_TEXT = """
Too much yapping? Summarise what people have said using the power of the GPT overlords!
"""

SHORT_HELP_TEXT = """Summarise messages."""

mentions = AllowedMentions(everyone=False, users=False, roles=False, replied_user=True)
chat_cmd = CONFIG.PREFIX + "chat"
summarise_cmd = CONFIG.PREFIX + "summarise"


def clean(msg, *prefixes):
    for pre in prefixes:
        msg = msg.strip().removeprefix(pre)
    return msg.strip()


class Summarise(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        openai.api_key = CONFIG.OPENAI_API_KEY
        self.model = "gpt-3.5-turbo"
        self.system_prompt = "People yap too much, I don't want to read all of it. In 200 words or less give me the gist of what is being said. Note that the messages are in reverse chronological order:"

    @commands.hybrid_command(help=LONG_HELP_TEXT, brief=SHORT_HELP_TEXT)
    async def tldr(
        self, ctx: Context, number_of_messages: int = 100, gpt4: bool = False
    ):
        number_of_messages = 400 if number_of_messages > 400 else number_of_messages

        # avoid banned users
        if not await is_author_banned_openai(ctx):
            return

        # get the last "number_of_messages" messages from the current channel and build the prompt
        curr_channel = ctx.guild.get_channel(ctx.channel.id)
        messages = curr_channel.history(limit=number_of_messages)
        messages = await self.create_message(messages)

        # send the prompt to the ai overlords to process
        async with ctx.typing():
            response = await self.dispatch_api(messages, gpt4)
            if response:
                prev = ctx.message
                for content in split_into_messages(response):
                    prev = await prev.reply(content, allowed_mentions=mentions)

    async def dispatch_api(self, messages, gpt4) -> Optional[str]:
        logging.info(f"Making OpenAI request: {messages}")

        # Make request
        model = "gpt-4" if gpt4 else self.model
        response = await openai.ChatCompletion.acreate(model=model, messages=messages)
        logging.info(f"OpenAI Response: {response}")

        # Remove prefix that chatgpt might add
        reply = response.choices[0].message.content
        if CONFIG.AI_INCLUDE_NAMES:
            name = f"{self.bot.user.display_name}: "
            reply = clean(reply, "Apollo: ", "apollo: ", name)
        return reply

    async def create_message(self, message_chain):
        # get initial prompt
        initial = self.system_prompt + "\n"

        # for each message, append it to the prompt as follows --- author : message \n
        async for msg in message_chain:
            if CONFIG.AI_INCLUDE_NAMES and msg.author != self.bot.user:
                initial += msg.author.name + ":" + msg.content + "\n"

        messages = [dict(role="system", content=initial)]

        return messages


async def setup(bot: Bot):
    await bot.add_cog(Summarise(bot))
