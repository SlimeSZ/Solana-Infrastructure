import requests
import discord
from discord.ext import commands
import asyncio
import aiohttp
import re
import time
from datetime import datetime
from env import DISCORD_BOT_TOKEN

from process_descriptions import TX_ANALYZER
from serverdata import ServerData
from dexapi import DexScreenerAPI

intents = discord.Intents.all()
intents.message_content = True
intents.guild_messages = True
bot = commands.Bot(command_prefix='!', intents=intents)

class ScrapeAD:
    def __init__(self, bot):
        #configs & imports
        self.bot = bot
        self.limit = 1
        self.description_processor = TX_ANALYZER()
        self.serv_data = ServerData()
        self.dex = DexScreenerAPI()
        
        #webhooks
        self.multi_alert_webhook = ""
        
        #message handling.tracking
        self.processed_messages = set()
        self.multi_alerted_cas = set()
        self.ca_to_tx_descriptions = {}
        self.ca_appearences = {}


        self.swt_message_data = {} 
        self.fresh_message_data = {}
        self.degen_message_data = {}
        self.ca_server_counts = {}


        #ca sets
        self.high_freq_cas = set()
        self.legend_cas = set()
        self.kol_alpha_cas = set()
        self.kol_regular_cas = set()
        self.whale_cas = set()
        self.smart_cas = set()
        self.challenge_cas = set()
        self.degen_cas = set()
        self.insider_wallet_cas = set()
        self.fresh_cas = set()
        self.fresh_5sol_1m_mc_cas = set()
        self.fresh_1h_cas = set()
        

    async def swt_fetch_messages(self, session):
        await self.bot.wait_until_ready()
        
        while True:
            try:
                message_found = False
                for channel_id in self.swt_channel_ids:
                    channel = self.bot.get_channel(channel_id)
                    channel_name = self.swt_channel_ids.get(channel_id, "Unknown Channel")
                    if channel:
                        async for message in channel.history(limit=self.limit):
                            message_id = str(message.id)
                            if message_id not in self.processed_messages:
                                message_found = True
                                self.processed_messages.add(message_id)
                                print(f"\nProcessing message from {channel_name}")
                                if message.embeds:
                                    for embed in message.embeds:
                                        message_data = {
                                            'timestamp': message.created_at.isoformat(),
                                            'description': embed.description or '',
                                            'fields': {},
                                            'channel_name': channel_name
                                        }
                                        if embed.fields:
                                            for field in embed.fields:
                                                field_name = field.name.strip()
                                                field_value = field.value.strip()
                                                message_data['fields'][field_name] = field_value

                                        self.swt_message_data[message_id] = message_data
                
                if message_found:
                    return self.swt_message_data
                
                await asyncio.sleep(4)

            except Exception as e:
                print(f"Error in SWT fetch: {str(e)}")
                await asyncio.sleep(4)

    async def swt_process_messages(self, session):
        while True:
            try:
                data = await self.swt_fetch_messages()
                if not data:
                    await asyncio.sleep(4)
                    continue
                
                for message_id, message_data in data.items():
                    # Description extraction
                    if message_data["description"]:
                        print(f"Description: {message_data['description']}")
                        tx_data = await self.description_processor.extract_buys_sells(message_data['description'])
                        if tx_data:
                            tx_type = tx_data['type']
                            sol_amount = tx_data['sol_amount']
                            raw_tx = tx_data['raw_description']
                            print(f"{tx_type} OF {sol_amount} SOL\n{raw_tx}\n")

                    fields = message_data.get('fields', {})
                    excluded_fields = ['sol:', 'useful links:', 'buy with bonkbot:']
                    for field_name, field_value in fields.items():
                        # Token name & CA
                        if field_name.lower() not in excluded_fields:
                            token_name = field_name
                            ca = field_value
                            print(f"{token_name} || {ca}")

                            channel_name = message_data['channel_name']
                            if ca:
                                if channel_name == "Whale":
                                    self.whale_cas.add(ca)
                                    await self.check_and_alert_union(ca, "SWT")
                                elif channel_name == "Smart":
                                    self.smart_cas.add(ca)
                                    await self.check_and_alert_union(ca, "SWT")
                                # ... (other channels)

                        # Trading dex links
                        if field_name == "Useful Links:":
                            links = field_value.split(" | ")
                            photon = next((link.split("](")[1].rstrip(")") 
                                        for link in links if "Photon](" in link), None)
                            dex = next((link.split("](")[1].rstrip(")") 
                                    for link in links if "DexScreener](" in link), None)
                            bull_x = next((link.split("](")[1].rstrip(")") 
                                    for link in links if "BullX](" in link), None)

            except Exception as e:
                print(f"Error in SWT process: {str(e)}")
                await asyncio.sleep(4)
                    

    async def count_ca_occurences(self, session, ca):
        counter = 0
        for channel_id in self.swt_channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                channel_counter = 0
                try:
                    async for message in channel.history(limit=self.limit):
                        if message.embeds:
                            for embed in message.embeds:
                                if embed.fields:
                                    for field in embed.fields:
                                        if field.name not in ["SOL:", "Useful Links:", "Buy with Bonkbot:"]:
                                            field_value = field.value.strip()
                                            token_ca = field_value.split("::")[-1].strip() if "::" in field_value else field_value
                                            if token_ca.lower() == ca.lower():
                                                channel_counter += 1
                                                break
                    counter += channel_counter
                except Exception as e:
                    print(f"Error fetching server count for {channel.name}: {str(e)}")
                    return None
                await asyncio.sleep(1)
        return counter
        

    async def fresh_fetch_messages(self, session):
        await self.bot.wait_until_ready()
        
        while True:
            try:
                message_found = False
                for channel_id in self.fresh_channel_ids:
                    channel = self.bot.get_channel(channel_id)
                    channel_name = self.fresh_channel_ids.get(channel_id, "Unknown Fresh Channel")
                    if channel:
                        async for message in channel.history(limit=1):
                            message_id = str(message.id)
                            if message_id not in self.processed_messages:
                                message_found = True
                                self.processed_messages.add(message_id)
                                print(f"\nProcessing Fresh message from {channel_name}")
                                if message.embeds:
                                    for embed in message.embeds:
                                        message_data = {
                                            'timestamp': message.created_at.isoformat(),
                                            'title': embed.title if embed.title else '',
                                            'description': embed.description if embed.description else '',
                                            'fields': {},
                                            'channel_name': channel_name
                                        }
                                        if embed.fields:
                                            for field in embed.fields:
                                                field_name = field.name.strip()
                                                field_value = field.value.strip()
                                                message_data['fields'][field_name] = field_value
                                        
                                        self.fresh_message_data[message_id] = message_data
                
                if message_found:
                    return self.fresh_message_data
                    
                await asyncio.sleep(2)
            
            except Exception as e:
                print(f"Error fetching fresh messages: {str(e)}")
                await asyncio.sleep(2)

    async def fresh_process_messages(self, session):
        while True:
            try:
                data = await self.fresh_fetch_messages()
                if not data:
                    await asyncio.sleep(4)
                    continue
                
                for message_id, message_data in data.items():
                    if message_data['description']:
                        tx_data = await self.description_processor.extract_buys_sells(message_data['description'])
                        if tx_data:
                            tx_type = tx_data['type']
                            sol_amount = tx_data['sol_amount']
                            raw_tx = tx_data['raw_description']
                            print(f"{tx_type} OF {sol_amount} SOL")
                    
                    if message_data['title']:
                        token_name = message_data['title']
                        print(token_name) if token_name else print(f"TOKEN NAME NOT EXTRACTED")

                    fields = message_data.get('fields', {})
                    for field_name, field_value in fields.items():
                        if field_name.strip(':').lower() == 'token address':
                            ca = field_value.strip()
                            channel_name = message_data['channel_name'] 
                            if ca:
                                print(f"{ca}\n{'=' * 50}")
                                if channel_name == "Fresh":
                                    self.fresh_cas.add(ca)
                                    await self.check_and_alert_union(ca, "Fresh")
                                elif channel_name == "Fresh 5sol 1m MC":
                                    self.fresh_5sol_1m_mc_cas.add(ca)
                                    await self.check_and_alert_union(ca, "Fresh")
                                elif channel_name == "Fresh 1h":
                                    self.fresh_1h_cas.add(ca)
                                    await self.check_and_alert_union(ca, "Fresh")

            except Exception as e:
                print(f"Error processing fresh messages: {str(e)}")
                await asyncio.sleep(4)

    async def degen_fetch_and_process_messages(self, session):
        await self.bot.wait_until_ready()
        print("Starting degen messages...")

        while True:
            try:
                channel = self.bot.get_channel(self.degen_channel_id)
                if channel:
                    async for message in channel.history(limit=self.limit):
                        message_id = str(message.id)
                        if message_id not in self.processed_messages:
                            self.processed_messages.add(message_id)
                            print(f"\nProcessing Degen message")
                            if message.embeds:
                                for embed in message.embeds:
                                    if embed.fields:
                                        message_data = {
                                            'timestamp': message.created_at.isoformat(),
                                            'fields': {}
                                        }
                                        for field in embed.fields:
                                            # Get CA
                                            if "Token:" in field.value:
                                                try:
                                                    ca = field.value.split('`')[1].strip()
                                                    if ca:
                                                        self.degen_cas.add(ca)
                                                        message_data['ca'] = ca
                                                        print(f"CA: {ca}")
                                                        await self.check_and_alert_union(ca, "Degen")
                                                except IndexError:
                                                    print("Could not extract CA from field")
                                            
                                            # Process Swap Details
                                            if "Swapped" in field.value:
                                                swap_details = field.value
                                                tx_data = await self.description_processor.extract_degen_buys_sells(swap_details)
                                                if tx_data:
                                                    tx_type = tx_data['type']
                                                    if tx_type == 'Sell':
                                                        sol_amount = tx_data['sol_amount']
                                                        token_amount = tx_data['token_amount']
                                                    else:
                                                        token_amount = tx_data['sol_amount']
                                                        sol_amount = tx_data['token_amount']
                                                    
                                                    print(f"{tx_type} OF {sol_amount} SOL")
                                                    print(f"Token Amount: {token_amount}")

                                                    message_data['transaction'] = {
                                                        'type': tx_type,
                                                        'sol_amount': sol_amount,
                                                        'token_amount': token_amount
                                                    }
                                            
                                            message_data['fields'][field.name] = field.value
                                        self.degen_message_data[message_id] = message_data
                                print("=" * 50)

                await asyncio.sleep(2)

            except Exception as e:
                print(f"Error in degen processing: {str(e)}")
                await asyncio.sleep(2)

    async def check_multialert(self, session, token_name, ca, source_channel):
        try:
            if ca in self.multi_alerted_cas:
                return
            
            current_time = datetime.now().isoformat()

            if ca not in self.ca_appearences:
                self.ca_appearences[ca] = {
                    'channels': set(),
                    'first_seen': current_time,
                    'token_name': token_name
                }
            self.ca_appearences[ca]['channels'].add(source_channel)
            
            all_fresh = self.fresh_cas | self.fresh_5sol_1m_mc_cas | self.fresh_1h_cas | self.degen_cas
            all_swt = (self.whale_cas | self.smart_cas | self.legend_cas | self.kol_alpha_cas | self.kol_regular_cas | self.challenge_cas | self.high_freq_cas | self.insider_wallet_cas)

            multialert_found = False #should act more as a dict with bool val associated w ca
            if ca in all_fresh and ca in all_swt: #associate ca w channel it was found in, pass it to print or webhook statements
                multialert_found = True

                
                
            
            if multialert_found: #ensure skips instead of returns if one thing not found
                
                #dex calls & processes:
                dex_data = await self.dex.fetch_token_data_from_dex(ca)
                if not dex_data:
                    return
                marketcap = dex_data['token_mc']
                m5_vol = dex_data['token_5m_vol']
                liquidity = dex_data['token_liqudity']
                token_created_at = dex_data['token_created_at']
                pool_address = dex_data['pool_address']

                telegram = dex_data['socials'].get('telegram', {}) or None
                twitter = dex_data['socials'].get('twitter', {}) or None
                dex_url = dex_data['dex_url']

                
                #get servercount & buy/sell data
                self.serv_data.target_ca = ca
                swt_data = await self.serv_data.swt_server_data()
                degen_data = await self.serv_data.degen_server_data()
                fresh_data = await self.serv_data.fresh_server_data()
                if not swt_data or not degen_data or not fresh_data:
                    return
                swt_count = swt_data['count']
                swt_buys = swt_data['buys']
                swt_sells = swt_data['sells']
                degen_count = degen_data['count']
                degen_buys = degen_data['buys']
                degen_sells = degen_data['sells']
                total_swt_count = swt_count + degen_count
                total_swt_buys = swt_buys + degen_buys
                total_swt_sells = swt_sells + degen_sells
                total_fresh_count = fresh_data['count']
                total_fresh_buys = fresh_data['buys']
                total_fresh_sells = fresh_data['sells']

                #get last 5 txs (serverdata.py)
                last_5_swt = swt_data['latest_descriptions'][-1:] if swt_data else []
                last_5_degen = degen_data['latest_descriptions'][-1:] if degen_data else []
                last_5_fresh = fresh_data['latest_descriptions'][-1:] if fresh_data else []
                
                #call tg evaluation



                webhook_data = {
                    
                }
                
                


                        


class Main:
    def __init__(self):
        self.ad_scraper = ScrapeAD(bot)
    
    async def run(self):
        @bot.event
        async def on_ready():
            print(f"Bot logged in as {bot.user}")

        async with aiohttp.ClientSession() as session:
            # Create all tasks including bot startup
            tasks = [
                bot.start(DISCORD_BOT_TOKEN),
                self.ad_scraper.swt_process_messages(),
                self.ad_scraper.fresh_process_messages(),
                self.ad_scraper.degen_fetch_and_process_messages()
            ]
            
            try:
                await asyncio.gather(*tasks)  # Don't forget the * to unpack tasks
            except Exception as e:
                print(f"Error in main loop: {str(e)}")
                await asyncio.sleep(5)
                # Optionally restart tasks
                await self.run()


if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())
