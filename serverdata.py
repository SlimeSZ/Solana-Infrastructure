import asyncio
import discord
from discord.ext import commands
from process_descriptions import TX_ANALYZER
from env import DISCORD_BOT_TOKEN

intents = discord.Intents.all()
intents.message_content = True
intents.guild_messages = True
bot = commands.Bot(command_prefix='!', intents=intents)

class ServerData:
    def __init__(self, bot):
        self.bot = bot
        self.tx = TX_ANALYZER()
        self.target_ca = None
        
        # Channel configurations
        self.swt_channel_ids = [
            1273250694257705070,  # whale  
            1280465862163304468,  # smart
            1279040666101485630,  # legend
            1280445495482781706,  # kol alpha
            1273245344263569484,  # kol reg
            1283348335863922720,  # challenge
            1273670414098501725,  # high freq
            1277231510574862366   # insider
        ]
        
        self.channel_names = {
            1273250694257705070: "Whale",
            1280465862163304468: "Smart",
            1279040666101485630: "Legend",
            1280445495482781706: "Kol Alpha",
            1273245344263569484: "Kol Regular",
            1283348335863922720: "Challenge",
            1273670414098501725: "High Freq",
            1277231510574862366: "Insider"
        }
        
        self.degen_channel_id = 1278278627997384704
        
        self.fresh_channel_names = {
            1281675800260640881: "Fresh",
            1281676746202026004: "Fresh 5sol 1m MC",
            1281677424005746698: "Fresh 1h"
        }

    def _create_base_server_data(self):
        """Creates the base server data structure"""
        return {
            'count': 0,
            'buys': 0.0,
            'sells': 0.0,
            'channels': {},
            'latest_descriptions': [],
            'trading_links': {
                'photon': None,
                'dex': None,
                'bull_x': None
            }
        }

    async def swt_server_data(self):
        if not self.target_ca:
            return
            
        server_data = self._create_base_server_data()
        
        for channel_id in self.swt_channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    channel_buys = 0.0
                    channel_sells = 0.0
                    channel_count = 0
                    
                    retry_count = 0
                    max_retries = 3
                    
                    while retry_count < max_retries:
                        try:
                            async for message in channel.history(limit=500):
                                if message.embeds:
                                    for embed in message.embeds:
                                        if embed.fields:
                                            excluded_fields = ['sol:', 'useful links:', 'buy with bonkbot:']
                                            found_ca = False
                                            
                                            # First pass: Check for CA match
                                            for field in embed.fields:
                                                field_name = field.name.lower() if field.name else ''
                                                if field_name not in excluded_fields:
                                                    ca = field.value.strip() if field.value else ''
                                                    if ca.lower() == self.target_ca.lower():
                                                        found_ca = True
                                                        channel_count += 1
                                                        if embed.description:
                                                            server_data['latest_descriptions'].append(embed.description)
                                                            tx_data = await self.tx.extract_buys_sells(embed.description)
                                                            if tx_data:
                                                                tx_type = tx_data['type']
                                                                sol_amount = tx_data['sol_amount']
                                                                if tx_type == "Buy":
                                                                    channel_buys += sol_amount
                                                                else:
                                                                    channel_sells += sol_amount
                                                        break
                                            
                                            # Second pass: If CA matched, look for trading links
                                            if found_ca:
                                                for field in embed.fields:
                                                    field_name = field.name.lower() if field.name else ''
                                                    if field_name == "useful links:":
                                                        links = field.value.split(" | ")
                                                        for link in links:
                                                            if "Photon](" in link:
                                                                server_data['trading_links']['photon'] = link.split("](")[1].rstrip(")")
                                                            elif "DexScreener](" in link:
                                                                server_data['trading_links']['dex'] = link.split("](")[1].rstrip(")")
                                                            elif "BullX](" in link:
                                                                server_data['trading_links']['bull_x'] = link.split("](")[1].rstrip(")")
                            break  # If successful, break the retry loop
                            
                        except discord.errors.HTTPException as e:
                            retry_count += 1
                            print(f"Rate limit hit for {channel.name}, attempt {retry_count} of {max_retries}")
                            if retry_count < max_retries:
                                await asyncio.sleep(5 * retry_count)
                            else:
                                print(f"Max retries reached for {channel.name}, skipping...")
                                break

                    # Update channel-specific data with channel name from mapping
                    channel_name = self.channel_names.get(channel_id, channel.name)
                    server_data['channels'][channel_name] = {
                        'count': channel_count,
                        'buys': channel_buys,
                        'sells': channel_sells,
                        'buy_pressure': channel_buys / (channel_sells + 0.0001),  # Avoid division by zero
                        'channel_id': channel_id
                    }
                    
                    # Update totals
                    server_data['count'] += channel_count
                    server_data['buys'] += channel_buys
                    server_data['sells'] += channel_sells
                    
                except Exception as e:
                    print(f"Error counting SWT messages in {channel.name}: {str(e)}")
                    import traceback
                    print(traceback.format_exc())
                
                await asyncio.sleep(2)

        server_data['latest_descriptions'] = server_data['latest_descriptions'][-5:] if server_data['latest_descriptions'] else []
        return server_data

    async def fresh_server_data(self):
        if not self.target_ca:
            return
            
        server_data = self._create_base_server_data()
        del server_data['trading_links']  # Not needed for fresh data
        
        for channel_id in self.fresh_channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    channel_buys = 0.0
                    channel_sells = 0.0
                    channel_count = 0
                    async for message in channel.history(limit=500):
                        if message.embeds:
                            for embed in message.embeds:
                                if embed.fields:
                                    for field in embed.fields:
                                        if field.name.strip(':').lower() == "token address":
                                            ca = field.value.strip()
                                            if ca.lower() == self.target_ca.lower():
                                                channel_count += 1
                                                if embed.description:
                                                    server_data['latest_descriptions'].append(embed.description)
                                                tx_data = await self.tx.extract_buys_sells(embed.description)
                                                if tx_data:
                                                    tx_type = tx_data['type']
                                                    sol_amount = tx_data['sol_amount']
                                                    if tx_type == "Buy":
                                                        channel_buys += sol_amount
                                                    else:
                                                        channel_sells += sol_amount
                    
                    # Update channel-specific data with channel name from mapping
                    channel_name = self.fresh_channel_names.get(channel_id, channel.name)
                    server_data['channels'][channel_name] = {
                        'count': channel_count,
                        'buys': channel_buys,
                        'sells': channel_sells,
                        'buy_pressure': channel_buys / (channel_sells + 0.0001),  # Avoid division by zero
                        'channel_id': channel_id
                    }
                    
                    # Update totals
                    server_data['count'] += channel_count
                    server_data['buys'] += channel_buys
                    server_data['sells'] += channel_sells
                    
                except Exception as e:
                    print(f"Error counting Fresh messages in {channel.name}: {e}")
                
                await asyncio.sleep(1)
                
        server_data['latest_descriptions'] = server_data['latest_descriptions'][-5:] if server_data['latest_descriptions'] else []
        return server_data

    async def degen_server_data(self):
        if not self.target_ca:
            return
        
        server_data = self._create_base_server_data()
        del server_data['trading_links']  # Not needed for degen data
        
        channel = self.bot.get_channel(self.degen_channel_id)
        if channel:
            try:
                channel_buys = 0.0
                channel_sells = 0.0
                channel_count = 0
                async for message in channel.history(limit=500):
                    if message.embeds:
                        for embed in message.embeds:
                            if embed.fields:
                                current_ca = None
                                is_target_tx = False
                                
                                for field in embed.fields:
                                    if "Token:" in field.value:
                                        try:
                                            current_ca = field.value.split('`')[1].strip()
                                            if current_ca.lower() == self.target_ca.lower():
                                                is_target_tx = True
                                                channel_count += 1
                                                break
                                        except Exception as e:
                                            print(f"Error extracting CA: {e}")
                                            continue
                                
                                if is_target_tx:
                                    for field in embed.fields:
                                        if field.value and ("swapped" in field.value.lower() or "transferred" in field.value.lower()):
                                            tx_desc = field.value
                                            if tx_desc:
                                                server_data['latest_descriptions'].append(tx_desc)
                                            
                                            tx_data = await self.tx.extract_degen_buys_sells(tx_desc)
                                            if tx_data:
                                                tx_type = tx_data['type']
                                                sol_amount = tx_data['sol_amount']
                                                
                                                if tx_type == "Buy":
                                                    channel_buys += sol_amount
                                                elif tx_type == "Sell":
                                                    channel_sells += sol_amount

                server_data['channels']["Degen"] = {
                    'count': channel_count,
                    'buys': channel_buys,
                    'sells': channel_sells,
                    'buy_pressure': channel_buys / (channel_sells + 0.0001),  # Avoid division by zero
                    'channel_id': self.degen_channel_id
                }
                
                server_data['count'] = channel_count
                server_data['buys'] = channel_buys
                server_data['sells'] = channel_sells
                                            
            except Exception as e:
                print(f"Error in degen processing: {str(e)}")
                import traceback
                print(traceback.format_exc())
        
        server_data['latest_descriptions'] = server_data['latest_descriptions'][-5:] if server_data['latest_descriptions'] else []
        return server_data