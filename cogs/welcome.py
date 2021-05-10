from datetime import datetime
from pathlib import Path
from random import choice, choices

import yaml
from discord import Member
from discord.ext.commands import Bot, Cog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy_utils import ScalarListException

from config import CONFIG
from models import User, db_session
from utils import get_database_user


class Category:
    """Categories of favourite things."""

    def __init__(self, cat: dict):
        self.name = cat.get("name")
        self.template = cat.get("template", "{}")
        self.values = cat.get("values", [])
        self.weight = cat.get("weight")
        if self.weight is None or self.weight == "LENGTH":
            self.weight = len(self.values)

    def generate(self):
        return self.template.format(choice(self.values))


class Welcome(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        with open(Path("resources") / "welcome_messages.yaml") as f:
            parsed = yaml.full_load(f).get("welcome_messages")
        self.greetings = parsed.get("greetings")
        self.categories = [Category(c) for c in parsed.get("categories")]
        self.category_weights = [c.weight for c in self.categories]
        self.welcome_template = parsed.get("message")

    def generate_welcome_message(self, name):
        intro_channel = self.bot.get_channel(CONFIG.UWCS_INTROS_CHANNEL_ID)
        greeting = choice(self.greetings)
        category = choices(self.categories, self.category_weights)[0]
        thing = category.generate()
        return self.welcome_template.format(
            greetings=greeting, name=name, intros=intro_channel.mention, thing=thing
        )

    @Cog.listener()
    async def on_member_join(self, member: Member):
        # Add the user to our database if they've never joined before
        user = get_database_user(member)
        if not user:
            user = User(user_uid=member.id, username=str(member))
            db_session.add(user)
        else:
            user.last_seen = datetime.utcnow()
        try:
            db_session.commit()
        except (ScalarListException, SQLAlchemyError):
            db_session.rollback()

        #  await member.send(WELCOME_MESSAGE.format(user_id=member.id))

        # Join message
        channel = self.bot.get_channel(CONFIG.UWCS_WELCOME_CHANNEL_ID)
        await channel.send(self.generate_welcome_message(member.display_name))


def setup(bot: Bot):
    bot.add_cog(Welcome(bot))
