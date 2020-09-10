import contextlib
import logging
from typing import Optional, Union

import discord
import github
from discord.ext.alternatives import jump_url
from redbot.core import Config, commands
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger(__name__)


def quote(t: str) -> str:
    return "> " + t.rstrip("\n").replace("\n", "\n> ")


class GitHub(commands.Cog):
    """Create, edit and close your GitHub issues"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=800001066, force_registration=True)
        self.config.register_global(
            **{
                "repo": None,
                "bug_label": "bug",
                "feature_label": "enhancement",
                "enhancement_label": "enhancement",
            }
        )
        self.github: github.Github = None
        self.bot.loop.create_task(self.create_client())

    async def create_client(self) -> None:
        api_tokens = await self.bot.get_shared_api_tokens("github")
        access_token = api_tokens.get("access_token")
        if not access_token:
            log.warning("No valid access_token found")
        self.github = github.Github(access_token)

    @commands.group(name="ghubset")
    async def ghubset(self, ctx):
        pass

    @ghubset.command(name="repo")
    async def ghubset__repo(self, ctx, repo: Optional[str] = None):
        if repo:
            await self.config.repo.set(repo)
            await ctx.send("Repository has been set to `{repo}`".format(repo=repo))
        else:
            repo = await self.config.repo()
            await ctx.send("Repository is `{repo}`".format(repo=repo))

    @ghubset.group(name="bug")
    async def ghubset__bug(self, ctx):
        pass

    @ghubset__bug.command(name="label")
    async def ghubset__bug__label(self, ctx, label: Optional[str] = None):
        if label:
            await self.config.bug_label.set(label)
            await ctx.send("Bug label has been set to `{label}`".format(label=label))
        else:
            label = await self.config.bug_label()
            await ctx.send("Bug label is `{label}`".format(label=label))

    @ghubset.group(name="feature")
    async def ghubset__feature(self, ctx):
        pass

    @ghubset__feature.command(name="label")
    async def ghubset__feature__label(self, ctx, label: Optional[str] = None):
        if label:
            await self.config.feature_label.set(label)
            await ctx.send("Feature label has been set to `{label}`".format(label=label))
        else:
            label = await self.config.feature_label()
            await ctx.send("Feature label is `{label}`".format(label=label))

    @ghubset.group(name="enhancement")
    async def ghubset__enhancement(self, ctx):
        pass

    @ghubset__enhancement.command(name="label")
    async def ghubset__enhancement__label(self, ctx, label: Optional[str] = None):
        if label:
            await self.config.enhancement_label.set(label)
            await ctx.send("Enhancement label has been set to `{label}`".format(label=label))
        else:
            label = await self.config.enhancement_label()
            await ctx.send("Enhancement label is `{label}`".format(label=label))

    @ghubset.command(name="token")
    async def ghubset__token(self, ctx, access_token: Optional[str] = None):
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

    async def create_issue_embed(
        self,
        repo: github.Repository.Repository,
        issue: Union[github.Issue.Issue, github.PullRequest.PullRequest],
    ) -> discord.Embed:
        if isinstance(issue, github.PullRequest.PullRequest):
            is_pr = True
        elif isinstance(issue, github.Issue.Issue) and issue.pull_request:
            is_pr = True
            issue = issue.as_pull_request()
        elif isinstance(issue, github.Issue.Issue):
            is_pr = False
        else:
            raise TypeError

        embed: discord.Embed = discord.Embed(
            title=cf.escape(f"{issue.title} (#{issue.number})", mass_mentions=True),
            description=cf.escape(issue.body, mass_mentions=True),
            url=issue.html_url,
            timestamp=issue.updated_at,
        )
        if is_pr and issue.state == "open" and issue.draft:
            embed.colour = discord.Colour.light_grey()
        elif is_pr and issue.state == "closed" and issue.merged:
            embed.colour = discord.Colour.dark_purple()
        elif issue.state == "closed":
            embed.colour = discord.Colour.dark_red()
        else:
            embed.colour = discord.Colour.green()

        embed.set_author(
            name=cf.escape(f"{issue.user.login} ({issue.user.name})", mass_mentions=True),
            url=issue.user.html_url,
            icon_url=issue.user.avatar_url,
        )
        footer_text = "{issue_type} • {state}".format(
            issue_type="PR" if is_pr else "Issue", state=str(issue.state).title()
        )
        if is_pr:
            footer_text += " • {issue.additions}".format(issue=issue)
        embed.set_footer(text=footer_text)

        if issue.assignees:
            embed.add_field(
                name="Assignees",
                value=cf.escape(
                    cf.humanize_list([f"[@{x.login}]({x.html_url})" for x in issue.assignees]),
                    mass_mentions=True,
                ),
            )

        if issue.labels:
            embed.add_field(
                name="Labels",
                value=cf.escape(
                    cf.humanize_list([x.name for x in issue.labels]), mass_mentions=True
                ),
            )

        if issue.milestone:
            embed.add_field(
                name="Milestone",
                value=cf.escape(issue.milestone.title, mass_mentions=True),
            )
        return embed

    @commands.command(name="issue", aliases=["pr"])
    async def issue(self, ctx, issue: int):
        """Can be obtained via https://github.com/settings/tokens"""
        async with ctx.typing():
            __repo = await self.config.repo()
            try:
                repo: github.Repository = self.github.get_repo(__repo)
            except github.GithubException:
                await ctx.send(
                    "Repo cannot be found, please check your config with `[p]ghubset repo`"
                )
                return
            __issue = issue
            try:
                issue: github.Issue = repo.get_issue(number=__issue)
            except github.GithubException:
                await ctx.send("Issue or Pull Request not found.")
                return
            embed = await self.create_issue_embed(repo, issue)
            await ctx.send(embed=embed)

    @commands.command(name="bug", rest_is_raw=True)
    async def bug(self, ctx, title: str, *, body: str):
        """Can be obtained via https://github.com/settings/tokens"""
        async with ctx.typing():
            __repo = await self.config.repo()
            try:
                repo: github.Repository = self.github.get_repo(__repo)
            except github.GithubException:
                await ctx.send(
                    "Repo cannot be found, please check your config with `[p]ghubset repo`"
                )
                return

            __issue = {"title": title}
            __issue["body"] = quote(body)
            __issue["body"] += (
                "\n\nBug [reported]({message.jump_url})"
                " by *{member}*"
                " on [{guild.name}]({guild.jump_url})"
            ).format(message=ctx.message, member=ctx.author, guild=ctx.guild)

            __label = await self.config.bug_label()
            with contextlib.suppress(github.GithubException):
                label = repo.get_label(__label)
                __issue["labels"] = [label]

            issue = repo.create_issue(**__issue)
            embed = await self.create_issue_embed(repo, issue)
            await ctx.send(content="Bug report created", embed=embed)
