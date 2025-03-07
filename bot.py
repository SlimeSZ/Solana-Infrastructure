#libraries
import requests
import sqlite3
import math
import discord
from discord.ext import commands
import asyncio
import aiohttp
import re
import time
from datetime import datetime
from env import DISCORD_BOT_TOKEN
#.py imports
from process_descriptions import TX_ANALYZER
from hr24maxprice import Max
from trueage import TrueAge
from serverdata import ServerData
from dexapi import DexScreenerAPI
from tg import SoulScannerBot, BundleBot, WAlletPNL
from tokenage import TokenAge
from alefalerts import MessageSender
from topholders import HolderAmount
from walletpnl import WalletPNL
from scoring import HolderScore, TokenomicScore, TrustScore, PenalizeScore, TokenAgeConvert
from marketcapfinal import Supply, Price, Marketcap
from bdmetadata import BuySellTradeUniqueData
from devreport import DevHist
from twoxmonitor import TwoXChecker
from ob import OrderBlock
from supportresistance import SupportResistance
from getohlcv import OH 
#from x import Twitter
from scanforentry import MarketcapMonitor
from ath import ATH
from backupath import BATH
from webhooks import AlefAlertWebhook, MultiAlert 

intents = discord.Intents.all()
intents.message_content = True
intents.guild_messages = True
bot = commands.Bot(command_prefix='!', intents=intents)

from create_table import create_all_tables
create_all_tables()

