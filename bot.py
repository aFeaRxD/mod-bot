import discord
from discord.ext import commands
import json
import os
import asyncio
from datetime import datetime, timedelta
import re

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='?', intents=intents)

# Data storage (in memory for now)
mod_stats = {}
mod_logs = {}
warnings = {}
temp_roles = {}
role_persist = {}

def save_data():
    """Save all data to files"""
    pass  # Will implement file saving if needed

def load_data():
    """Load data from files"""
    pass  # Will implement file loading if needed

def parse_time(time_str):
    """Parse time string like '1h', '30m', '5s' into seconds"""
    if not time_str:
        return None
    
    match = re.match(r'^(\d+)([smhd])$', time_str.lower())
    if not match:
        return None
    
    value, unit = match.groups()
    value = int(value)
    
    if unit == 's':
        return value
    elif unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600
    elif unit == 'd':
        return value * 86400
    
    return None

def add_mod_action(mod_id, action):
    """Add action to mod stats"""
    if mod_id not in mod_stats:
        mod_stats[mod_id] = {'kicks': 0, 'bans': 0, 'mutes': 0, 'warns': 0, 'other': 0}
    
    if action in mod_stats[mod_id]:
        mod_stats[mod_id][action] += 1
    else:
        mod_stats[mod_id]['other'] += 1

def add_mod_log(user_id, action, mod_id, reason=None, duration=None):
    """Add entry to user's mod log"""
    if user_id not in mod_logs:
        mod_logs[user_id] = []
    
    log_entry = {
        'action': action,
        'mod_id': mod_id,
        'reason': reason or 'No reason provided',
        'timestamp': datetime.now().isoformat(),
        'duration': duration
    }
    
    mod_logs[user_id].append(log_entry)

@bot.event
async def on_ready():
    print(f'{bot.user} is now online!')
    print(f'Loaded in {len(bot.guilds)} servers')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} slash commands')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
    
    # Start background tasks
    bot.loop.create_task(temp_role_handler())

async def temp_role_handler():
    """Handle temporary role removal"""
    while True:
        try:
            current_time = datetime.now()
            expired_roles = []
            
            for key, data in temp_roles.items():
                if current_time >= data['expires']:
                    expired_roles.append(key)
            
            for key in expired_roles:
                try:
                    guild_id, user_id, role_id = map(int, key.split('_'))
                    guild = bot.get_guild(guild_id)
                    if guild:
                        user = guild.get_member(user_id)
                        role = guild.get_role(role_id)
                        if user and role:
                            await user.remove_roles(role, reason="Temporary role expired")
                    del temp_roles[key]
                except Exception as e:
                    print(f"Error removing temp role: {e}")
                    del temp_roles[key]
            
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            print(f"Error in temp role handler: {e}")
            await asyncio.sleep(60)

# MODERATION COMMANDS

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    """Kick a member"""
    try:
        await member.kick(reason=f"Kicked by {ctx.author} | {reason}")
        
        embed = discord.Embed(title="Member Kicked", color=0xff9900)
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        
        await ctx.send(embed=embed)
        
        add_mod_action(ctx.author.id, 'kicks')
        add_mod_log(member.id, 'kick', ctx.author.id, reason)
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to kick this user.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    """Ban a member"""
    try:
        await member.ban(reason=f"Banned by {ctx.author} | {reason}")
        
        embed = discord.Embed(title="Member Banned", color=0xff0000)
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        
        await ctx.send(embed=embed)
        
        add_mod_action(ctx.author.id, 'bans')
        add_mod_log(member.id, 'ban', ctx.author.id, reason)
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to ban this user.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, duration: str = None, *, reason="No reason provided"):
    """Mute a member using Discord timeout"""
    if not duration:
        await ctx.send("❌ Please specify duration (e.g., 10m, 1h, 1d)")
        return
    
    seconds = parse_time(duration)
    if not seconds:
        await ctx.send("❌ Invalid time format. Use: 10s, 5m, 2h, 1d")
        return
    
    if seconds > 2419200:  # 28 days max
        await ctx.send("❌ Maximum timeout duration is 28 days.")
        return
    
    try:
        until = discord.utils.utcnow() + timedelta(seconds=seconds)
        await member.timeout(until, reason=f"Muted by {ctx.author} | {reason}")
        
        embed = discord.Embed(title="Member Muted", color=0xffff00)
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        
        await ctx.send(embed=embed)
        
        add_mod_action(ctx.author.id, 'mutes')
        add_mod_log(member.id, 'mute', ctx.author.id, reason, duration)
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to timeout this user.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member, *, reason="No reason provided"):
    """Unmute a member"""
    try:
        await member.timeout(None, reason=f"Unmuted by {ctx.author} | {reason}")
        
        embed = discord.Embed(title="Member Unmuted", color=0x00ff00)
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        
        await ctx.send(embed=embed)
        add_mod_log(member.id, 'unmute', ctx.author.id, reason)
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to remove timeout from this user.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int, *, reason="No reason provided"):
    """Unban a user by ID"""
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=f"Unbanned by {ctx.author} | {reason}")
        
        embed = discord.Embed(title="User Unbanned", color=0x00ff00)
        embed.add_field(name="User", value=f"{user} ({user.id})", inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=True)
        
        await ctx.send(embed=embed)
        add_mod_log(user.id, 'unban', ctx.author.id, reason)
        
    except discord.NotFound:
        await ctx.send("❌ User not found or not banned.")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to unban users.")
    except Exception as e:
        await ctx.send(f"❌ Error: {e}")

