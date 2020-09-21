import contextlib
import json
import logging
import re
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
                "priority_labels": {1: "low", 2: "medium", 3: "high"},
                "priority_default_level": 2,
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

    @commands.group(name="issueset")
    async def issueset(self, ctx):
        pass

    @issueset.command(name="repo")
    async def issueset__repo(self, ctx, repo: Optional[str] = None):
        if repo:
            await self.config.repo.set(repo)
            await ctx.send("Repository has been set to `{repo}`".format(repo=repo))
        else:
            repo = await self.config.repo()
            await ctx.send("Repository is `{repo}`".format(repo=repo))

    @issueset.command(name="bug")
    async def issueset__bug(self, ctx, label: Optional[str] = None):
        if label:
            await self.config.bug_label.set(label)
            await ctx.send("Bug label has been set to `{label}`".format(label=label))
        else:
            label = await self.config.bug_label()
            await ctx.send("Bug label is `{label}`".format(label=label))

    @issueset.command(name="feature")
    async def issueset__feature(self, ctx, label: Optional[str] = None):
        if label:
            await self.config.feature_label.set(label)
            await ctx.send("Feature label has been set to `{label}`".format(label=label))
        else:
            label = await self.config.feature_label()
            await ctx.send("Feature label is `{label}`".format(label=label))

    @issueset.command(name="enhancement")
    async def issueset__enhancement(self, ctx, label: Optional[str] = None):
        if label:
            await self.config.enhancement_label.set(label)
            await ctx.send("Enhancement label has been set to `{label}`".format(label=label))
        else:
            label = await self.config.enhancement_label()
            await ctx.send("Enhancement label is `{label}`".format(label=label))

    @issueset.command(name="priority")
    async def issueset__priority(
        self, ctx, priority: Optional[int] = None, label: Optional[str] = None
    ):
        labels = await self.config.priority_labels()
        if label is not None and priority is not None:
            labels[priority] = label
            await self.config.priority_labels.set(labels)
            await ctx.send(
                "Priority level {level} set\n".format(level=priority)
                + cf.box(json.dumps(labels, indent=2, ensure_ascii=False), "json")
            )
        else:
            await ctx.send(
                "Priority levels:\n"
                + cf.box(json.dumps(labels, indent=2, ensure_ascii=False), "json")
            )

    @issueset.command(name="default_priority")
    async def issueset__default_priority(self, ctx, level: Optional[int] = None):
        if level:
            await self.config.priority_default_level.set(label)
            await ctx.send("Default Priority Level has been set to `{level}`".format(level=level))
        else:
            level = await self.config.priority_default_level()
            await ctx.send("Default Priority Level is `{level}`".format(level=level))

    @issueset.command(name="token")
    async def issueset__token(self, ctx, access_token: Optional[str] = None):
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
                repo = self.github.get_repo(__repo)
            except github.GithubException:
                await ctx.send(
                    "Repo cannot be found, please check your config with `[p]issueset repo`"
                )
                return
            __issue = issue
            try:
                issue = repo.get_issue(number=__issue)
            except github.GithubException:
                await ctx.send("Issue or Pull Request not found.")
                return
            embed = await self.create_issue_embed(repo, issue)
            await ctx.send(embed=embed)

    @commands.Cog.listener("on_message_without_command")
    async def find_issue_from_message(self, message: discord.Message) -> None:
        """If the repo name is posted with what looks like an issue number on the end, find issue.

        Fails silently
        """
        if not (await self.bot.message_eligible_as_command(message)):
            return

        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return

        __repo = await self.config.repo()
        if __repo:
            pattern = r"{repo}#(\d*)".format(repo=__repo.split("/")[1])
        else:
            return

        search = re.search(pattern, message.content, re.IGNORECASE)
        if search:
            __issue = int(search[1])
        else:
            return

        async with message.channel.typing():
            try:
                repo = self.github.get_repo(__repo)
                issue = repo.get_issue(number=__issue)
            except github.GithubException:
                return
            embed = await self.create_issue_embed(repo, issue)
            await message.channel.send(embed=embed)

    @commands.command(name="bug", rest_is_raw=True)
    async def bug(self, ctx, title: str, *, body: str):
        async with ctx.typing():
            __repo = await self.config.repo()
            try:
                repo = self.github.get_repo(__repo)
            except github.GithubException:
                await ctx.send(
                    "Repo cannot be found, please check your config with `[p]issueset repo`"
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

    @commands.command(name="feature", rest_is_raw=True)
    async def feature(self, ctx, title: str, *, body: str):
        async with ctx.typing():
            __repo = await self.config.repo()
            try:
                repo = self.github.get_repo(__repo)
            except github.GithubException:
                await ctx.send(
                    "Repo cannot be found, please check your config with `[p]issueset repo`"
                )
                return

            __issue = {"title": title}
            __issue["body"] = quote(body)
            __issue["body"] += (
                "\n\nFeature [requested]({message.jump_url})"
                " by *{member}*"
                " on [{guild.name}]({guild.jump_url})"
            ).format(message=ctx.message, member=ctx.author, guild=ctx.guild)

            __label = await self.config.bug_label()
            with contextlib.suppress(github.GithubException):
                label = repo.get_label(__label)
                __issue["labels"] = [label]

            issue = repo.create_issue(**__issue)
            embed = await self.create_issue_embed(repo, issue)
            await ctx.send(content="Feature request created", embed=embed)

    @commands.command(name="enhancement", rest_is_raw=True)
    async def enhancement(self, ctx, title: str, *, body: str):
        async with ctx.typing():
            __repo = await self.config.repo()
            try:
                repo = self.github.get_repo(__repo)
            except github.GithubException:
                await ctx.send(
                    "Repo cannot be found, please check your config with `[p]issueset repo`"
                )
                return

            __issue = {"title": title}
            __issue["body"] = quote(body)
            __issue["body"] += (
                "\n\nEnhancement [suggested]({message.jump_url})"
                " by *{member}*"
                " on [{guild.name}]({guild.jump_url})"
            ).format(message=ctx.message, member=ctx.author, guild=ctx.guild)

            __label = await self.config.bug_label()
            with contextlib.suppress(github.GithubException):
                label = repo.get_label(__label)
                __issue["labels"] = [label]

            issue = repo.create_issue(**__issue)
            embed = await self.create_issue_embed(repo, issue)
            await ctx.send(content="Enhancement suggestion created", embed=embed)