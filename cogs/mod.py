import datetime
import re
import time
from subprocess import call
import discord

from discord.ext import commands
from utils.checks import is_staff, check_staff_id, check_bot_or_staff
from utils.converters import SafeMember, FetchMember
from utils import utils, crud, models


class Mod(commands.Cog):
    """
    Staff commands.
    """

    def __init__(self, bot):
        self.bot = bot

    @is_staff("Owner")
    @commands.command()
    async def quit(self, ctx):
        """Stops the bot."""
        await ctx.send("👋 Bye bye!")
        await self.bot.close()

    @is_staff("SuperOP")
    @commands.command()
    async def pull(self, ctx):
        """Pull new changes from GitHub and restart."""
        if self.bot.IS_DOCKER:
            await ctx.send("Pull isn't used when running from a Docker container!")
            return
        else:
            await ctx.send("Pulling changes...")
            call(['git', 'pull'])
            await ctx.send("👋 Restarting bot!")
            await self.bot.close()

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command(aliases=['ui'])
    async def userinfo(self, ctx, u: FetchMember):
        """Shows information from a user. Staff and Helpers only."""
        basemsg = f"name = {u.name}\nid = {u.id}\ndiscriminator = {u.discriminator}\navatar = {u.avatar}\nbot = {u.bot}\navatar_url = {u.avatar_url_as(static_format='png')}\ndefault_avatar= {u.default_avatar}\ndefault_avatar_url = <{u.default_avatar_url}>\ncreated_at = {u.created_at}\n"
        if isinstance(u, discord.Member):
            role = u.top_role.name
            await ctx.send(f"{basemsg}display_name = {u.display_name}\njoined_at = {u.joined_at}\nstatus ={u.status}\nactivity = {u.activity.name if u.activity else None}\ncolour = {u.colour}\ntop_role = {role}\n")
        else:
            try:
                ban = await ctx.guild.fetch_ban(u)
            except discord.NotFound:  # NotFound is raised if the user isn't banned
                ban = None
            await ctx.send(f"{basemsg}{f'**Banned**, reason: {ban.reason}' if ban is not None else ''}\n")

    @commands.guild_only()
    @commands.command(aliases=['ui2'])
    async def userinfo2(self, ctx, user: FetchMember = None):
        """Shows information from a user. Staff and Helpers only."""

        if user is None:
            user = ctx.author

        if (not await check_staff_id('Helper', ctx.author.id)) and (ctx.author != user or ctx.channel != self.bot.channels['bot-cmds']):
            await ctx.message.delete()
            return await ctx.send(f"{ctx.author.mention} This command can only be used in {self.bot.channels['bot-cmds'].mention} and only on yourself.", delete_after=10)

        embed = discord.Embed(color=utils.gen_color(user.id))
        embed.description = (
            f"**User:** {user.mention}\n"
            f"**User's ID:** {user.id}\n"
            f"**Created on:** {user.created_at}\n"
            f"**Default Profile Picture:** {user.default_avatar}\n"
        )

        if isinstance(user, discord.Member):
            member_type = "member"
            embed.description += (
                f"**Join date:** {user.joined_at}\n"
                f"**Current Status:** {user.status}\n"
                f"**User Activity:**: {user.activity}\n"
                f"**Current Display Name:** {user.display_name}\n"
                f"**Nitro Boost Info:** {user.premium_since}\n"
                f"**Current Top Role:** {user.top_role}\n"
                f"**Color:** {user.color}\n"
            )
        else:
            member_type = "user"
            try:
                ban = await ctx.guild.fetch_ban(user)
                embed.description += f"\n**Banned**, reason: {ban.reason}"
            except discord.NotFound:
                pass

        member_type = member_type if not user.bot else "bot"
        embed.title = f"**Userinfo for {member_type} {user}**"
        embed.set_thumbnail(url=user.avatar_url_as(static_format='png'))
        await ctx.send(embed=embed)

    @is_staff("HalfOP")
    @commands.guild_only()
    @commands.command()
    async def matchuser(self, ctx, *, rgx: str):
        """Match users by regex."""
        author = ctx.author
        msg = "```\nmembers:\n"
        for m in self.bot.guild.members:
            if bool(re.search(rgx, m.name, re.IGNORECASE)):
                msg += f"{m.id} - {m}\n"
        msg += "```"
        await author.send(msg)

    @is_staff("Owner")
    @commands.guild_only()
    @commands.command()
    async def multiban(self, ctx, users: commands.Greedy[int]):
        """Multi-ban users."""
        author = ctx.author
        msg = "```\nfailed:\n"
        for m in users:
            try:
                await self.bot.guild.ban(discord.Object(id=m))
            except (discord.errors.NotFound, discord.errors.Forbidden) as e:
                msg += f"{m}:\n  {e.text}\n"
                pass
        msg += "```"
        await utils.send_dm_message(author, msg)

    @is_staff("Owner")
    @commands.guild_only()
    @commands.bot_has_permissions(ban_members=True)
    @commands.command()
    async def multibanre(self, ctx, *, rgx: str):
        """Multi-ban users by regex."""
        author = ctx.author
        msg = "```\nbanned:\n"
        toban = []  # because "dictionary changed size during iteration"
        for m in self.bot.guild.members:
            if bool(re.search(rgx, m.name, re.IGNORECASE)):
                msg += f"{m.id} - {m}\n"
                toban.append(m)
        for m in toban:
            try:
                await m.ban()
            except discord.errors.NotFound:
                pass
        msg += "```"
        await utils.send_dm_message(author, msg)

    @is_staff("Helper")
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    @commands.command()
    async def slowmode(self, ctx, time, channel: discord.TextChannel = None):
        """Apply a given slowmode time to a channel.

        The time format is identical to that used for timed kicks/bans/takehelps.
        It is not possible to set a slowmode longer than 6 hours.

        Helpers in assistance channels and Staff only."""
        if not channel:
            channel = ctx.channel

        if channel not in self.bot.assistance_channels and not await check_staff_id("OP", ctx.author.id):
            return await ctx.send("You cannot use this command outside of assistance channels.")

        if (seconds := utils.parse_time(time)) == -1:
            return await ctx.send("💢 I don't understand your time format.")

        if seconds > 21600:
            return await ctx.send("💢 You can't slowmode a channel for longer than 6 hours!")
        try:
            await channel.edit(slowmode_delay=seconds)
            await ctx.send(f"Slowmode delay for {channel.mention} is now {time} ({seconds}).")
        except discord.errors.Forbidden:
            return await ctx.send("💢 I don't have permission to do this.")
        msg = f"🕙 **Slowmode**: {ctx.author.mention} set a slowmode delay of {time} ({seconds}) in {channel.mention}"
        await self.bot.channels["mod-logs"].send(msg)

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command(aliases=["clear"])
    async def purge(self, ctx, limit: int):
        """Clears a given number of messages. Helpers in assistance channels and Staff only."""
        if ctx.channel not in self.bot.assistance_channels and not await check_staff_id("OP", ctx.author.id):
            return await ctx.send("You cannot use this command outside of assistance channels.")
        await ctx.channel.purge(limit=limit + 1, check=lambda message: not message.pinned)
        msg = f"🗑 **Cleared**: {ctx.author.mention} cleared {limit} messages in {ctx.channel.mention}"
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("HalfOP")
    @commands.guild_only()
    @commands.command()
    async def metamute(self, ctx, member: SafeMember, *, reason=""):
        """Mutes a user so they can't speak in meta. Staff only."""
        if not await crud.add_permanent_role(member.id, self.bot.roles['meta-mute'].id):
            await ctx.send("User is already meta muted!")
            return
        await member.add_roles(self.bot.roles['meta-mute'])
        msg_user = "You were meta muted!"
        if reason != "":
            msg_user += " The given reason is: " + reason
        await utils.send_dm_message(member, msg_user, ctx)
        await ctx.send(f"{member.mention} can no longer speak in meta.")
        msg = f"🔇 **Meta muted**: {ctx.author.mention} meta muted {member.mention} | {self.bot.escape_text(member)}"
        signature = utils.command_signature(ctx.command)
        if reason != "":
            msg += "\n✏️ __Reason__: " + reason
        else:
            msg += f"\nPlease add an explanation below. In the future, it is recommended to use `{signature}` as the reason is automatically sent to the user."
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("HalfOP")
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.command()
    async def metaunmute(self, ctx, member: SafeMember):
        """Unmutes a user so they can speak in meta. Staff only."""
        try:
            if not await crud.remove_permanent_role(member.id, self.bot.roles["meta-mute"].id) and self.bot.roles['meta-mute'] not in member.roles:
                return await ctx.send("This user is not meta muted!")
            await member.remove_roles(self.bot.roles['meta-mute'])
            await ctx.send(f"{member.mention} can now speak in meta again.")
            msg = f"🔈 **Meta unmuted**: {ctx.author.mention} meta unmuted {member.mention} | {self.bot.escape_text(member)}"
            await self.bot.channels['mod-logs'].send(msg)
        except discord.errors.Forbidden:
            await ctx.send("💢 I don't have permission to do this.")

    @is_staff("HalfOP")
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.command()
    async def mute(self, ctx, member: SafeMember, *, reason=""):
        """Mutes a user so they can't speak. Staff only."""
        if await check_bot_or_staff(ctx, member, "mute"):
            return
        if not await crud.add_permanent_role(member.id, self.bot.roles['Muted'].id):
            # Check if the user has a timed restriction.
            # If there is one, this will convert it to a permanent one.
            # If not, it will display that it was already taken.
            if not await crud.get_time_restrictions_by_user_type(member.id, 'timemute'):
                return await ctx.send("User is already muted!")
            else:
                await crud.remove_timed_restriction(member.id, 'timemute')
        await member.add_roles(self.bot.roles['Muted'])
        await member.remove_roles(self.bot.roles['#elsewhere'], self.bot.roles['#art-discussion'])
        msg_user = "You were muted!"
        if reason != "":
            msg_user += " The given reason is: " + reason
        await utils.send_dm_message(member, msg_user, ctx)
        await ctx.send(f"{member.mention} can no longer speak.")
        msg = f"🔇 **Muted**: {ctx.author.mention} muted {member.mention} | {self.bot.escape_text(member)}"
        if reason != "":
            msg += "\n✏️ __Reason__: " + reason
        else:
            signature = utils.command_signature(ctx.command)
            msg += f"\nPlease add an explanation below. In the future, it is recommended to use `{signature}` as the reason is automatically sent to the user."
        await self.bot.channels['mod-logs'].send(msg)
        # change to permanent mute

    @is_staff("HalfOP")
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    @commands.command()
    async def timemute(self, ctx, member: SafeMember, length, *, reason=""):
        """Mutes a user for a limited period of time so they can't speak. Staff only.\n\nLength format: #d#h#m#s"""
        if await check_bot_or_staff(ctx, member, "mute"):
            return
        await member.add_roles(self.bot.roles['Muted'])
        await member.remove_roles(self.bot.roles['#elsewhere'], self.bot.roles['#art-discussion'])

        issuer = ctx.author

        if (seconds := utils.parse_time(length)) == -1:
            return await ctx.send("💢 I don't understand your time format.")

        timestamp = datetime.datetime.now()
        delta = datetime.timedelta(seconds=seconds)
        unmute_time = timestamp + delta
        unmute_time_string = unmute_time.strftime("%Y-%m-%d %H:%M:%S")

        old_timestamp = await crud.add_timed_restriction(member.id, unmute_time, 'timemute')
        await crud.add_permanent_role(member.id, self.bot.roles['Muted'].id)
        msg_user = "You were muted!"
        if reason != "":
            msg_user += " The given reason is: " + reason
        msg_user += f"\n\nThis mute expires {unmute_time_string} {time.tzname[0]}."
        await utils.send_dm_message(member, msg_user, ctx)
        signature = utils.command_signature(ctx.command)
        if not old_timestamp:
            await ctx.send(f"{member.mention} can no longer speak.")
            msg = f"🔇 **Timed mute**: {issuer.mention} muted {member.mention}| {self.bot.escape_text(member)} for {delta}, until {unmute_time_string} "
        else:
            await ctx.send(f"{member.mention} mute was updated.")
            msg = f"🔇 **Timed mute**: {issuer.mention} updated {member.mention}| {self.bot.escape_text(member)} time mute from {old_timestamp} until {unmute_time_string}"
        if reason != "":
            msg += "\n✏️ __Reason__: " + reason
        else:
            msg += f"\nPlease add an explanation below. In the future, it is recommended to use `{signature}` as the reason is automatically sent to the user."
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("HalfOP")
    @commands.guild_only()
    @commands.command()
    async def unmute(self, ctx, member: SafeMember):
        """Unmutes a user so they can speak. Staff only."""
        try:
            if not await crud.remove_permanent_role(member.id, self.bot.roles["Muted"].id):
                return await ctx.send("This user is not muted")
            await member.remove_roles(self.bot.roles['Muted'])
            await ctx.send(f"{member.mention} can now speak again.")
            msg = f"🔈 **Unmuted**: {ctx.author.mention} unmuted {member.mention} | {self.bot.escape_text(member)}"
            await self.bot.channels['mod-logs'].send(msg)
            await crud.remove_timed_restriction(member.id, 'timemute')
        except discord.errors.Forbidden:
            await ctx.send("💢 I don't have permission to do this.")

    @is_staff("HalfOP")
    @commands.command()
    async def art(self, ctx, member: SafeMember):
        """Restore art-discussion access for a user. Staff only."""
        if not await crud.remove_permanent_role(member.id, self.bot.roles['No-art'].id):
            return await ctx.send("This user is not restricted from art channels.")
        try:
            await member.remove_roles(self.bot.roles['No-art'])
        except discord.Forbidden:
            await ctx.send("💢 I don't have permission to do this.")
        await ctx.send(f"{member.mention} can access art-discussion again.")
        msg = f"⭕️ **Restored art**: {ctx.message.author.mention} restored art access to {member.mention} | {self.bot.escape_text(member)}"
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("HalfOP")
    @commands.command()
    async def noart(self, ctx, member: SafeMember, *, reason=""):
        """Removes art-discussion access from a user. Staff only."""
        if not await crud.add_permanent_role(member.id, self.bot.roles['No-art'].id):
            return await ctx.send("This user is already restricted from art channels.")
        try:
            await member.add_roles(self.bot.roles['No-art'])
        except discord.Forbidden:
            await ctx.send("💢 I don't have permission to do this.")
        await ctx.send(f"{member.mention} can no longer access art-discussion.")
        msg = f"🚫 **Removed art**: {ctx.message.author.mention} removed art access from {member.mention} | {self.bot.escape_text(member)}"
        signature = utils.command_signature(ctx.command)
        if reason != "":
            msg += "\n✏️ __Reason__: " + reason
        else:
            msg += f"\nPlease add an explanation below. In the future, it is recommended to use `{signature}` as the reason is automatically sent to the user."
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("HalfOP")
    @commands.guild_only()
    @commands.command()
    async def elsewhere(self, ctx, member: SafeMember):
        """Restore elsewhere access for a user. Staff only."""
        try:
            if not await crud.remove_permanent_role(member.id, self.bot.roles["No-elsewhere"].id):
                return await ctx.send("This user is not restricted from elsewhere!")
            await member.remove_roles(self.bot.roles['No-elsewhere'])
            await ctx.send(f"{member.mention} can access elsewhere again.")
            msg = f"⭕️ **Restored elsewhere**: {ctx.author.mention} restored elsewhere access to {member.mention} | {self.bot.escape_text(member)}"
            await self.bot.channels['mod-logs'].send(msg)
        except discord.errors.Forbidden:
            await ctx.send("💢 I don't have permission to do this.")

    @is_staff("HalfOP")
    @commands.guild_only()
    @commands.command()
    async def noelsewhere(self, ctx, member: SafeMember, *, reason=""):
        """Removes elsewhere access from a user. Staff only."""
        try:
            if not await crud.add_permanent_role(member.id, self.bot.roles['No-elsewhere'].id):
                return await ctx.send("This user is already restricted from elsewhere!")
            await member.add_roles(self.bot.roles['No-elsewhere'])
            await member.remove_roles(self.bot.roles['#elsewhere'])
            await ctx.send(f"{member.mention} can no longer access elsewhere.")
            msg = f"🚫 **Removed elsewhere**: {ctx.author.mention} removed elsewhere access from {member.mention} | {self.bot.escape_text(member)}"
            signature = utils.command_signature(ctx.command)
            if reason != "":
                msg += "\n✏️ __Reason__: " + reason
            else:
                msg += f"\nPlease add an explanation below. In the future, it is recommended to use `{signature}` as the reason is automatically sent to the user."
            await self.bot.channels['mod-logs'].send(msg)
        except discord.errors.Forbidden:
            await ctx.send("💢 I don't have permission to do this.")

    @is_staff("HalfOP")
    @commands.guild_only()
    @commands.command()
    async def noembed(self, ctx, member: SafeMember, *, reason=""):
        """Removes embed permissions from a user. Staff only."""
        if await check_bot_or_staff(ctx, member, "noembed"):
            return
        try:
            await crud.add_permanent_role(member.id, self.bot.roles['No-Embed'].id)
            await member.add_roles(self.bot.roles['No-Embed'])
            msg_user = "You lost embed and upload permissions!"
            if reason != "":
                msg_user += " The given reason is: " + reason
            msg_user += "\n\nIf you feel this was unjustified, you may appeal in <#270890866820775946>."
            await utils.send_dm_message(member, msg_user, ctx)
            await ctx.send(f"{member.mention} can no longer embed links or attach files.")
            msg = f"🚫 **Removed Embed**: {ctx.author.mention} removed embed from {member.mention} | {self.bot.escape_text(member)}"
            signature = utils.command_signature(ctx.command)
            if reason != "":
                msg += "\n✏️ __Reason__: " + reason
            else:
                msg += f"\nPlease add an explanation below. In the future, it is recommended to use `{signature}` as the reason is automatically sent to the user."
            await self.bot.channels['mod-logs'].send(msg)
        except discord.errors.Forbidden:
            await ctx.send("💢 I don't have permission to do this.")

    @is_staff("HalfOP")
    @commands.guild_only()
    @commands.command()
    async def embed(self, ctx, member: SafeMember):
        """Restore embed permissions for a user. Staff only."""
        try:
            await crud.remove_permanent_role(member.id, self.bot.roles["No-Embed"].id)
            await member.remove_roles(self.bot.roles['No-Embed'])
            await ctx.send(f"{member.mention} can now embed links and attach files again.")
            msg = f"⭕️ **Restored Embed**: {ctx.author.mention} restored embed to {member.mention} | {self.bot.escape_text(member)}"
            await self.bot.channels['mod-logs'].send(msg)
        except discord.errors.Forbidden:
            await ctx.send("💢 I don't have permission to do this.")

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command(aliases=["nohelp", "yesnthelp"])
    async def takehelp(self, ctx, member: FetchMember, *, reason=""):
        """Remove access to the assistance channels. Staff and Helpers only."""
        if await check_bot_or_staff(ctx, member, "takehelp"):
            return
        if not await crud.add_permanent_role(member.id, self.bot.roles['No-Help'].id):
            # Check if the user has a timed restriction.
            # If there is one, this will convert it to a permanent one.
            # If not, it will display that it was already taken.
            if not await crud.get_time_restrictions_by_user_type(member.id, 'timenohelp'):
                return await ctx.send("This user's help is already taken!")
            else:
                await crud.remove_timed_restriction(member.id, 'timenohelp')
        msg_user = "You lost access to help channels!"
        if isinstance(member, discord.Member):
            await member.add_roles(self.bot.roles['No-Help'])
            if reason != "":
                msg_user += " The given reason is: " + reason
            msg_user += "\n\nIf you feel this was unjustified, you may appeal in <#270890866820775946>."
            await utils.send_dm_message(member, msg_user, ctx)
        await ctx.send(f"{member.mention} can no longer access the help channels.")
        msg = f"🚫 **Help access removed**: {ctx.author.mention} removed access to help channels from {member.mention} | {self.bot.escape_text(member)}"
        signature = utils.command_signature(ctx.command)
        if reason != "":
            msg += "\n✏️ __Reason__: " + reason
        else:
            msg += f"\nPlease add an explanation below. In the future, it is recommended to use `{signature}` as the reason is automatically sent to the user."
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command(aliases=["yeshelp"])
    async def givehelp(self, ctx, member: FetchMember):
        """Restore access to the assistance channels. Staff and Helpers only."""
        if not await crud.remove_permanent_role(member.id, self.bot.roles["No-Help"].id):
            return await ctx.send("This user is not take-helped!")
        if isinstance(member, discord.Member):
            try:
                await member.remove_roles(self.bot.roles['No-Help'])
            except discord.errors.Forbidden:
                await ctx.send("💢 I don't have permission to do this.")
        await ctx.send(f"{member.mention} can access the help channels again.")
        msg = f"⭕️ **Help access restored**: {ctx.author.mention} restored access to help channels to {member.mention} | {self.bot.escape_text(member)}"
        await self.bot.channels['mod-logs'].send(msg)
        await crud.remove_timed_restriction(member.id, 'timenohelp')

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command(aliases=["timenohelp"])
    async def timetakehelp(self, ctx, member: SafeMember, length, *, reason=""):
        """Restricts a user from Assistance Channels for a limited period of time. Staff and Helpers only.\n\nLength format: #d#h#m#s"""
        if await check_bot_or_staff(ctx, member, "takehelp"):
            return
        issuer = ctx.author

        if (seconds := utils.parse_time(length)) == -1:
            return await ctx.send("💢 I don't understand your time format.")

        delta = datetime.timedelta(seconds=seconds)
        timestamp = datetime.datetime.now()

        unnohelp_time = timestamp + delta
        unnohelp_time_string = unnohelp_time.strftime("%Y-%m-%d %H:%M:%S")

        await crud.add_timed_restriction(member.id, unnohelp_time, 'timenohelp')
        await crud.add_permanent_role(member.id, self.bot.roles['No-Help'].id)
        await member.add_roles(self.bot.roles['No-Help'])
        msg_user = "You lost access to help channels temporarily!"
        if reason != "":
            msg_user += " The given reason is: " + reason
        msg_user += "\n\nIf you feel this was unjustified, you may appeal in <#270890866820775946>."
        msg_user += f"\n\nThis restriction expires {unnohelp_time_string} {time.tzname[0]}."
        await utils.send_dm_message(member, msg_user, ctx)
        await ctx.send(f"{member.mention} can no longer speak in Assistance Channels.")
        signature = utils.command_signature(ctx.command)
        msg = f"🚫 **Timed No-Help**: {issuer.mention} restricted {member.mention} for {delta}, until {unnohelp_time_string} | {self.bot.escape_text(member)}"
        if reason != "":
            msg += "\n✏️ __Reason__: " + reason
        else:
            msg += f"\nPlease add an explanation below. In the future, it is recommended to use `{signature}` as the reason is automatically sent to the user."
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command(aliases=["notech", "technt"])
    async def taketech(self, ctx, member: FetchMember, *, reason=""):
        """Remove access to the tech channel. Staff and Helpers only."""
        if await check_bot_or_staff(ctx, member, "taketech"):
            return
        if not await crud.add_permanent_role(member.id, self.bot.roles['No-Tech'].id):
            # Check if the user has a timed restriction.
            # If there is one, this will convert it to a permanent one.
            # If not, it will display that it was already taken.
            if not await crud.get_time_restrictions_by_user_type(member.id, 'timenotech'):
                return await ctx.send("This user's tech is already taken!")
            else:
                await crud.remove_timed_restriction(member.id, 'timenotech')
        msg_user = "You lost access to the tech channel!"
        if isinstance(member, discord.Member):
            await member.add_roles(self.bot.roles['No-Tech'])
            if reason != "":
                msg_user += " The given reason is: " + reason
            msg_user += "\n\nIf you feel this was unjustified, you may appeal in <#270890866820775946>."
            await utils.send_dm_message(member, msg_user, ctx)
        await ctx.send(f"{member.mention} can no longer access the tech channel.")
        msg = f"🚫 **Help access removed**: {ctx.author.mention} removed access to tech channel from {member.mention} | {self.bot.escape_text(member)}"
        signature = utils.command_signature(ctx.command)
        if reason != "":
            msg += "\n✏️ __Reason__: " + reason
        else:
            msg += f"\nPlease add an explanation below. In the future, it is recommended to use `{signature}` as the reason is automatically sent to the user."
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command(aliases=["yestech"])
    async def givetech(self, ctx, member: FetchMember):
        """Restore access to the tech channel. Staff and Helpers only."""
        if not await crud.remove_permanent_role(member.id, self.bot.roles["No-Tech"].id):
            return await ctx.send("This user is not take-helped!")
        if isinstance(member, discord.Member):
            try:
                await member.remove_roles(self.bot.roles['No-Tech'])
            except discord.errors.Forbidden:
                await ctx.send("💢 I don't have permission to do this.")
        await ctx.send(f"{member.mention} can access the tech channel again.")
        msg = f"⭕️ **Help access restored**: {ctx.author.mention} restored access to tech channel to {member.mention} | {self.bot.escape_text(member)}"
        await self.bot.channels['mod-logs'].send(msg)
        await crud.remove_timed_restriction(member.id, 'timenotech')

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command(aliases=["timenotech"])
    async def timetaketech(self, ctx, member: SafeMember, length, *, reason=""):
        """Restricts a user from the tech channel for a limited period of time. Staff and Helpers only.\n\nLength format: #d#h#m#s"""
        if await check_bot_or_staff(ctx, member, "taketech"):
            return
        issuer = ctx.author

        if (seconds := utils.parse_time(length)) == -1:
            return await ctx.send("💢 I don't understand your time format.")

        delta = datetime.timedelta(seconds=seconds)
        timestamp = datetime.datetime.now()

        unnotech_time = timestamp + delta
        unnotech_time_string = unnotech_time.strftime("%Y-%m-%d %H:%M:%S")

        await crud.add_timed_restriction(member.id, unnotech_time, 'timenotech')
        await crud.add_permanent_role(member.id, self.bot.roles['No-Tech'].id)
        await member.add_roles(self.bot.roles['No-Tech'])
        msg_user = "You lost access to the tech channel temporarily!"
        if reason != "":
            msg_user += " The given reason is: " + reason
        msg_user += "\n\nIf you feel this was unjustified, you may appeal in <#270890866820775946>."
        msg_user += f"\n\nThis restriction expires {unnotech_time_string} {time.tzname[0]}."
        await utils.send_dm_message(member, msg_user, ctx)
        await ctx.send(f"{member.mention} can no longer speak in the tech channel.")
        signature = utils.command_signature(ctx.command)
        msg = f"🚫 **Timed No-Tech**: {issuer.mention} restricted {member.mention} for {delta}, until {unnotech_time_string} | {self.bot.escape_text(member)}"
        if reason != "":
            msg += "\n✏️ __Reason__: " + reason
        else:
            msg += f"\nPlease add an explanation below. In the future, it is recommended to use `{signature}` as the reason is automatically sent to the user."
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command(aliases=["mutehelp"])
    async def helpmute(self, ctx, member: FetchMember, *, reason=""):
        """Remove speak perms to the assistance channels. Staff and Helpers only."""
        if await check_bot_or_staff(ctx, member, "helpmute"):
            return
        if not await crud.add_permanent_role(member.id, self.bot.roles['help-mute'].id):
            if not await crud.get_time_restrictions_by_user_type(member.id, 'timehelpmute'):
                return await ctx.send("This user is already helpmuted!")
            else:
                await crud.remove_timed_restriction(member.id, 'timehelpmute')
        msg_user = "You muted in the help channels!"
        if isinstance(member, discord.Member):
            await member.add_roles(self.bot.roles['help-mute'])
            if reason != "":
                msg_user += " The given reason is: " + reason
            msg_user += "\n\nIf you feel this was unjustified, you may appeal in <#270890866820775946>."
            await utils.send_dm_message(member, msg_user, ctx)
        await ctx.send(f"{member.mention} can no longer speak in the help channels.")
        msg = f"🚫 **Help mute**: {ctx.author.mention} removed speak access in help channels from {member.mention} | {self.bot.escape_text(member)}"
        signature = utils.command_signature(ctx.command)
        if reason != "":
            msg += "\n✏️ __Reason__: " + reason
        else:
            msg += f"\nPlease add an explanation below. In the future, it is recommended to use `{signature}` as the reason is automatically sent to the user."
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command(aliases=["timemutehelp"])
    async def timehelpmute(self, ctx, member: SafeMember, length, *, reason=""):
        """Restricts a user from speaking in Assistance Channels for a limited period of time. Staff and Helpers only.\n\nLength format: #d#h#m#s"""
        if await check_bot_or_staff(ctx, member, "helpmute"):
            return
        issuer = ctx.author

        if (seconds := utils.parse_time(length)) == -1:
            return await ctx.send("💢 I don't understand your time format.")

        delta = datetime.timedelta(seconds=seconds)
        timestamp = datetime.datetime.now()

        unhelpmute_time = timestamp + delta
        unhelpmute_time_string = unhelpmute_time.strftime("%Y-%m-%d %H:%M:%S")

        await crud.add_timed_restriction(member.id, unhelpmute_time, 'timehelpmute')
        await crud.add_permanent_role(member.id, self.bot.roles['help-mute'].id)
        await member.add_roles(self.bot.roles['help-mute'])
        msg_user = "You lost send access to help channels temporarily!"
        if reason != "":
            msg_user += " The given reason is: " + reason
        msg_user += "\n\nIf you feel this was unjustified, you may appeal in <#270890866820775946>."
        msg_user += f"\n\nThis restriction expires {unhelpmute_time_string} {time.tzname[0]}."
        await utils.send_dm_message(member, msg_user, ctx)
        await ctx.send(f"{member.mention} can no longer speak in the help channels.")
        signature = utils.command_signature(ctx.command)
        msg = f"🚫 **Timed Help mute**: {issuer.mention} help muted {member.mention} for {delta}, until {unhelpmute_time_string} | {self.bot.escape_text(member)}"
        if reason != "":
            msg += "\n✏️ __Reason__: " + reason
        else:
            msg += f"\nPlease add an explanation below. In the future, it is recommended to use `{signature}` as the reason is automatically sent to the user."
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command()
    async def helpunmute(self, ctx, member: FetchMember):
        """Restores speak access to help channels. Helpers+ only."""
        if not await crud.remove_permanent_role(member.id, self.bot.roles["help-mute"].id):
            return await ctx.send("This user is not help muted!")
        if isinstance(member, discord.Member):
            try:
                await member.remove_roles(self.bot.roles['help-mute'])
            except discord.errors.Forbidden:
                await ctx.send("💢 I don't have permission to do this.")
        await crud.remove_timed_restriction(member.id, 'timehelpmute')
        await ctx.send(f"{member.mention} can now speak in the help channels again.")
        msg = f"⭕ **Help unmuted**: {ctx.author.mention} help unmuted {member.mention} | {self.bot.escape_text(member)}"
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command()
    async def takesmallhelp(self, ctx, members: commands.Greedy[SafeMember]):
        """Remove access to small help channel. Staff and Helpers only."""
        if len(members) < 1:
            await ctx.send("Mention at least one user")
            return
        for member in members:
            await member.remove_roles(self.bot.roles['Small Help'])
        await ctx.send(f"{', '.join([x.mention for x in members])} can no longer access the small help channel.")
        msg = f"⭕️ **Small help access revoked**: {ctx.author.mention} revoked access to small help channel from {', '.join([f'{x.mention} | {x}'for x in members])}"
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command()
    async def givesmallhelp(self, ctx, members: commands.Greedy[SafeMember]):
        """Provide access to small help channel for 1-on-1 help. Staff and Helpers only."""
        if len(members) < 1:
            await ctx.send("Mention at least one user")
            return
        for member in members:
            await member.add_roles(self.bot.roles['Small Help'])
        await ctx.send(f"{', '.join([x.mention for x in members])} can access the small help channel.")
        msg = f"⭕️ **Small help access granted**: {ctx.author.mention} granted access to small help channel to {', '.join([f'{x.mention} | {x}'for x in members])}"
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command()
    async def probate(self, ctx, member: FetchMember, *, reason=""):
        """Probate a user. Staff and Helpers only."""
        if await check_bot_or_staff(ctx, member, "probate"):
            return
        if not await crud.add_permanent_role(member.id, self.bot.roles['Probation'].id):
            return await ctx.send("This user is already probated!")
        if isinstance(member, discord.Member):
            await member.add_roles(self.bot.roles['Probation'])
            msg_user = "You are under probation!"
            if reason != "":
                msg_user += " The given reason is: " + reason
            await utils.send_dm_message(member, msg_user, ctx)
        await ctx.send(f"{member.mention} is now in probation.")
        msg = f"🚫 **Probated**: {ctx.author.mention} probated {member.mention} | {self.bot.escape_text(member)}"
        signature = utils.command_signature(ctx.command)
        if reason != "":
            msg += "\n✏️ __Reason__: " + reason
        else:
            msg += f"\nPlease add an explanation below. In the future, it is recommended to use `{signature}` as the reason is automatically sent to the user."
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command()
    async def unprobate(self, ctx, member: FetchMember):
        """Unprobate a user. Staff and Helpers only."""
        if not await crud.remove_permanent_role(member.id, self.bot.roles["Probation"].id) and self.bot.roles["Probation"] not in member.roles:
            return await ctx.send("This user is not probated!")
        if isinstance(member, discord.Member):
            await member.remove_roles(self.bot.roles['Probation'])
        await ctx.send(f"{member.mention} is out of probation.")
        msg = f"⭕️ **Un-probated**: {ctx.author.mention} un-probated {member.mention} | {self.bot.escape_text(member)}"
        await self.bot.channels['mod-logs'].send(msg)

    @is_staff("Owner")
    @commands.guild_only()
    @commands.command()
    async def updatechannel(self, ctx, name, channel: discord.TextChannel):
        """Changes the id of a channel"""
        if name not in self.bot.channels:
            await ctx.send("Invalid channel name!")
            return
        await models.Channel.update.values(id=channel.id).where(models.Channel.name == name).gino.status
        self.bot.channels[name] = channel
        await ctx.send(f"Changed {name} channel to {channel.mention} | {channel.id}")
        await self.bot.channels['server-logs'].send(f"⚙ **Changed**: {ctx.author.mention} changed {name} channel to {channel.mention} | {channel.id}")

    @is_staff("OP")
    @commands.command()
    async def playing(self, ctx, *, gamename):
        """Sets playing message. Staff only."""
        await self.bot.change_presence(activity=discord.Game(name=gamename))

    @is_staff("OP")
    @commands.command()
    async def status(self, ctx, status):
        """Sets status. Staff only."""
        if status == "online":
            await self.bot.change_presence(status=discord.Status.online)
        elif status == "offline":
            await self.bot.change_presence(status=discord.Status.offline)
        elif status == "idle":
            await self.bot.change_presence(status=discord.Status.idle)
        elif status == "dnd":
            await self.bot.change_presence(status=discord.Status.dnd)
        elif status == "invisible":
            await self.bot.change_presence(status=discord.Status.invisible)

    @is_staff("OP")
    @commands.command()
    async def username(self, ctx, *, username):
        """Sets bot name. Staff only."""
        await self.bot.user.edit(username=username)

    @is_staff("SuperOP")
    @commands.guild_only()
    @commands.command()
    async def nofilter(self, ctx, channel: discord.TextChannel):
        """Adds nofilter to the channel"""
        if await crud.check_nofilter(channel):
            return await ctx.send("This channel is already no filtered!")
        await crud.add_nofilter(channel)
        await self.bot.channels['mod-logs'].send(f"⭕ **No filter**: {ctx.author.mention} added no filter to {channel.mention}")

    @is_staff("SuperOP")
    @commands.guild_only()
    @commands.command()
    async def filter(self, ctx, channel: discord.TextChannel):
        """Removes nofilter from the channel"""
        if not await crud.check_nofilter(channel):
            return await ctx.send("This channel is already filtered!")
        await crud.remove_nofilter(channel)
        await self.bot.channels['mod-logs'].send(f"🚫 **Filter**: {ctx.author.mention} removed no filter from {channel.mention}")

    @is_staff("Helper")
    @commands.guild_only()
    @commands.command()
    async def approve(self, ctx, alias: str, invite: discord.Invite, times: int = 1):
        """Approves a server invite for a number of times. Staff and Helpers only."""

        code = invite.code

        if await self.bot.invitefilter.fetch_invite_by_alias(alias) or await self.bot.invitefilter.fetch_invite_by_code(code):
            return await ctx.send("This code or alias is already in use!")

        if times < 1:
            return await ctx.send("The invite must be approved for a number of times higher than 0")

        await self.bot.invitefilter.add(code=code, alias=alias, uses=times)
        await ctx.send(f"Approved an invite to {invite.guild}({code}) for posting {times} times")
        await self.bot.channels['mod-logs'].send(f"⭕ **Approved**: {ctx.author.mention} approved server {invite.guild}({code}) to be posted {times} times")

    @is_staff("SuperOP")
    @commands.command(aliases=['setrole', 'scr'])
    async def setchannelrole(self, ctx, channel: discord.TextChannel, role: discord.Role):
        """Sets the default role of a channel."""
        dbchannel = await models.Channel.get(channel.id)
        if not dbchannel:
            dbchannel = await crud.add_dbchannel(channel.id, channel.name)
        if not await models.Role.get(role.id):
            await crud.add_dbrole(role.id, role.name)
        await dbchannel.update(default_role=role.id).apply()
        await ctx.send("Parameter updated succesfully")

    @is_staff("Helper")
    @commands.command(aliases=['ci'])
    async def channelinfo(self, ctx, channel: discord.TextChannel = None):
        """Shows database information about a text channel."""
        state = {0: "Not locked", 1: "softlocked", 2: "locked", 3: "super locked"}
        if not channel:
            channel = ctx.channel
        dbchannel = await models.Channel.get(channel.id)
        if not dbchannel:
            return await ctx.send("This channel is not in the database")
        role = await crud.get_dbrole(dbchannel.default_role) if dbchannel.default_role else ctx.guild.default_role
        embed = discord.Embed(title=dbchannel.name)
        embed.add_field(name="ID", value=dbchannel.id, inline=False)
        embed.add_field(name="Default Role", value=role.name, inline=False)
        embed.add_field(name="Filtered", value=str(not dbchannel.nofilter), inline=False)
        embed.add_field(name="Status", value=state[dbchannel.lock_level], inline=False)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Mod(bot))