class ScrapeAD:
    def __init__(self, bot):
        #configs & imports
        self.bot = bot
        self.limit = 1
        self.description_processor = TX_ANALYZER()
        self.dev_history = DevHist()
        self.serv_data = None
        self.dex = DexScreenerAPI()
        self.soul_scanner_bot = SoulScannerBot()
        self.bundle_bot = BundleBot()
        self.wallet_pnl = WalletPNL()
        self.wallet_pnl_tg = WAlletPNL()
        self.token_age = TokenAge()
        self.slime_alert = MessageSender()
        self.rickbot_webhook = AlefAlertWebhook()  
        self.ma_webhooks = MultiAlert()
        self.mc_monitor = MarketcapMonitor()
        self.true_age = TrueAge()
        self.ath = ATH()
        self.bath = BATH()
        self.o = OH()
        self.sr = SupportResistance()
        #self.price = Price()
        #self.x = Twitter()
        self.get_top_holders = HolderAmount()
        self.ob = OrderBlock()
        #scoring imports
        self.holderscore = HolderScore()
        self.tokenomicscore = TokenomicScore()
        self.trustscore = TrustScore()
        self.penalizescore = PenalizeScore()

        
        self.bd_trade_data = BuySellTradeUniqueData()
        self.twox = TwoXChecker()
        self.age_converter = TokenAgeConvert()
        
        #webhooks
        self.multi_alert_webhook = ""
        
        #message handling.tracking
        self.processed_messages = set()
        self.multi_alerted_cas = set()
        self.ten_five_sol_alerts = set()
        self.ca_to_tx_descriptions = {}
        self.ca_appearences = {}
        self.ca_trading_links = {}

        self.swt_message_data = {} 
        self.fresh_message_data = {}
        self.degen_message_data = {}
        self.ca_server_counts = {}


        #ca sets & channel ids
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
        self.swt_channel_ids = {
            1273250694257705070: "Whale",
            1280465862163304468: "Smart",
            1279040666101485630: "Legend",
            1280445495482781706: "Kol Alpha",
            1273245344263569484: "Kol Regular",
            1283348335863922720: "Challenge",
            1273670414098501725: "High Freq",
            1277231510574862366: "Insider",
        }
        self.fresh_channel_ids = {
             1281675800260640881: "Fresh",
            1281676746202026004: "Fresh 5sol 1m MC",
            1281677424005746698: "Fresh 1h",
        }
        self.degen_channel_id = 1278278627997384704

        self.short_timeframes = ["1min", "30s", "10s", "1s"]
        self.longer_timeframes = ["5min", "10min", "30min", "1h"]

        self.sup = Supply()
        self.pri = Price()
        self.markca = Marketcap()


    async def initialize(self):
        await self.bot.wait_until_ready()
        self.serv_data = ServerData(self.bot)
        

    async def swt_fetch_messages(self):
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

                print(f"[{datetime.now().strftime('%H:%M:%S')}] Processing {len(data)} new SWT message(s)")
                
                for message_id, message_data in data.items():
                    # Description extraction
                    if message_data["description"]:
                        tx_data = await self.description_processor.extract_buys_sells(message_data['description'])
                        if tx_data:
                            raw_tx = tx_data['raw_description']
                            tx_type = tx_data['type']
                            sol_amount = tx_data['sol_amount']
                                    
                            raw_tx = tx_data['raw_description']

                    fields = message_data.get('fields', {})
                    excluded_fields = ['sol:', 'useful links:', 'buy with bonkbot:']
                    for field_name, field_value in fields.items():
                        # Token name & CA
                        if field_name.lower() not in excluded_fields:
                            token_name = field_name
                            ca = field_value
                            channel_name = message_data['channel_name']
                            if ca:
                                if channel_name == "Whale":
                                    self.whale_cas.add(ca)
                                    await self.check_multialert(session, token_name, ca, channel_name)
                                elif channel_name == "Smart":
                                    self.smart_cas.add(ca)
                                    await self.check_multialert(session, token_name, ca, channel_name)
                                elif channel_name == "Challenge":
                                    self.challenge_cas.add(ca)
                                    await self.check_multialert(session, token_name, ca, channel_name)
                                elif channel_name == "Legend":
                                    self.legend_cas.add(ca)
                                    await self.check_multialert(session, token_name, ca, channel_name)
                                elif channel_name == "Kol Alpha":
                                    await self.check_multialert(session, token_name, ca, channel_name)
                                elif channel_name == "Kol Regular":
                                    await self.check_multialert(session, token_name, ca, channel_name)
                                elif channel_name == "High Freq":
                                    await self.check_multialert(session, token_name, ca, channel_name)
                                elif channel_name == "Insider":
                                    await self.check_multialert(session, token_name, ca, channel_name)
                            if ca and sol_amount > 10:
                                if ca not in self.ten_five_sol_alerts:
                                    self.ten_five_sol_alerts.add(ca)
                                    print(f"10+ SOL BUY DETECTED")
                                    await self.ma_webhooks.tensolbuywebhook(sol_amount, token_name, ca, channel_name)

            except Exception as e:
                print(f"Error in SWT process: {str(e)}")
                await asyncio.sleep(4)        

    async def fresh_fetch_messages(self):
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

                print(f"[{datetime.now().strftime('%H:%M:%S')}] Processing {len(data)} new Fresh message(s)")
                
                for message_id, message_data in data.items():
                    if message_data['description']:
                        tx_data = await self.description_processor.extract_buys_sells(message_data['description'])
                        if tx_data:
                            tx_type = tx_data['type']
                            sol_amount = tx_data['sol_amount']
                            raw_tx = tx_data['raw_description']
                    
                    if message_data['title']:
                        token_name = message_data['title']

                    fields = message_data.get('fields', {})
                    for field_name, field_value in fields.items():
                        if field_name.strip(':').lower() == 'token address':
                            ca = field_value.strip()
                            channel_name = message_data['channel_name'] 
                            if ca:
                                if channel_name == "Fresh":
                                    self.fresh_cas.add(ca)
                                    await self.check_multialert(session, token_name, ca, "Fresh")
                                elif channel_name == "Fresh 5sol 1m MC":
                                    self.fresh_5sol_1m_mc_cas.add(ca)
                                    await self.check_multialert(session, token_name, ca, "Fresh 5sol 1m mc")
                                elif channel_name == "Fresh 1h":
                                    self.fresh_1h_cas.add(ca)
                                    await self.check_multialert(session, token_name, ca, "Fresh 1h")

            except Exception as e:
                print(f"Error processing fresh messages: {str(e)}")
                await asyncio.sleep(4)

    async def degen_fetch_and_process_messages(self, session):
        await self.bot.wait_until_ready()

        while True:
            try:
                channel = self.bot.get_channel(self.degen_channel_id)
                if channel:
                    async for message in channel.history(limit=self.limit):
                        message_id = str(message.id)
                        if message_id not in self.processed_messages:
                            self.processed_messages.add(message_id)
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
                                                        await self.check_multialert(session, "", ca, "Degen")
                                                except IndexError:
                                                    print("Could not extract CA from field")
                                            
                                            # Process Swap Details
                                            if "Swapped" in field.value:
                                                swap_details = field.value
                                                tx_data = await self.description_processor.extract_degen_buys_sells(swap_details)
                                                if tx_data:
                                                    tx_type = tx_data['type']
                                                    sol_amount = tx_data['sol_amount']
                                                    
                                                    message_data['transaction'] = {
                                                        'type': tx_type,
                                                        'sol_amount': sol_amount,
                                                        'raw_description': tx_data['raw_description']
        }
                                                    

                                                    message_data['transaction'] = {
                                                        'type': tx_type,
                                                        'sol_amount': sol_amount
                                                    }
                                            
                                            message_data['fields'][field.name] = field.value
                                        self.degen_message_data[message_id] = message_data

                await asyncio.sleep(2)

            except Exception as e:
                print(f"Error in degen processing: {str(e)}")
                await asyncio.sleep(2)

    async def start_2x_monitoring(self, ca, token_name):
        """Start monitoring a token for 2x price movements"""
        try:
            async with aiohttp.ClientSession() as session:
                # Create task for 2x monitoring
                await self.twox.start_marketcap_monitoring(ca, token_name)
                print(f"Started 2x monitoring for {token_name} ({ca})")
        except Exception as e:
            print(f"Error starting 2x monitoring for {ca}: {str(e)}")

    async def check_multialert(self, session, token_name, ca, channel_name):
        if self.serv_data is None:
            await self.initialize()
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
            self.ca_appearences[ca]['channels'].add(channel_name)
            
            all_fresh = self.fresh_cas | self.fresh_5sol_1m_mc_cas | self.fresh_1h_cas
            all_swt = (self.whale_cas | self.smart_cas | self.legend_cas | self.kol_alpha_cas | self.kol_regular_cas | self.challenge_cas | self.high_freq_cas | self.insider_wallet_cas)

            multialert_found = False 

            #test_ca = "DDAokw8my9MdWDZxbJw2gS6qu7svUcyaCRrv3AUKpump"
            #if ca == test_ca:
                #multialert_found = True

            if ca in all_fresh and (ca in self.degen_cas or ca in all_swt):
                multialert_found = True

            if multialert_found:
                self.multi_alerted_cas.add(ca)
                print(f"\nMUlTI ALERT FOUND\n{"*" * 50}")
                
                asyncio.create_task(self.start_2x_monitoring(ca, token_name))

                dex_data = {}
                backup_bd_data = {}
                unique_bd_data = {}
                marketcap = 0
                m5_vol = 0
                m30_vol = 0
                m30_vol_change = 0
                liquidity = 0
                telegram = None
                twitter = None
                holder_count = 0
                pool_address = None

                try:
                    price = await self.pri.price(ca)
                except Exception as e:
                    print(str(e))
                
                try:
                    dex_data = await self.dex.fetch_token_data_from_dex(ca) or {}
                except Exception as e:
                    print(f"Error fetching dex data: {str(e)}")
                
                try:
                    unique_bd_data = await self.bd_trade_data.process(ca) or {}
                    print("DEBUG: Got unique BD data")
                except Exception as e:
                    print(f"Error fetching unique BD data: {str(e)}")

                try:
                    token_name = dex_data.get('token_name') or backup_bd_data.get('name', 'Unknown Name')
                    print(f"Token Name: {token_name} CA: {ca}")
                    marketcap = dex_data.get('token_mc', 0) or self.markca.marketcap(ca)
                    print(f"Marketcap: ${marketcap:.2f}")
                    m5_vol = dex_data.get('token_5m_vol', 0)
                    print(f"5m volume: {m5_vol:.2f}")     
                    liquidity = dex_data.get('token_liquidity', 0)
                    if not liquidity:
                        l_data = await self.pri._bd_price_liquidity(ca)
                        _, liquidity = l_data
                    print(f"Liquidity: {liquidity}")
                    pool_address = dex_data.get('pool_address')
                    print(f"Pool Address: {pool_address if pool_address else 'Not found'}")
                except Exception as e:
                    print(f"Error processing token data: {str(e)}")

                print("DEBUG: About to fetch social data")
                try:
                    if dex_data and 'socials' in dex_data:
                        telegram = dex_data['socials'].get('telegram')
                        twitter = dex_data['socials'].get('twitter')
                    if not telegram and backup_bd_data:
                        telegram = backup_bd_data.get('telegram')
                    if not twitter and backup_bd_data:
                        twitter = backup_bd_data.get('twitter')
                    print(f"Twitter: {twitter}")
                    print(f"Telegram: {telegram}")
                except Exception as e:
                    print(f"Error processing social data: {e}")

                websites_data = None
                try:
                    if dex_data and 'websites' in dex_data:
                        websites_data = dex_data['websites']
                        print(f"Websites: Count={websites_data['count']}, Types={websites_data['types']}")
                except Exception as e:
                    print(f"Error processing website data: {e}")
                    websites_data = {'count': 0, 'types': [], 'urls': {}}
                
                print("DEBUG: About to process birdeye data")
                try:
                    if unique_bd_data:
                        m30_vol = unique_bd_data.get('m30_vol', 0)
                        m30_buys = unique_bd_data.get('m30_buys', 0)
                        m30_sells = unique_bd_data.get('m30_sells', 0)
                        m30_price_change = unique_bd_data.get('m30_price_change', 0)
                        m30_vol_change = unique_bd_data.get('m30_vol_change', 0)
                        m30_trades = unique_bd_data.get('m30_trade', 0)

                        # unique wallet data 
                        new_unique_wallet_count_30m = unique_bd_data.get('new_unique_wallets_30_min_count', 0)
                        print(f"New Unique wallets last 30m: {new_unique_wallet_count_30m}")

                        new_unique_wallet_percent_change_30m = unique_bd_data.get('new_unique_wallets_30_min_percent_change', 0)
                        print(f"Percentage change in unique wallets last 30m: {new_unique_wallet_percent_change_30m}%")

                        new_unique_wallet_count_1h = unique_bd_data.get('new_unique_wallets_1h_count', 0)
                        print(f"New Unique wallets last 1h: {new_unique_wallet_count_1h}")

                        new_unique_wallet_percent_change_1h = unique_bd_data.get('new_unique_wallets_1h_percent_change', 0)
                        print(f"Percentage change in unique wallets last 1h: {new_unique_wallet_percent_change_1h}%")

                        # general buy sell data 
                        trade_percent_change_30m = unique_bd_data.get('trade_30_min_percent_change', 0)
                        print(f"Trade percentage change last 30m: {trade_percent_change_30m}%")

                        buy_percent_change_30m = unique_bd_data.get('buy_30_min_percent_change', 0)
                        print(f"Buy percentage change last 30m: {buy_percent_change_30m}%")

                        sell_percent_change_30m = unique_bd_data.get('sell_30_min_percent_change', 0)
                        print(f"Sell percentage change last 30m: {sell_percent_change_30m}%")

                        holder_count = unique_bd_data.get('holders', 0)
                    else:
                        new_unique_wallet_count_30m = 0
                        new_unique_wallet_percent_change_30m = 0
                        new_unique_wallet_count_1h = 0
                        new_unique_wallet_percent_change_1h = 0
                        trade_percent_change_30m = 0
                        buy_percent_change_30m = 0
                        sell_percent_change_30m = 0
                        holder_count = 0
                except Exception as e:
                    print(f"Error processing birdeye data: {e}")
                    new_unique_wallet_count_30m = 0
                    new_unique_wallet_percent_change_30m = 0
                    new_unique_wallet_count_1h = 0
                    new_unique_wallet_percent_change_1h = 0
                    trade_percent_change_30m = 0
                    buy_percent_change_30m = 0
                    sell_percent_change_30m = 0
                    holder_count = 0

                print("DEBUG: About to fetch server data")           
                #get servercount & buy/sell data
                print(f"\nFetching server data for CA: {ca}")
                self.serv_data.target_ca = ca

                # Check SWT data
                swt_data = {}
                try:
                    swt_data = await self.serv_data.swt_server_data() or {}
                    print("DEBUG: Got SWT server data")
                except Exception as e:
                    print(f"Error fetching SWT server data: {str(e)}")
                    swt_data = {
                        'count': 0, 'buys': 0, 'sells': 0, 
                        'channels': {}, 'latest_descriptions': [],
                        'trading_links': {'photon': '', 'bull_x': '', 'dex': ''}
                    }

                # Check Degen data
                degen_data = {}
                try:
                    degen_data = await self.serv_data.degen_server_data() or {}
                    print("DEBUG: Got Degen server data")
                except Exception as e:
                    print(f"Error fetching Degen server data: {str(e)}")
                    degen_data = {
                        'count': 0, 'buys': 0, 'sells': 0,
                        'channels': {'Degen': {'buys': 0, 'sells': 0}},
                        'latest_descriptions': []
                    }

                # Check Fresh data
                fresh_data = {}
                try:
                    fresh_data = await self.serv_data.fresh_server_data() or {}
                    print("DEBUG: Got Fresh server data")
                except Exception as e:
                    print(f"Error fetching Fresh server data: {str(e)}")
                    fresh_data = {
                        'count': 0, 'buys': 0, 'sells': 0,
                        'channels': {}, 'latest_descriptions': []
                    }

                print("DEBUG: About to process trading links")
                #trading links:
                try:
                    links = swt_data.get('trading_links', {})
                    if not links:
                        links = {'photon': '', 'bull_x': '', 'dex': ''}
                    
                    photon_link = links.get('photon', '')
                    bull_x_link = links.get('bull_x', '')
                    dexscreener_link = links.get('dex', '')
                    print(f"Photon: {photon_link}")
                    print(f"Bullx: {bull_x_link}")
                    print(f"Dex Link: {dexscreener_link}")
                except Exception as e:
                    print(f"Error processing trading links: {str(e)}")
                    photon_link = ''
                    bull_x_link = ''
                    dexscreener_link = ''

                print("DEBUG: About to process server count data")
                try:
                    swt_count = swt_data.get('count', 0)
                    swt_buys = swt_data.get('buys', 0)
                    swt_sells = swt_data.get('sells', 0)
                    degen_count = degen_data.get('count', 0)
                    degen_buys = degen_data.get('buys', 0)
                    degen_sells = degen_data.get('sells', 0)
                    
                    total_swt_count = swt_count + degen_count
                    total_swt_buys = swt_buys + degen_buys
                    total_swt_sells = swt_sells + degen_sells
                    total_fresh_count = fresh_data.get('count', 0)
                    total_fresh_buys = fresh_data.get('buys', 0)
                    total_fresh_sells = fresh_data.get('sells', 0)
                    print(f"\nBuy Sell & Server Count Data for {ca}")
                    print(f"SWT BUYS: {total_swt_buys}")
                    print(f"SWT SELLS: {total_swt_sells}")
                    print(f"Fresh Buys: {total_fresh_buys}")
                    print(f"Fresh Sells: {total_fresh_sells}")
                    print(f"SWT COUNT: {total_swt_count} || Fresh Count: {total_fresh_count}")
                except Exception as e:
                    print(f"Error processing server count data: {str(e)}")
                    total_swt_count = 0
                    total_swt_buys = 0
                    total_swt_sells = 0
                    total_fresh_count = 0
                    total_fresh_buys = 0
                    total_fresh_sells = 0

                #get last 5 txs (serverdata.py)
                try:
                    last_swt = swt_data.get('latest_descriptions', [])[-1:] if swt_data else []
                    last_degen = degen_data.get('latest_descriptions', [])[-1:] if degen_data else []
                    last_fresh = fresh_data.get('latest_descriptions', [])[-1:] if fresh_data else []
                    print(f"\nLast 3 Descriptions: ")
                    print(last_swt)
                    print(last_fresh)
                    print(last_degen)
                except Exception as e:
                    print(f"Error processing transaction descriptions: {str(e)}")
                    last_swt = []
                    last_degen = []
                    last_fresh = []

                print("DEBUG: About to call TG evaluation")
                #call tg evaluation
                soul_data = {'passes': False, 'dev_holding': 0, 'sniper_percent': 0, 'scans': 0}
                try:
                    soul_data = await self.soul_scanner_bot.send_and_receive_message(ca) or soul_data
                    if soul_data:
                        try:
                            holder_count = unique_bd_data.get('holders', 0)
                            #top_hold = soul_data['top_percentage']
                            dev_holding = soul_data.get('dev_holding', 0)
                            sniper_percent = soul_data.get('sniper_percent', 0)
                            scans = soul_data.get('scans', 0)

                            tg_metrics = {
                                'token_migrated': False,
                                'holding_percentage': None,
                                'holder_count': holder_count,
                                #'top_holding_percentage': top_hold,
                                'dev_holding_percentage': dev_holding,
                                'sniper_percent': sniper_percent,
                                'scans': scans
                            }
                    
                            if soul_data.get('passes', False):
                                print(f"\nSOUL SCANNER TEST PASSED FOR: {ca}")
                            else:
                                print(f"Soul Scanner Failed")
                        except Exception as e:
                            print(f"Error processing soul scanner data: {str(e)}")
                            dev_holding = 0
                            sniper_percent = 0
                            scans = 0
                            tg_metrics = {
                                'token_migrated': False,
                                'holding_percentage': None,
                                'holder_count': holder_count,
                                'dev_holding_percentage': 0,
                                'sniper_percent': 0,
                                'scans': 0
                            }
                except Exception as e:
                    print(f"Error during soul scanner: {str(e)}")
                    dev_holding = 0
                    sniper_percent = 0
                    scans = 0
                    tg_metrics = {
                        'token_migrated': False,
                        'holding_percentage': None,
                        'holder_count': holder_count,
                        'dev_holding_percentage': 0,
                        'sniper_percent': 0,
                        'scans': 0
                    }
                    
                bundle_data = {'passes': False}
                try:
                    bundle_data = await self.bundle_bot.send_and_receive_message(ca) or bundle_data
                    if bundle_data and bundle_data.get('passes', False):
                            #await self.rickbot_webhook.full_send_ca_to_alefdao(ca)
                            #await self.slime_alert.send_message(ca)
                            print(f"\nBundle bot PASSED FOR: {ca}")
                            if isinstance(bundle_data['token_bonded'], bool):
                                tg_metrics['token_migrated'] = bundle_data['token_bonded']
                                print(f"Token Migrated to Dex!")
                            else:
                                print(f"Token on pump!")
                            
                            #tg_metrics['holding_percentage'] = ['holding_percentage']
                            #if bundle_data['token_bonded']:
                                #if isinstance(bundle_data['token_bonded'], bool):
                                    #tg_metrics['token_migrated'] = bundle_data['token_bonded']
                                    #print(f"Token Migrated")
                                #else:
                                    #print(F"Token On Pump")
                            #else:
                                #await self.rickbot_webhooks.conditional_send_ca_to_alefdao(ca)
                                #await self.slime_alert.send_message(ca)
                            
                except Exception as e:
                    print(f"Bundle Bot Error: {str(e)}")

                try:
                    if soul_data.get('passes', False) and bundle_data.get('passes', False):
                        await self.rickbot_webhook.full_send_ca_to_alefdao(ca)
                        #await self.slime_alert.send_message(ca)
                    elif soul_data.get('passes', False) or bundle_data.get('passes', False):
                        await self.rickbot_webhook.conditional_send_ca_to_alefdao(ca)
                except Exception as e:
                    print(f"Error sending to webhook: {str(e)}")

                try:
                    print(f"Holder Count: {tg_metrics['holder_count']}")
                    #print(f"Top Holders hold total of: {tg_metrics['top_holding_percentage']} %")
                    print(f"Dev holds: {tg_metrics['dev_holding_percentage']} %" )
                    print(f"Sniper Percent: {tg_metrics['sniper_percent']}")
                except Exception as e:
                    print(f"Error printing TG metrics: {str(e)}")

                print("DEBUG: About to check dex paid")
                #dex paid check
                dex_paid = False
                try:
                    dex_paid = await self.wallet_pnl_tg.send_and_recieve_message_dex_paid(ca) or False
                    print(f"Dex Paid? {dex_paid}")
                except Exception as e:
                    print(f"Error checking dex paid: {str(e)}")
                    
                #get dex chat .png
                """
                dex_chart_data = await self.wallet_pnl_tg.send_and_recieve_dex_chart(ca)
                if dex_chart_data:
                    chart_image = dex_chart_data['image_data']
                """

                print("DEBUG: About to check token age")
                #token age
                bonded_time = {'value': 0, 'unit': 'minutes'}
                try:
                    bonded_time = await self.token_age.process_pair_age(ca) or bonded_time
                    if bonded_time:
                        age_value = bonded_time.get('value', 0)
                        age_unit = bonded_time.get('unit', 'minutes')
                        age_str = f"{age_value} {age_unit}"
                        print(f"Bonded time: {age_str}")
                    else:
                        print("No bonded time data available, using default")
                        age_value = 0
                        age_unit = 'minutes'
                        age_str = "0 minutes"
                except Exception as e:
                    print(f"Error processing bonded time: {str(e)}")
                    age_value = 0
                    age_unit = 'minutes'
                    age_str = "0 minutes"
                
                true_age_minutes = 0
                try:
                    true_age_minutes = await self.true_age.get(ca) or 0
                    if true_age_minutes:
                        # Convert to appropriate units
                        if true_age_minutes >= 1440:  # 24 hours in minutes
                            days = true_age_minutes // 1440
                            true_age = {'value': days, 'unit': 'days'}
                            print(f"True age: {days} days")
                        elif true_age_minutes >= 60:
                            hours = true_age_minutes // 60
                            true_age = {'value': hours, 'unit': 'hours'}
                            print(f"True age: {hours} hours")
                        else:
                            true_age = {'value': true_age_minutes, 'unit': 'minutes'}
                            print(f"True age: {true_age_minutes} minutes")
                    else:
                        print("No true age data available, using default")
                        true_age = {'value': 0, 'unit': 'minutes'}
                except Exception as e:
                    print(f"Error processing true age: {str(e)}")
                    true_age = {'value': 0, 'unit': 'minutes'}

                time_to_bond_minutes = 0
                try:
                    # Convert bonded_time to minutes if it's a dictionary with value and unit
                    if isinstance(bonded_time, dict) and 'value' in bonded_time and 'unit' in bonded_time:
                        bonded_time_value = bonded_time['value']
                        bonded_time_unit = bonded_time['unit'].lower()
                        
                        if bonded_time_unit == 'minutes':
                            bonded_time_minutes = bonded_time_value
                        elif bonded_time_unit == 'hours':
                            bonded_time_minutes = bonded_time_value * 60
                        elif bonded_time_unit == 'days':
                            bonded_time_minutes = bonded_time_value * 1440  # 24 * 60
                        else:
                            bonded_time_minutes = 0
                    else:
                        bonded_time_minutes = 0
                    
                    # Only calculate the difference if both values are positive
                    if true_age_minutes > 0 and bonded_time_minutes > 0:
                        time_to_bond_minutes = max(0, true_age_minutes - bonded_time_minutes)
                        print(f"Time to bond: {time_to_bond_minutes} minutes")
                    else:
                        time_to_bond_minutes = 0
                        print("Cannot calculate time to bond - using default value of 0 minutes")
                except Exception as e:
                    print(f"Error calculating time to bond: {str(e)}")
                    time_to_bond_minutes = 0  # Default to 0 if calculation fails



                print("DEBUG: About to analyze holders")
                total_held = 0
                holders_over_5 = 0
                holder_criteria = False
                wallet_analysis = {}
                self.wallet_analysis = None
                try:
                    holder_data = await self.get_top_holders.calculate_holder_value(ca, price)
                    if holder_data and isinstance(holder_data, tuple) and len(holder_data) == 2:
                        holder_values, holder_evaluation = holder_data
                        if holder_values and isinstance(holder_values, dict) and 'metadata' in holder_values:
                            metadata = holder_values.get('metadata', {})
                            if metadata:
                                supply = metadata.get('supply', 0)
                                # Validate the values
                                total_held = metadata.get('total_percentage_held', 0)
                                if total_held > 100:  # Sanity check
                                    print(f"Warning: Invalid total_held value: {total_held}%, capping at 100%")
                                    total_held = 100
                                    
                                holders_over_5 = metadata.get('holders_over_5_percent', 0)
                                if holders_over_5 > 10:  # Sanity check for reasonable max
                                    print(f"Warning: Suspicious holders_over_5: {holders_over_5}, capping at 10")
                                    holders_over_5 = 10

                                #check criteria to run top wallet pnl analysis
                                if soul_data.get('passes', False) and holders_over_5 < 4 and dev_holding < 5:
                                    holder_criteria = True
                                    if holder_criteria:
                                        wallet_analysis = {}
                                        wallets_processed = 0
                                    #Tonly then run below analysis
                                        print("\nTop Wallet Performance Analysis:")
                                        print("-" * 50)
                                        # Process top 4 wallets excluding metadata
                                        wallets_processed = 0
                                        for wallet_address, wallet_info in holder_values.items():
                                            if wallet_address != 'metadata' and wallets_processed < 4:
                                                try:
                                                    wallet_pnl = await self.wallet_pnl.calculate_pnl(wallet_address)
                                                    if wallet_pnl and isinstance(wallet_pnl, dict):  # Make sure wallet_pnl is not None and is a dict
                                                        wallet_analysis[wallet_address] = {
                                                            'pnl': wallet_pnl.get('pnl', 0),  # Use .get() to handle missing keys
                                                            'tokens_traded': wallet_pnl.get('tokens_traded', 0),
                                                            'wins': wallet_pnl.get('trades_won', 0),
                                                            'losses': wallet_pnl.get('trades_loss', 0),
                                                            'avg_entry': wallet_pnl.get('average_entry_per_trade', 0) if wallet_pnl.get('average_entry_per_trade', 0) > 0 else None
                                                        }
                                                        wallets_processed += 1  # Increment counter by 1
                                                except Exception as e:
                                                    print(f"Error processing wallet PNL for {wallet_address}: {str(e)}")
                                self.wallet_analysis = wallet_analysis if holder_criteria else None
                except Exception as e:
                    print(f"Error in holder analysis: {str(e)}")
                                                    
                print("DEBUG: About to process transactions")
                all_transactions = []

                # Add transactions from each source
                try:
                    if swt_data and swt_data.get('latest_descriptions', []):
                        all_transactions.extend(swt_data.get('latest_descriptions', [])[-1:])
                    if degen_data and degen_data.get('latest_descriptions', []):
                        all_transactions.extend(degen_data.get('latest_descriptions', [])[-1:])
                    if fresh_data and fresh_data.get('latest_descriptions', []):
                        all_transactions.extend(fresh_data.get('latest_descriptions', [])[-1:])

                    # Format for webhook
                    if all_transactions:
                        tx_summary = "\n".join([f"• {tx}" for tx in all_transactions])
                    else:
                        tx_summary = "No recent transactions"
                except Exception as e:
                    print(f"Error processing transactions: {str(e)}")
                    all_transactions = []
                    tx_summary = "Error processing transactions"

                try:
                    channel_metrics = {
                        'swt': {
                            'channels': swt_data.get('channels', {}),
                            'total_count': total_swt_count,
                            'total_buys': total_swt_buys,
                            'total_sells': total_swt_sells
                        },
                        'fresh': {
                            'channels': fresh_data.get('channels', {}),
                            'total_count': total_fresh_count,
                            'total_buys': total_fresh_buys,
                            'total_sells': total_fresh_sells
                        },
                        'degen': {
                            'channels': degen_data.get('channels', {}),
                            'total_count': degen_count,
                            'total_buys': degen_buys,
                            'total_sells': degen_sells
                        }
                    }

                    channels_ca_found_in = {}
                    for channel_name, data in swt_data.get('channels', {}).items():
                        if data.get('buys', 0) > 0:
                            channels_ca_found_in[channel_name] = data.get('buys', 0)
                    try:
                        if degen_data.get('channels', {}).get('Degen', {}).get('buys', 0) > 0:
                            channels_ca_found_in['Degen'] = degen_data.get('channels', {}).get('Degen', {}).get('buys', 0)
                    except:
                        pass
                    for channel_name, data in fresh_data.get('channels', {}).items():
                        if data.get('buys', 0) > 0:
                            channels_ca_found_in[channel_name] = data.get('buys', 0)

                    channel_text = "No active channels yet" if not channels_ca_found_in else "\n".join([f"• {channel} ({amount:.2f}sol)" for channel, amount in channels_ca_found_in.items() if amount > 0])                
                except Exception as e:
                    print(f"Error processing channel metrics: {str(e)}")
                    channel_text = "Error processing channel data"

                print("DEBUG: About to calculate scores")
                #----------------------------------------------------------------------------------
                holder_score = {}
                try:
                    holder_score = await self.holderscore.calculate_score(
                        token_age=true_age,
                        holder_count=holder_count,
                        top10holds=total_held,
                        holdersover5percent=holders_over_5,
                        devholds=dev_holding,
                        sniper_percent=sniper_percent,
                        wallet_data=wallet_analysis if holder_criteria else None
                    ) or {'total_score': 0, 'holder_count_age_confluence': 0, 'holder_security': 0, 'wallet_score': 0}
                except Exception as e:
                    print(f"Error calculating holder score: {str(e)}")
                    holder_score = {'total_score': 0, 'holder_count_age_confluence': 0, 'holder_security': 0, 'wallet_score': 0}

                tokenomic_score, tokenomic_breakdown = 0, {}
                try:
                    m30_vol = m30_vol if isinstance(m30_vol, (int, float)) else 0
                    m30_vol_change = m30_vol_change if isinstance(m30_vol_change, (int, float)) else 0
                    m5_vol = m5_vol if isinstance(m5_vol, (int, float)) else 0
                    trade_percent_change_30m = trade_percent_change_30m if isinstance(trade_percent_change_30m, (int, float)) else 0
                    buy_percent_change_30m = buy_percent_change_30m if isinstance(buy_percent_change_30m, (int, float)) else 0
                    sell_percent_change_30m = sell_percent_change_30m if isinstance(sell_percent_change_30m, (int, float)) else 0
                    new_unique_wallet_count_30m = new_unique_wallet_count_30m if isinstance(new_unique_wallet_count_30m, (int, float)) else 0
                    new_unique_wallet_count_1h = new_unique_wallet_count_1h if isinstance(new_unique_wallet_count_1h, (int, float)) else 0
                    new_unique_wallet_percent_change_30m = new_unique_wallet_percent_change_30m if isinstance(new_unique_wallet_percent_change_30m, (int, float)) else 0
                    new_unique_wallet_percent_change_1h = new_unique_wallet_percent_change_1h if isinstance(new_unique_wallet_percent_change_1h, (int, float)) else 0
                    holder_count = holder_count if isinstance(holder_count, (int, float)) else 0
                    tokenomic_score, tokenomic_breakdown = await self.tokenomicscore.calculate_tokenomic_score(
                        token_age=true_age,
                        marketcap=marketcap,
                        m30_vol=m30_vol,
                        m30_vol_change=m30_vol_change,
                        liquidity=liquidity,
                        total_trade_change=trade_percent_change_30m,
                        buys_change=buy_percent_change_30m,
                        sells_change=sell_percent_change_30m,
                        total_unique_wallets_30m=new_unique_wallet_count_30m,
                        total_unique_wallets_1h=new_unique_wallet_count_1h,
                        unique_wallet_change_30m=new_unique_wallet_percent_change_30m,
                        unique_wallet_change_1h=new_unique_wallet_percent_change_1h,
                        holder_count=holder_count,
                        m5_vol=m5_vol
                    ) or (0, {'total_score': 0, 'volume_marketcap_liquidity_confluence': 0, 'm30_age_volume_confluence': 0, 
                            'm5_age_volume_confluence': 0, 'total_trades_buy_confluence': 0, 'buying_pressure': 0, 'wallet_growth': 0})
                except Exception as e:
                    print(f"Error calculating tokenomic score: {str(e)}")
                    tokenomic_score, tokenomic_breakdown = 0, {'total_score': 0, 'volume_marketcap_liquidity_confluence': 0, 'm30_age_volume_confluence': 0,
                                                            'm5_age_volume_confluence': 0, 'total_trades_buy_confluence': 0, 'buying_pressure': 0, 'wallet_growth': 0}

                trust_score, trust_breakdown = 0, {}
                try:
                    trust_score, trust_breakdown = await self.trustscore.calculate_trust_score(
                        token_age=true_age,
                        server_buys=total_swt_buys + total_fresh_buys,
                        server_sells=total_swt_sells + total_fresh_sells,
                        server_count=total_swt_count + total_fresh_count,
                        has_tg=telegram is not None,
                        has_x=twitter is not None,
                        dexpaid=dex_paid,
                        soulscannerpass=soul_data.get('passes', False),
                        bundlebotpass=bundle_data.get('passes', False),
                        buys_change=buy_percent_change_30m,
                        sells_change=sell_percent_change_30m
                    ) or (0, {'total_score': 0, 'server_buy_sell_pool_buy_sells_confluence': 0, 'age_server_count_confluence': 0,
                            'security_evaluation': 0, 'server_activity_evaluation': 0, 'social_presence_evaluation': 0})
                except Exception as e:
                    print(f"Error calculating trust score: {str(e)}")
                    trust_score, trust_breakdown = 0, {'total_score': 0, 'server_buy_sell_pool_buy_sells_confluence': 0, 'age_server_count_confluence': 0,
                                                    'security_evaluation': 0, 'server_activity_evaluation': 0, 'social_presence_evaluation': 0}

                # Calculate penalties
                penalties = 0
                try:
                    penalties = await self.penalizescore.calculate_penalties(
                        token_age=true_age,
                        liquidity=liquidity,
                        server_buys=total_swt_buys + total_fresh_buys,
                        server_sells=total_swt_sells + total_fresh_sells,
                        has_tg=telegram is not None,
                        has_x=twitter is not None,
                        holdersover5percent=holders_over_5,
                        sniper_percent=sniper_percent,
                        soulscannerpasses=soul_data.get('passes', False),
                        bundlebotpasses=bundle_data.get('passes', False),
                        dex_paid=dex_paid
                    ) or 0
                except Exception as e:
                    print(f"Error calculating penalties: {str(e)}")

                # Calculate composite score
                total_score_before_penalties = 0

                if holder_score and isinstance(holder_score, dict):
                    total_score_before_penalties += holder_score.get('total_score', 0)

                if tokenomic_breakdown and isinstance(tokenomic_breakdown, dict):
                    total_score_before_penalties += tokenomic_breakdown.get('total_score', 0)

                if trust_breakdown and isinstance(trust_breakdown, dict):
                    total_score_before_penalties += trust_breakdown.get('total_score', 0)

                final_score = max(0, total_score_before_penalties - (penalties or 0))

                weekly_stats = None
                tokens_created = 0
                rug_count = 0
                successful_count = 0
                rug_rate = 0
                """
                #Twitter Analysis
                if final_score >= 75:
                    print(f"Running Twitter Analysis for: {ca}")
                    #extract twit user for twitter processing
                    if twitter:
                        username = twitter.split("/")[-1]
                        print(f"\nRunning Searchbar Analysis for: {ca} as well as token account analysis for @{username}")
                """
                
                dev_data = await self.dev_history.dev_report(ca=ca, token_name=token_name)
                if not dev_data:
                    dev_data = {
                        'weekly_activity': [{}],
                        'general_stats': {
                            'total_tokens_created': 0,
                            'total_rugs': 0,
                            'total_successful': 0,
                            'rug_rate': 0
                        }
                    }
                

                weekly_stats = dev_data['weekly_activity'][0] if dev_data['weekly_activity'] else {}
                tokens_created = dev_data['general_stats'].get('total_tokens_created', 0)
                rug_count = dev_data['general_stats'].get('total_rugs', 0)
                successful_count = dev_data['general_stats'].get('total_successful', 0)
                rug_rate = dev_data['general_stats'].get('rug_rate', 0)
                

                supply = await self.sup.supply(ca)
                ohlcv_data = await self._get_ohlcv_d(age=true_age_minutes, pair_address=pool_address)
                if not ohlcv_data:
                    print(f"Fatal error in getting ohlcv")

                try:
                    sr_data = await self.sr.get_sr_zones(token_name, ca, supply, ohlcv_data)
                    if sr_data and 'sr_levels' in sr_data:
                        sr_levels = sr_data['sr_levels']
                        main_support = sr_levels['support']['mean']
                        main_resistance = sr_levels['resistance']['mean']
                        support_strength = sr_levels.get('support_strength', 0) * 100
                        resistance_strength = sr_levels.get('resistance_strength', 0) * 100
                        print(f"Successfully obtained SR levels: Support=${main_support:.2f}, Resistance=${main_resistance:.2f}")
                    else:
                        print("Failed to get valid SR levels data")
                        # Default values if SR data is not available
                        main_support = 0
                        main_resistance = 0
                        support_strength = 0
                        resistance_strength = 0
                except Exception as e:
                    print(f"Error processing SR levels: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    # Default values in case of error
                    main_support = 0
                    main_resistance = 0
                    support_strength = 0
                    resistance_strength = 0
                
                ob_data = {}
                ob_entry = False
                ob_top = 0
                ob_bottom = 0
                ob_volume = 0
                ob_strength = 0

                try:
                    if pool_address:
                        print("\nFetching Order Block data...")
                        ob_data = await self.ob.update_order_blocks(
                            ca, 
                            pool_address, 
                            token_name, 
                            supply, 
                            ohlcv_data,
                            short_timeframes=self.short_timeframes,
                            longer_timeframes=self.longer_timeframes
                        )
                        
                        if ob_data:
                            print("Successfully retrieved Order Block data")
                            
                            # Check if we're in an OB zone
                            if hasattr(self.ob, 'active_obs') and self.ob.active_obs:
                                # Get closest OB to current price
                                closest_ob = None
                                min_distance = float('inf')
                                
                                for ob in self.ob.active_obs:
                                    # Use marketcap as the price metric
                                    ob_mid = (ob['top'] + ob['bottom']) / 2
                                    distance = abs(marketcap - ob_mid) / ob_mid
                                    
                                    if distance < min_distance:
                                        min_distance = distance
                                        closest_ob = ob
                                
                                if closest_ob:
                                    ob_top = closest_ob['top']
                                    ob_bottom = closest_ob['bottom']
                                    ob_volume = closest_ob.get('volume', 0)
                                    ob_strength = closest_ob.get('strength', 0)
                                    
                                    # Check if we're in this OB
                                    if ob_bottom * 0.98 <= marketcap <= ob_top * 1.02:
                                        ob_entry = True
                                        print(f"Token is currently in an Order Block zone: ${ob_bottom:.2f} - ${ob_top:.2f}")
                                    else:
                                        print(f"Closest Order Block: ${ob_bottom:.2f} - ${ob_top:.2f}, not in zone")
                                else:
                                    print("No valid Order Blocks found")
                        else:
                            print("No Order Block data available")
                    else:
                        print("No pool address available for Order Block analysis")
                except Exception as e:
                    print(f"Error processing Order Block data: {str(e)}")
                    import traceback
                    traceback.print_exc()
                
                rls = 0
                if all([scans, true_age_minutes, liquidity, m5_vol]):
                    raw_rls = (scans / true_age_minutes) * ((liquidity + m5_vol) / 2)
                    rls = math.log10(raw_rls + 1)


                
                try:
                    await self.ma_webhooks.multialert_webhook(
                        token_name=token_name,
                        ca=ca,
                        websites_data=websites_data,
                        marketcap=marketcap,
                        m5_vol=m5_vol,
                        liquidity=liquidity,
                        telegram=telegram,
                        twitter=twitter,
                        photon_link=photon_link,
                        bull_x_link=bull_x_link,
                        dex_link=dexscreener_link,
                        swt_count=total_swt_count,
                        swt_buys=total_swt_buys,
                        swt_sells=total_swt_sells,
                        fresh_count=total_fresh_count,
                        fresh_buys=total_fresh_buys,
                        fresh_sells=total_fresh_sells,
                        last_3_tx=all_transactions,
                        holder_count=holder_count,
                        dev_holding_percentage=dev_holding,
                        token_migrated=tg_metrics.get('token_migrated', False),
                        passes_soulscanner=soul_data.get('passes', False),
                        passes_bundlebot=bundle_data.get('passes', False) if bundle_data else False,
                        dex_paid=dex_paid,
                        token_age=true_age,
                        time_to_bond=bonded_time if tg_metrics.get('token_migrated') else "N/A",
                        top_10_holding_percentage=total_held,
                        holders_over_5=holders_over_5,
                        wallet_data=wallet_analysis if holder_criteria else None,
                        m30_vol=m30_vol,
                        m30_vol_change=m30_vol_change,
                        new_unique_wallets_30m=new_unique_wallet_count_30m,
                        new_unique_wallet_30m_change=new_unique_wallet_percent_change_30m,
                        trade_change_30m=trade_percent_change_30m,
                        buy_change_30m=buy_percent_change_30m,
                        sell_change_30m=sell_percent_change_30m,
                        channel_text=channel_text,
                        sniper_percent=sniper_percent,
                        dev_token_created=tokens_created,
                        dev_rug_count=rug_count,
                        dev_successful_count=successful_count,
                        dev_rug_rate=rug_rate,
                        support=main_support,
                        support_strength=support_strength,
                        resistance=main_resistance,
                        resistance_strength=resistance_strength,
                        ob_top=ob_top,
                        ob_bottom=ob_bottom,
                        ob_volume=ob_volume,
                        ob_strength=ob_strength,
                        scans=scans,
                        comp_score=final_score
                    )
                    print("DEBUG: Sent multi-alert webhook")
                except Exception as e:
                    print(f"Error sending multi-alert webhook: {str(e)}")
                    
                try:
                    await self.ma_webhooks.score_webhook(
                        token_name=token_name,
                        ca=ca,
                        
                        holder_total=holder_score.get('total_score', 0),
                        holder_age_confluence=holder_score.get('holder_count_age_confluence', 0),
                        holder_security=holder_score.get('holder_security', 0),
                        holder_wallet_analysis=holder_score.get('wallet_score', 0),
                        
                        tokenomic_total=tokenomic_breakdown.get('total_score', 0),
                        tokenomic_vol_liq=tokenomic_breakdown.get('volume_marketcap_liquidity_confluence', 0),
                        tokenomic_30m_vol=tokenomic_breakdown.get('m30_age_volume_confluence', 0),
                        tokenomic_5m_vol=tokenomic_breakdown.get('m5_age_volume_confluence', 0),
                        tokenomic_trade_confluence=tokenomic_breakdown.get('total_trades_buy_confluence', 0),
                        tokenomic_buy_pressure=tokenomic_breakdown.get('buying_pressure', 0),
                        tokenomic_wallet_growth=tokenomic_breakdown.get('wallet_growth', 0),
                        
                        trust_total=trust_breakdown.get('total_score', 0),
                        trust_bs_confluence=trust_breakdown.get('server_buy_sell_pool_buy_sells_confluence', 0),
                        trust_age_count=trust_breakdown.get('age_server_count_confluence', 0),
                        trust_security=trust_breakdown.get('security_evaluation', 0),
                        trust_activity=trust_breakdown.get('server_activity_evaluation', 0),
                        trust_social=trust_breakdown.get('social_presence_evaluation', 0),
                        
                        total_before_penalties=total_score_before_penalties,
                        penalties=penalties,
                        final_score=final_score
                    )
                    print("DEBUG: Sent score webhook")
                except Exception as e:
                    print(f"Error sending score webhook: {str(e)}")

                try:
                    #if final_score >= 60 and pool_address:
                        #marketcap_task = asyncio.create_task(self.mc_monitor.monitor_marketcap(token_name, ca, pool_address, true_age_minutes))
                        #print("DEBUG: Created marketcap monitoring task")
                    

                    if not hasattr(self, 'background_tasks'):
                        self.background_tasks = []
                    
                    #if final_score >= 48 and pool_address and true_age_minutes <= 60:
                        #self.background_tasks.append(marketcap_task)

                    data_task = asyncio.create_task(self.index_data(
                        token_name=token_name,
                        ca=ca,
                        initial_marketcap=marketcap,
                        initial_m5_vol=m5_vol,
                        m30_vol=m30_vol,
                        m30_vol_change=m30_vol_change,
                        m30_buys=m30_buys,
                        m30_sells=m30_sells,
                        m30_price_change=m30_price_change,
                        m30_trades=m30_trades,
                        initial_liquidity=liquidity,
                        dex_paid=dex_paid,
                        sniper_percent=sniper_percent,
                        scans=scans,
                        passes_soul=soul_data['passes'],
                        passes_bundle=bundle_data['passes'],
                        initial_holder_count=holder_count,
                        migrated=tg_metrics.get('token_migrated', False),
                        top_holding_percentage=total_held,
                        holders_over_5_count=holders_over_5,
                        dev_holding_percentage=dev_holding,
                        trade_30m_change_percent=trade_percent_change_30m,
                        buy_30m_change_percent=buy_percent_change_30m,
                        sell_30m_change_percent=sell_percent_change_30m,
                        unique_wallet_30m_count=new_unique_wallet_count_30m,
                        unique_wallet_30m_change_percentage=new_unique_wallet_percent_change_30m,
                        has_tg=telegram is not None,
                        has_x=twitter is not None,
                        server_swt_mentions=total_swt_count,
                        server_fresh_mentions=total_fresh_count,
                        swt_buys=total_swt_buys,
                        swt_sells=total_swt_sells,
                        fresh_buys=total_fresh_buys,
                        fresh_sells=total_fresh_sells,
                        token_age=true_age_minutes,
                        time_to_bond=time_to_bond_minutes,
                        comp_score=final_score,
                        total_swt_sol_amount=swt_data.get('total_sol_amount', 0),
                        total_fresh_sol_amount=fresh_data.get('total_sol_amount', 0),
                        swt_wallets=swt_data.get('unique_wallets', 0),
                        fresh_wallets=fresh_data.get('unique_wallets', 0),
                        dev_token_created_count=tokens_created,
                        dev_rug_count=rug_count,
                        dev_successful_count=successful_count,
                        rls=rls,
                        website_count=websites_data.get('count', 0) if websites_data else 0,
                        channels_data=channels_ca_found_in
                    ))
                    self.background_tasks.append(data_task)

                    self.background_tasks = [task for task in self.background_tasks if not task.done()]
                    print("DEBUG: MultiAlert processing completed successfully")
                except Exception as e:
                    print(f"Error creating background tasks: {str(e)}")
        
        except Exception as e:
            print(f"Error in running check for multialert: {str(e)}")
            import traceback
            print(traceback.format_exc())

    async def calculate_composite_score(holder_score, tokenomic_score, trust_score):
        try:
            composite_score = holder_score + tokenomic_score + trust_score
            return composite_score
        except Exception as e:
            print(str(e))    
            return None
        
    async def _get_ohlcv_d(self, age, pair_address):
        try:
            if age < 60:
                for tf in self.short_timeframes:
                    print(f"\nTrying Timeframe: {tf}")
                    ohlcv_data = await self.o.fetch(timeframe=tf, pair_address=pair_address)
                    if not ohlcv_data or (isinstance(ohlcv_data, dict) and 'message' in ohlcv_data and 'Internal server error' in ohlcv_data.get('message', '')):
                        print(f"Failed to get OHLCV")
                        continue  # Try next timeframe
                    if isinstance(ohlcv_data, dict) and ohlcv_data:
                        return ohlcv_data
            else:
                for tf in self.longer_timeframes:
                    print(f"\nTrying Longer Timeframe: {tf}")
                    ohlcv_data = await self.o.fetch(timeframe=tf, pair_address=pair_address)
                    if not ohlcv_data or (isinstance(ohlcv_data, dict) and 'message' in ohlcv_data and 'Internal server error' in ohlcv_data.get('message', '')):
                        print(f"Failed to get OHLCV")
                        continue  # Try next timeframe
                    if isinstance(ohlcv_data, dict) and ohlcv_data:
                        return ohlcv_data
            return None
        except Exception as e:
            print(f"Error in _get_ohlcv_d: {str(e)}")
            return None
        
    async def apply_penalities(composite_score, penalties):
        try:
            final_score = max(0, composite_score - penalties)
            return final_score
        except Exception as e:
            print(f"{str(e)}")
            return None

    async def index_data(self, 
                token_name,
                ca,
                initial_marketcap,
                initial_m5_vol,
                m30_vol,
                m30_vol_change,
                m30_buys,
                m30_sells,
                m30_price_change,
                m30_trades,
                initial_liquidity,
                dex_paid,
                sniper_percent,
                scans,
                passes_soul,
                passes_bundle,
                initial_holder_count,
                migrated,
                top_holding_percentage,
                holders_over_5_count,
                dev_holding_percentage,
                trade_30m_change_percent,
                buy_30m_change_percent,
                sell_30m_change_percent,
                unique_wallet_30m_count,
                unique_wallet_30m_change_percentage,
                has_tg,
                has_x,
                server_swt_mentions,
                server_fresh_mentions,
                swt_buys,
                swt_sells,
                total_swt_sol_amount,
                total_fresh_sol_amount,
                fresh_buys,
                fresh_sells,
                token_age,
                time_to_bond,
                comp_score,
                swt_wallets,
                fresh_wallets,
                dev_token_created_count,
                dev_rug_count,
                dev_successful_count,
                rls,
                website_count=0,
                channels_data=None):

        try:
            # Convert token age to minutes if it's not already
            time_to_bond_minutes = time_to_bond  # Already in minutes
            
            # Calculate total social count (websites + social media)
            total_social_count = website_count
            if has_tg:
                total_social_count += 1
            if has_x:
                total_social_count += 1
                
            # Initialize all channel amounts to 0
            legend_amount = 0
            kol_regular_amount = 0
            kol_alpha_amount = 0
            smart_amount = 0
            degen_amount = 0
            whale_amount = 0
            challenge_amount = 0
            high_freq_amount = 0
            insider_amount = 0
            fresh_amount = 0
            fresh_1h_amount = 0
            fresh_5sol_1m_mc_amount = 0

            # Use the channels_data parameter which contains the channels_ca_found_in dictionary
            try:
                if channels_data and isinstance(channels_data, dict):
                    for channel_name, amount in channels_data.items():
                        if "Legend" in channel_name:
                            legend_amount = amount
                        elif "Kol Regular" in channel_name:
                            kol_regular_amount = amount
                        elif "Kol Alpha" in channel_name:
                            kol_alpha_amount = amount
                        elif "Smart" in channel_name:
                            smart_amount = amount
                        elif "Whale" in channel_name:
                            whale_amount = amount
                        elif "Challenge" in channel_name:
                            challenge_amount = amount
                        elif "High Freq" in channel_name:
                            high_freq_amount = amount
                        elif "Insider" in channel_name:
                            insider_amount = amount
                        elif "Degen" in channel_name:
                            degen_amount = amount
                        elif "Fresh 5sol 1m MC" in channel_name:
                            fresh_5sol_1m_mc_amount = amount
                        elif "Fresh 1h" in channel_name:
                            fresh_1h_amount = amount
                        elif "Fresh" in channel_name:  # Must be after other Fresh checks
                            fresh_amount = amount
                else:
                    # Fallback to set-based detection
                    if ca in self.legend_cas:
                        legend_amount = 1.0
                    if ca in self.kol_regular_cas:
                        kol_regular_amount = 1.0
                    if ca in self.kol_alpha_cas:
                        kol_alpha_amount = 1.0
                    if ca in self.smart_cas:
                        smart_amount = 1.0
                    if ca in self.degen_cas:
                        degen_amount = 1.0
                    if ca in self.whale_cas:
                        whale_amount = 1.0
                    if ca in self.challenge_cas:
                        challenge_amount = 1.0
                    if ca in self.high_freq_cas:
                        high_freq_amount = 1.0
                    if ca in self.insider_wallet_cas:
                        insider_amount = 1.0
                    if ca in self.fresh_cas:
                        fresh_amount = 1.0
                    if ca in self.fresh_1h_cas:
                        fresh_1h_amount = 1.0
                    if ca in self.fresh_5sol_1m_mc_cas:
                        fresh_5sol_1m_mc_amount = 1.0
                        
                # Convert values to float for consistency
                legend_amount = float(legend_amount) if legend_amount is not None else 0.0
                kol_regular_amount = float(kol_regular_amount) if kol_regular_amount is not None else 0.0
                kol_alpha_amount = float(kol_alpha_amount) if kol_alpha_amount is not None else 0.0
                smart_amount = float(smart_amount) if smart_amount is not None else 0.0
                degen_amount = float(degen_amount) if degen_amount is not None else 0.0
                whale_amount = float(whale_amount) if whale_amount is not None else 0.0
                challenge_amount = float(challenge_amount) if challenge_amount is not None else 0.0
                high_freq_amount = float(high_freq_amount) if high_freq_amount is not None else 0.0
                insider_amount = float(insider_amount) if insider_amount is not None else 0.0
                fresh_amount = float(fresh_amount) if fresh_amount is not None else 0.0
                fresh_1h_amount = float(fresh_1h_amount) if fresh_1h_amount is not None else 0.0
                fresh_5sol_1m_mc_amount = float(fresh_5sol_1m_mc_amount) if fresh_5sol_1m_mc_amount is not None else 0.0
                
                print(f"Channel amounts for {ca}:")
                print(f"Legend: {legend_amount}, Kol Regular: {kol_regular_amount}, Kol Alpha: {kol_alpha_amount}")
                print(f"Smart: {smart_amount}, Whale: {whale_amount}, Challenge: {challenge_amount}")
                print(f"High Freq: {high_freq_amount}, Insider: {insider_amount}, Degen: {degen_amount}")
                print(f"Fresh: {fresh_amount}, Fresh 1h: {fresh_1h_amount}, Fresh 5sol 1m MC: {fresh_5sol_1m_mc_amount}")

            except Exception as e:
                print(f"Error processing channel amounts: {str(e)}")
                import traceback
                traceback.print_exc()
                    
            # Wallet analysis data - initialize with defaults
            top_wallet_avg_pnl = 0
            top_wallet_avg_trade_count = 0
            top_wallet1_pnl = 0
            top_wallet2_pnl = 0
            top_wallet3_pnl = 0
            top_wallet4_pnl = 0
            
            # If wallet analysis data exists, process it
            if hasattr(self, 'wallet_analysis') and self.wallet_analysis:
                wallet_data = self.wallet_analysis
                wallet_count = len(wallet_data)
                if wallet_count > 0:
                    # Calculate average PNL
                    total_pnl = 0
                    total_trades = 0
                    wallets = list(wallet_data.items())
                    
                    # Process up to 4 wallets
                    for i, (wallet_address, data) in enumerate(wallets[:4]):
                        pnl = data.get('pnl', 0)
                        trades = data.get('tokens_traded', 0)
                        total_pnl += pnl
                        total_trades += trades
                        
                        # Assign wallet-specific PNL values
                        if i == 0:
                            top_wallet1_pnl = pnl
                        elif i == 1:
                            top_wallet2_pnl = pnl
                        elif i == 2:
                            top_wallet3_pnl = pnl
                        elif i == 3:
                            top_wallet4_pnl = pnl
                    
                    # Calculate averages
                    if wallet_count > 0:
                        top_wallet_avg_pnl = total_pnl / wallet_count
                        top_wallet_avg_trade_count = total_trades / wallet_count
            
            # Initialize volume and market cap tracking fields (will be updated later)
            # These will be properly updated by the background tasks when intervals are reached
            vol_1m_after = None  # Use NULL instead of 0
            vol_3m_after = None
            vol_5m_after = None
            vol_10m_after = None
            mc_3m = None
            mc_8m = None
            mc_15m = None
            hr24_max_mc = None  # Start with NULL, will be updated in real time
            
            # Current timestamp for the alert
            current_time = datetime.now().isoformat()

            # Check if any of the values are coroutines and await them if needed
            if asyncio.iscoroutine(initial_marketcap):
                initial_marketcap = await initial_marketcap
            
            # Handle dev stats specifically
            try:
                # Check if dev_token_created_count is a coroutine
                if asyncio.iscoroutine(dev_token_created_count):
                    dev_token_created_count = await dev_token_created_count
                
                # Check if dev_rug_count is a coroutine
                if asyncio.iscoroutine(dev_rug_count):
                    dev_rug_count = await dev_rug_count
                
                # Check if dev_successful_count is a coroutine
                if asyncio.iscoroutine(dev_successful_count):
                    dev_successful_count = await dev_successful_count
                
                # Convert dev stats to appropriate types with error handling
                try:
                    dev_token_created_count = int(dev_token_created_count) if dev_token_created_count is not None else 0
                except (TypeError, ValueError):
                    print(f"Error converting dev_token_created_count, using default value")
                    dev_token_created_count = 0
                    
                try:
                    dev_rug_count = int(dev_rug_count) if dev_rug_count is not None else 0
                except (TypeError, ValueError):
                    print(f"Error converting dev_rug_count, using default value")
                    dev_rug_count = 0
                    
                try:
                    dev_successful_count = int(dev_successful_count) if dev_successful_count is not None else 0
                except (TypeError, ValueError):
                    print(f"Error converting dev_successful_count, using default value")
                    dev_successful_count = 0
                
                # Log dev stats for debugging
                print(f"DEV STATS: Created: {dev_token_created_count}, Rugs: {dev_rug_count}, Successful: {dev_successful_count}")
                
            except Exception as e:
                print(f"Error processing dev stats: {str(e)}")
                dev_token_created_count = 0
                dev_rug_count = 0
                dev_successful_count = 0

            # Convert other values with proper error handling
            try:
                initial_marketcap = float(initial_marketcap) if initial_marketcap is not None else 0.0
            except (TypeError, ValueError):
                print(f"Error converting initial_marketcap, using default value")
                initial_marketcap = 0.0
                
            # Now handle all remaining parameters in a similar way
            try:
                initial_m5_vol = float(initial_m5_vol) if initial_m5_vol is not None else 0.0
            except (TypeError, ValueError):
                initial_m5_vol = 0.0
                
            try:
                m30_vol = float(m30_vol) if m30_vol is not None else 0.0
            except (TypeError, ValueError):
                m30_vol = 0.0
            
            try:
                m30_vol_change = float(m30_vol_change) if m30_vol_change is not None else 0.0
            except (TypeError, ValueError):
                m30_vol_change = 0.0
                
            try:
                m30_buys = float(m30_buys) if m30_buys is not None else 0.0
            except (TypeError, ValueError):
                m30_buys = 0.0
                
            try:
                m30_sells = float(m30_sells) if m30_sells is not None else 0.0
            except (TypeError, ValueError):
                m30_sells = 0.0
                
            try:
                m30_price_change = float(m30_price_change) if m30_price_change is not None else 0.0
            except (TypeError, ValueError):
                m30_price_change = 0.0
                
            try:
                m30_trades = float(m30_trades) if m30_trades is not None else 0.0
            except (TypeError, ValueError):
                m30_trades = 0.0
                
            try:
                initial_liquidity = float(initial_liquidity) if initial_liquidity is not None else 0.0
            except (TypeError, ValueError):
                initial_liquidity = 0.0
                
            try:
                sniper_percent = float(sniper_percent) if sniper_percent is not None else 0.0
            except (TypeError, ValueError):
                sniper_percent = 0.0
                
            try:
                scans = int(scans) if scans is not None else 0
            except (TypeError, ValueError):
                scans = 0
                
            try:
                initial_holder_count = int(initial_holder_count) if initial_holder_count is not None else 0
            except (TypeError, ValueError):
                initial_holder_count = 0
                
            try:
                top_holding_percentage = float(top_holding_percentage) if top_holding_percentage is not None else 0.0
            except (TypeError, ValueError):
                top_holding_percentage = 0.0
                
            try:
                holders_over_5_count = int(holders_over_5_count) if holders_over_5_count is not None else 0
            except (TypeError, ValueError):
                holders_over_5_count = 0
                
            try:
                dev_holding_percentage = float(dev_holding_percentage) if dev_holding_percentage is not None else 0.0
            except (TypeError, ValueError):
                dev_holding_percentage = 0.0
                
            try:
                trade_30m_change_percent = float(trade_30m_change_percent) if trade_30m_change_percent is not None else 0.0
            except (TypeError, ValueError):
                trade_30m_change_percent = 0.0
                
            try:
                buy_30m_change_percent = float(buy_30m_change_percent) if buy_30m_change_percent is not None else 0.0
            except (TypeError, ValueError):
                buy_30m_change_percent = 0.0
                
            try:
                sell_30m_change_percent = float(sell_30m_change_percent) if sell_30m_change_percent is not None else 0.0
            except (TypeError, ValueError):
                sell_30m_change_percent = 0.0
                
            try:
                unique_wallet_30m_count = int(unique_wallet_30m_count) if unique_wallet_30m_count is not None else 0
            except (TypeError, ValueError):
                unique_wallet_30m_count = 0
                
            try:
                unique_wallet_30m_change_percentage = float(unique_wallet_30m_change_percentage) if unique_wallet_30m_change_percentage is not None else 0.0
            except (TypeError, ValueError):
                unique_wallet_30m_change_percentage = 0.0
                
            try:
                token_age = int(token_age) if token_age is not None else 0
            except (TypeError, ValueError):
                token_age = 0
                
            try:
                time_to_bond_minutes = int(time_to_bond_minutes) if time_to_bond_minutes is not None else 0
            except (TypeError, ValueError):
                time_to_bond_minutes = 0
                
            try:
                comp_score = float(comp_score) if comp_score is not None else 0.0
            except (TypeError, ValueError):
                comp_score = 0.0
                
            try:
                rls = float(rls) if rls is not None else 0.0
            except (TypeError, ValueError):
                rls = 0.0

            # Convert boolean values to integers for SQLite
            has_tg = 1 if has_tg else 0
            has_x = 1 if has_x else 0
            dex_paid = 1 if dex_paid else 0
            passes_soul = 1 if passes_soul else 0
            passes_bundle = 1 if passes_bundle else 0
            migrated = 1 if migrated else 0
            
            with sqlite3.connect('memedb.db') as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(multialerts)")
                columns = cursor.fetchall()
                print(f"Table 'multialerts' has {len(columns)} columns")
                
                insert_columns = [
                    'alert_time', 'token_name', 'ca', 'initial_marketcap', 'initial_m5_vol', 
                    'initial_m30_vol', 'm30_vol_change', 'm30_buy_count', 'm30_sell_count', 'm30_price_change', 'm30_trade_count',
                    'initial_liquidity', 'dex_paid', 
                    'sniper_percent', 'scans', 'passes_soul', 'passes_bundle', 
                    'initial_holder_count', 'migrated', 'top_holding_percentage', 
                    'holders_over_5', 'dev_holding_percentage', 'trade_30m_change_percentage',
                    'buy_30m_change_percentage', 'sell_30m_change_percentage', 
                    'unique_wallet_30m_change_percentage', 'unique_wallet_30m_change_count',
                    'has_tg', 'has_x', 'swt_mentions', 'fresh_mentions', 
                    'total_swt_buy_amount', 'total_swt_sell_amount', 
                    'total_fresh_buy_amount', 'total_fresh_sell_amount',
                    'token_age_minutes', 'time_to_bond_minutes', 'score', 
                    'website_count', 'total_social_count', 'dev_token_created_count', 
                    'dev_rug_count', 'dev_successful_count', 
                    'vol_1m', 'vol_3m', 'vol_5m', 'vol_10m',
                    'mc_3m', 'mc_8m', 'mc_15m', 'hr24_max_mc',
                    'top_wallet_avg_pnl', 'top_wallet_avg_trade_count', 
                    'top_wallet1_pnl', 'top_wallet2_pnl', 'top_wallet3_pnl', 'top_wallet4_pnl',
                    'legend_amount', 'kol_regular_amount', 'kol_alpha_amount', 'smart_amount', 
                    'degen_amount', 'whale_amount', 'challenge_amount', 'high_freq_amount', 
                    'insider_amount', 'fresh_amount', 'fresh_1h_amount', 'fresh_5sol_1m_mc_amount',
                    'rls', 'twox'
                ]
                
                # Create SQL insert statement with explicit columns
                column_list = ', '.join(insert_columns)
                value_placeholders = ', '.join(['?' for _ in range(len(insert_columns))])
                insert_sql = f"INSERT OR REPLACE INTO multialerts ({column_list}) VALUES ({value_placeholders})"
                
                # Create a matching values tuple with values in the same order as insert_columns
                values = (
                    current_time, token_name, ca, initial_marketcap, initial_m5_vol, m30_vol, 
                    m30_vol_change, m30_buys, m30_sells, m30_price_change, m30_trades, initial_liquidity, dex_paid, sniper_percent, scans, passes_soul, 
                    passes_bundle, initial_holder_count, migrated, top_holding_percentage, 
                    holders_over_5_count, dev_holding_percentage, trade_30m_change_percent,
                    buy_30m_change_percent, sell_30m_change_percent, 
                    unique_wallet_30m_change_percentage, unique_wallet_30m_count,
                    has_tg, has_x, server_swt_mentions, server_fresh_mentions, 
                    swt_buys, swt_sells, fresh_buys, fresh_sells,
                    token_age, time_to_bond_minutes, comp_score, 
                    website_count, total_social_count, dev_token_created_count, 
                    dev_rug_count, dev_successful_count, 
                    vol_1m_after, vol_3m_after, vol_5m_after, vol_10m_after,  # Pass None for these values
                    mc_3m, mc_8m, mc_15m, hr24_max_mc,  # Pass None for these values
                    top_wallet_avg_pnl, top_wallet_avg_trade_count, 
                    top_wallet1_pnl, top_wallet2_pnl, top_wallet3_pnl, top_wallet4_pnl,
                    legend_amount, kol_regular_amount, kol_alpha_amount, smart_amount, 
                    degen_amount, whale_amount, challenge_amount, high_freq_amount, 
                    insider_amount, fresh_amount, fresh_1h_amount, fresh_5sol_1m_mc_amount,
                    rls, 0  # twox - set to False initially
                )
                cursor.execute(insert_sql, values)
                conn.commit()
                
                print(f"Successfully indexed token {token_name} ({ca}) to db")
                
                asyncio.create_task(self.update_volume_data(ca))
                asyncio.create_task(self.update_marketcap_data(ca))
                
        except Exception as e:
            print(f"Error in DB Indexing: {str(e)}")
            import traceback
            print(traceback.format_exc())

    async def update_volume_data(self, ca):
        """
        Updates volume data at specific intervals after token indexing.
        This function monitors the token age and only updates the DB when
        each specific interval is reached from initial indexing time.
        """
        try:
            # Intervals to check (in minutes)
            intervals = [1, 3, 5, 10]
            completed = set()
            
            # Get the reference time - when this function started running
            # This serves as our "time zero" for all interval calculations
            reference_time = time.time()
            print(f"Starting volume tracking for {ca} at {datetime.fromtimestamp(reference_time).strftime('%H:%M:%S')}")
            
            while len(completed) < len(intervals):
                current_time = time.time()
                # Calculate elapsed time since we started tracking this token
                elapsed_minutes = (current_time - reference_time) / 60
                
                # Check each interval
                for interval in intervals:
                    if interval in completed:
                        continue
                    
                    # Only update if we've reached this interval
                    if elapsed_minutes >= interval:
                        print(f"Reached {interval}m interval for {ca}, updating volume data...")
                        
                        # Get current volume from DexScreener
                        try:
                            dex_data = await self.dex.fetch_token_data_from_dex(ca)
                            if dex_data:
                                volume = dex_data.get('token_5m_vol', 0)
                                
                                # Update DB with the volume at this interval
                                column_name = f"vol_{interval}m"
                                
                                with sqlite3.connect('memedb.db') as conn:
                                    cursor = conn.cursor()
                                    cursor.execute(f"""
                                        UPDATE multialerts 
                                        SET {column_name} = ?
                                        WHERE ca = ?
                                    """, (volume, ca))
                                    conn.commit()
                                    
                                print(f"Updated {column_name} for {ca} with value {volume}")
                                completed.add(interval)
                        except Exception as e:
                            print(f"Error updating volume at {interval}m interval: {str(e)}")
                
                # If we've completed all intervals, exit
                if len(completed) == len(intervals):
                    print(f"All volume intervals completed for {ca}")
                    break
                    
                # Sleep before checking again - shorter sleep to be more accurate with timing
                await asyncio.sleep(10)  # Check every 10 seconds
                
        except Exception as e:
            print(f"Error in update_volume_data: {str(e)}")
            import traceback
            traceback.print_exc()

    async def update_marketcap_data(self, ca):
        """
        Updates marketcap data at specific intervals after token indexing.
        This function monitors time from function start and only updates 
        the DB when each specific interval is reached.
        """
        try:
            # Intervals to check (in minutes)
            intervals = [3, 8, 15]
            completed = set()
            max_mc = 0  # Still track max_mc locally but don't update DB with it
            pool_address = None
            
            # Get the reference time - when this function started running
            # This serves as our "time zero" for all interval calculations
            reference_time = time.time()
            print(f"Starting marketcap tracking for {ca} at {datetime.fromtimestamp(reference_time).strftime('%H:%M:%S')}")
            
            # For 24hr tracking, we'll need to wait a full 24 hours + 20 minutes
            hr24_check_time = reference_time + ((24 * 60 * 60) + (20 * 60))
                
            # Get pool address once for later use
            try:
                dex_data = await self.dex.fetch_token_data_from_dex(ca)
                if dex_data:
                    pool_address = dex_data.get('pool_address')
                    print(f"Found pool address for {ca}: {pool_address}")
            except Exception as e:
                print(f"Error getting pool address: {str(e)}")
            
            # Continue until all intervals are completed and 24hr check is done
            hr24_completed = False
            
            while (len(completed) < len(intervals)) or (not hr24_completed and time.time() < hr24_check_time + 300):
                current_time = time.time()
                # Calculate elapsed time since we started tracking this token
                elapsed_minutes = (current_time - reference_time) / 60
                elapsed_hours = elapsed_minutes / 60
                
                # Log progress occasionally
                if elapsed_minutes % 5 < 0.17:  # Log roughly every 5 minutes
                    fmt_time = "{:.1f}".format(elapsed_minutes)
                    print(f"Tracking 24hr max for {ca}: {fmt_time} minutes elapsed")
                
                # After 24 hours + 20 minutes, fetch and record the 24hr max price
                if not hr24_completed and current_time >= hr24_check_time and pool_address:
                    try:
                        print(f"Reached 24hr mark for {ca}, fetching max price...")
                        hr24_max_mc = await self.ath.get_ath(ca)
                        if not hr24_max_mc:
                            hr24_max_mc = await self.bath.calculate_all_time_high(ca, pool_address)
                            if hr24_max_mc is not None:
                                # Update the database with the 24hr max market cap
                                with sqlite3.connect('memedb.db') as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        UPDATE multialerts 
                                        SET hr24_max_mc = ?
                                        WHERE ca = ?
                                    """, (hr24_max_mc, ca))
                                    conn.commit()
                                    
                                print(f"Updated 24hr max MC for {ca}: ${hr24_max_mc:.2f}")
                            else:
                                print(f"Got None value for hr24_max_mc, skipping update")
                            
                            hr24_completed = True
                        else:
                            print(f"No valid 24hr max price data for {ca}")
                            hr24_completed = True  # Mark as completed even if it failed
                    except Exception as e:
                        print(f"Error fetching 24hr max price: {str(e)}")
                        hr24_completed = True  # Mark as completed even if it failed
                
                # Get current marketcap for interval checking and local max tracking
                try:
                    marketcap = await self.markca.marketcap(ca)
                    
                    if marketcap is None:
                        print(f"WARNING: marketcap is None for {ca}, setting to 0")
                        marketcap = 0
                    
                    try:
                        marketcap = float(marketcap)
                    except (ValueError, TypeError):
                        print(f"WARNING: Cannot convert marketcap to float for {ca}, setting to 0")
                        marketcap = 0
                    
                    # Still track max locally but don't update DB
                    if marketcap > max_mc:
                        max_mc = marketcap
                    
                    # Check each interval - only update when we reach the exact interval
                    for interval in intervals:
                        if interval in completed:
                            continue
                        
                        # Only update if we've reached this interval
                        if elapsed_minutes >= interval:
                            print(f"Reached {interval}m interval for {ca}, updating marketcap...")
                            
                            # Update DB with the marketcap at this interval
                            column_name = f"mc_{interval}m"
                            
                            with sqlite3.connect('memedb.db') as conn:
                                cursor = conn.cursor()
                                cursor.execute(f"""
                                    UPDATE multialerts 
                                    SET {column_name} = ?
                                    WHERE ca = ?
                                """, (marketcap, ca))
                                conn.commit()
                                
                            print(f"Updated {column_name} for {ca} with value {marketcap}")
                            completed.add(interval)
                    
                except Exception as e:
                    print(f"Error updating marketcap: {str(e)}")
                    import traceback
                    traceback.print_exc()
                
                # If we've completed all intervals and the 24hr check, exit
                if len(completed) == len(intervals) and hr24_completed:
                    print(f"All marketcap intervals and 24hr check completed for {ca}")
                    break
                    
                # Sleep before checking again - shorter sleep to be more accurate with timing
                await asyncio.sleep(30)  # Check every 30 seconds
                
        except Exception as e:
            print(f"Error in update_marketcap_data: {str(e)}")
            import traceback
            traceback.print_exc()
    


    async def convert_token_age_to_minutes(self, token_age):
        """
        Ensure token age is in minutes format
        """
        if isinstance(token_age, (int, float)):
            return token_age  # Already in minutes
            
        try:
            if isinstance(token_age, dict):
                value = token_age.get('value', 0)
                unit = token_age.get('unit', 'minutes').lower()
                
                if unit == 'minutes':
                    return value
                elif unit == 'hours':
                    return value * 60
                elif unit == 'days':
                    return value * 24 * 60
                elif unit == 'seconds':
                    return value / 60
                else:
                    return value  # Default to assuming minutes
            else:
                return 0
        except Exception as e:
            print(f"Error converting token age to minutes: {str(e)}")
            return 0


  


class Main:
    def __init__(self):
        self.ad_scraper = ScrapeAD(bot)
    
    async def run(self):
        @bot.event
        async def on_ready():
            print(f"Bot logged in as {bot.user}")
            await self.ad_scraper.initialize()

        async with aiohttp.ClientSession() as session:
            tasks = [
                bot.start(DISCORD_BOT_TOKEN),
                self.ad_scraper.swt_process_messages(session), 
                self.ad_scraper.fresh_process_messages(session),  
                self.ad_scraper.degen_fetch_and_process_messages(session)
                #self.ad_scraper.check_multialert(session, "test_name", 'test_ca', "test_channel")
            ]
            
            try:
                await asyncio.gather(*tasks)
            except Exception as e:
                print(f"Error in main loop: {str(e)}")
                await asyncio.sleep(5)
                await self.run()


if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())
