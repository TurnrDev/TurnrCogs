from .issues import GitHub

__version__ = "1.0.1"
__author__ = "TurnrDev"
__red_end_user_data_statement__ = "This cog does not persistently store data about users."


def setup(bot):
    bot.add_cog(GitHub(bot))