@bot.command()
@commands.has_permissions(kick_members=True)
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    """Warn a member"""
    if member.id not in warnings:
        warnings[member.id] = []
    
    warning = {
        'reason': reason,
        'mod_id': ctx.author.id,
        'timestamp': datetime.now().isoformat()
    }
    
    warnings[member.id].append(warning)
    
    embed = discord.Embed(title="Member Warned", color=0xffa500)
    embed.add_field(name="User", value=f"{member} ({member.id})", inline=False)
    embed.add_field(name="Warning Count", value=len(warnings[member.id]), inline=True)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    
    await ctx.send(embed=embed)
    
    add_mod_action(ctx.author.id, 'warns')
    add_mod_log(member.id, 'warn', ctx.author.id, reason)

@bot.command()
async def warnings(ctx, member: discord.Member = None):
    """Check warnings for a user"""
    if not member:
        member = ctx.author
    
    if member.id not in warnings or not warnings[member.id]:
        await ctx.send(f"{member} has no warnings.")
        return
    
    embed = discord.Embed(title=f"Warnings for {member}", color=0xff6b6b)
    embed.set_thumbnail(url=member.display_avatar.url)
    
    for i, warning in enumerate(warnings[member.id], 1):
        mod = bot.get_user(warning['mod_id'])
        mod_name = mod.name if mod else "Unknown"
        date = datetime.fromisoformat(warning['timestamp']).strftime('%Y-%m-%d %H:%M')
        
        embed.add_field(
            name=f"Warning {i}",
            value=f"**Reason:** {warning['reason']}\n**Moderator:** {mod_name}\n**Date:** {date}",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command()
async def modstats(ctx, member: discord.Member = None):
    """Check moderation statistics"""
    if not member:
        member = ctx.author
    
    if member.id not in mod_stats:
        await ctx.send(f"{member} has no moderation actions recorded.")
        return
    
    stats = mod_stats[member.id]
    total = sum(stats.values())
    
    embed = discord.Embed(title=f"Moderation Stats for {member}", color=0x3498db)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Kicks", value=stats.get('kicks', 0), inline=True)
    embed.add_field(name="Bans", value=stats.get('bans', 0), inline=True)
    embed.add_field(name="Mutes", value=stats.get('mutes', 0), inline=True)
    embed.add_field(name="Warnings", value=stats.get('warns', 0), inline=True)
    embed.add_field(name="Other", value=stats.get('other', 0), inline=True)
    embed.add_field(name="Total Actions", value=total, inline=True)
    
    await ctx.send(embed=embed)

@bot.command()
async def modlogs(ctx, member: discord.Member = None):
    """Check moderation logs for a user"""
    if not member:
        member = ctx.author
    
    if member.id not in mod_logs or not mod_logs[member.id]:
        await ctx.send(f"{member} has no moderation history.")
        return
    
    logs = mod_logs[member.id][-10:]  # Show last 10 entries
    
    embed = discord.Embed(title=f"Moderation Logs for {member}", color=0xe74c3c)
    embed.set_thumbnail(url=member.display_avatar.url)
    
    for log in logs:
        mod = bot.get_user(log['mod_id'])
        mod_name = mod.name if mod else "Unknown"
        date = datetime.fromisoformat(log['timestamp']).strftime('%Y-%m-%d %H:%M')
        
        field_value = f"**Moderator:** {mod_name}\n**Reason:** {log['reason']}\n**Date:** {date}"
        if log.get('duration'):
            field_value += f"\n**Duration:** {log['duration']}"
        
        embed.add_field(
            name=f"{log['action'].title()}",
            value=field_value,
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, channel: discord.TextChannel = None, delay: str = None):
    """Set or check slowmode"""
    if not channel:
        channel = ctx.channel
    
    if not delay:
        current = channel.slowmode_delay
        if current == 0:
            await ctx.send(f"{channel.mention} has no slowmode.")
        else:
            await ctx.send(f"{channel.mention} slowmode: {current} seconds")
        return
    
    seconds = parse_time(delay)
    if seconds is None:
        await ctx.send("❌ Invalid time format. Use: 10s, 5m, etc.")
        return
    
    if seconds > 21600:  # 6 hours max
        await ctx.send("❌ Maximum slowmode is 6 hours.")
        return
    
    try:
        await channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send(f"✅ Slowmode disabled for {channel.mention}")
        else:
            await ctx.send(f"✅ Slowmode set to {delay} for {channel.mention}")
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to edit this channel.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx, channel: discord.TextChannel = None):
    """Lock a channel"""
    if not channel:
        channel = ctx.channel
    
    try:
        await channel.set_permissions(ctx.guild.default_role, send_messages=False)
        embed = discord.Embed(title="Channel Locked", description=f"{channel.mention} has been locked.", color=0xff0000)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to edit this channel.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx, channel: discord.TextChannel = None):
    """Unlock a channel"""
    if not channel:
        channel = ctx.channel
    
    try:
        await channel.set_permissions(ctx.guild.default_role, send_messages=None)
        embed = discord.Embed(title="Channel Unlocked", description=f"{channel.mention} has been unlocked.", color=0x00ff00)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to edit this channel.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lockall(ctx):
    """Lock all channels in current category"""
    category = ctx.channel.category
    if not category:
        await ctx.send("❌ This channel is not in a category.")
        return
    
    locked_count = 0
    for channel in category.channels:
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.set_permissions(ctx.guild.default_role, send_messages=False)
                locked_count += 1
            except:
                pass
    
    embed = discord.Embed(title="Category Locked", description=f"Locked {locked_count} channels in {category.name}", color=0xff0000)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlockall(ctx):
    """Unlock all channels in current category"""
    category = ctx.channel.category
    if not category:
        await ctx.send("❌ This channel is not in a category.")
        return
    
    unlocked_count = 0
    for channel in category.channels:
        if isinstance(channel, discord.TextChannel):
            try:
                await channel.set_permissions(ctx.guild.default_role, send_messages=None)
                unlocked_count += 1
            except:
                pass
    
    embed = discord.Embed(title="Category Unlocked", description=f"Unlocked {unlocked_count} channels in {category.name}", color=0x00ff00)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def say(ctx, *, message):
    """Make the bot say something"""
    await ctx.message.delete()
    await ctx.send(message)

