import logging
from typing import Optional

import discord
import github
from redbot.core import Config, commands
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger(__name__)


class GitHub(commands.Cog):
    """Create, edit and close your GitHub issues"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=800001066, force_registration=True)
        self.config.register_global(**{"repo": None})
        self.github: github.Github = None
        self.bot.loop.create_task(self.create_client())

    async def create_client(self) -> None:
        api_tokens = await self.bot.get_shared_api_tokens("github")
        access_token = api_tokens.get("access_token")
        if not access_token:
            log.warning("No valid access_token found")
        self.github = github.Github(access_token)

    @commands.group(name="githubset")
    async def githubset(self, ctx):
        pass

    @githubset.command(name="repo")
    async def githubset__repo(self, ctx, repo: Optional[str] = None):
        if repo:
            await self.config.repo.set(repo)
            await ctx.send("Repository has been set to `{repo}`".format(repo=repo))
        else:
            repo = await self.config.repo()
            await ctx.send("Repository is `{repo}`".format(repo=repo))

    @githubset.command(name="token")
    async def githubset__token(self, ctx, access_token: Optional[str] = None):
        """Can be obtained via https://github.com/settings/tokens"""

        def last_four(t: str) -> str:
            return ("*" * len(t[:-4])) + t[-4:]

        if access_token:
            await self.bot.set_shared_api_tokens("github", access_token=last_four(access_token))
            await ctx.send(
                "Access Token has been set to `{access_token}`".format(
                    access_token="*" * len(access_token)
                )
            )
        else:
            api_tokens = await self.bot.get_shared_api_tokens("github")
            token = api_tokens.get("access_token")
            if token:
                await ctx.send("Access Token is `{token}`".format(token=last_four(token)))
            else:
                await ctx.send("Access Token is not set!")

    @commands.command(name="issue")
    async def issue(self, ctx, issue: int):
        """Can be obtained via https://github.com/settings/tokens"""
        async with ctx.typing():
            __repo = await self.config.repo()
            try:
                repo = self.github.get_repo(__repo)
            except github.GithubException.UnknownObjectException:
                await ctx.send(
                    "Repo cannot be found, please check your config with `[p]githubset repo`"
                )
                return
            __issue = issue
            try:
                issue = repo.get_issue(number=__issue)
            except github.GithubException.UnknownObjectException:
                await ctx.send("Issue not found.")
                return
            embed: discord.Embed = discord.Embed(
                title=f"{issue.title} (#{issue.number})",
                description=issue.body,
                url=issue.html_url,
                timestamp=issue.updated_at,
                colour=(
                    discord.Colour.dark_red()
                    if issue.state == "closed"
                    else discord.Colour.green()
                ),
            )
            embed.set_author(
                name=f"{issue.user.login} ({issue.user.name})",
                url=issue.user.html_url,
                icon_url=issue.user.avatar_url,
            )

            if issue.assignees:
                embed.add_field(
                    name="Assignees",
                    value=cf.humanize_list(
                        [f"[@{x.login}]({x.html_url})" for x in issue.assignees]
                    ),
                )

            if issue.labels:
                embed.add_field(
                    name="Labels", value=cf.humanize_list([x.name for x in issue.labels]),
                )

            if issue.milestone:
                embed.add_field(
                    name="Milestone",
                    value=f"[{issue.milestone.title}]({issue.milestone.html_url})",
                )

            if issue.milestone:
                embed.add_field(
                    name="Milestone",
                    value=f"[{issue.milestone.title}]({issue.milestone.html_url})",
                )
            await ctx.send(embed=embed)