@bot.command()
@commands.has_permissions(manage_roles=True)
async def temprole(ctx, member: discord.Member, role: discord.Role, duration: str):
    """Give a temporary role"""
    seconds = parse_time(duration)
    if not seconds:
        await ctx.send("❌ Invalid time format. Use: 10m, 1h, 1d")
        return
    
    try:
        await member.add_roles(role, reason=f"Temporary role by {ctx.author}")
        
        expires = datetime.now() + timedelta(seconds=seconds)
        key = f"{ctx.guild.id}_{member.id}_{role.id}"
        temp_roles[key] = {'expires': expires}
        
        embed = discord.Embed(title="Temporary Role Added", color=0x00ff00)
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Role", value=role.mention, inline=True)
        embed.add_field(name="Duration", value=duration, inline=True)
        
        await ctx.send(embed=embed)
        
    except discord.Forbidden:
        await ctx.send("❌ I don't have permission to manage this role.")

@bot.command()
async def membercount(ctx):
    """Show server member count"""
    guild = ctx.guild
    embed = discord.Embed(title=f"{guild.name} Member Count", color=0x3498db)
    embed.add_field(name="Total Members", value=guild.member_count, inline=True)
    embed.add_field(name="Humans", value=len([m for m in guild.members if not m.bot]), inline=True)
    embed.add_field(name="Bots", value=len([m for m in guild.members if m.bot]), inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def serverinfo(ctx):
    """Show server information"""
    guild = ctx.guild
    embed = discord.Embed(title=guild.name, color=0x3498db)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime('%Y-%m-%d'), inline=True)
    embed.add_field(name="Member Count", value=guild.member_count, inline=True)
    embed.add_field(name="Text Channels", value=len(guild.text_channels), inline=True)
    embed.add_field(name="Voice Channels", value=len(guild.voice_channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def roleinfo(ctx, *, role: discord.Role):
    """Show role information"""
    embed = discord.Embed(title=f"Role: {role.name}", color=role.color)
    embed.add_field(name="ID", value=role.id, inline=True)
    embed.add_field(name="Members", value=len(role.members), inline=True)
    embed.add_field(name="Color", value=str(role.color), inline=True)
    embed.add_field(name="Created", value=role.created_at.strftime('%Y-%m-%d'), inline=True)
    embed.add_field(name="Mentionable", value=role.mentionable, inline=True)
    embed.add_field(name="Hoisted", value=role.hoist, inline=True)
    await ctx.send(embed=embed)

# SLASH COMMANDS
@bot.tree.command(name="warn", description="Warn a member")
async def slash_warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    """Slash command version of warn"""
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("❌ You don't have permission to warn members.", ephemeral=True)
        return
    
    if member.id not in warnings:
        warnings[member.id] = []
    
    warning = {
        'reason': reason,
        'mod_id': interaction.user.id,
        'timestamp': datetime.now().isoformat()
    }
    
    warnings[member.id