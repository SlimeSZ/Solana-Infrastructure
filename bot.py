#libraries
import requests
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
from serverdata import ServerData
from dexapi import DexScreenerAPI
from tg import SoulScannerBot, BundleBot, WalletPNL
from tokenage import TokenAge
from alefalerts import MessageSender
from topholders import HolderAmount
from walletpnl import WAlletPNL
from scoring import HolderScore, TokenomicScore, TrustScore, PenalizeScore, TokenAgeConvert
from marketcap import MarketcapFetcher
from bdmetadata import BuySellTradeUniqueData, Tokenomics
from devreport import DevHist
from twoxmonitor import TwoXChecker
#from x import Twitter
from scanforentry import MarketcapMonitor
from webhooks import AlefAlertWebhook, MultiAlert 

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
        self.dev_history = DevHist()
        self.serv_data = None
        self.dex = DexScreenerAPI()
        self.soul_scanner_bot = SoulScannerBot()
        self.bundle_bot = BundleBot()
        self.wallet_pnl = WAlletPNL()
        self.wallet_pnl_tg = WalletPNL()
        self.token_age = TokenAge()
        self.slime_alert = MessageSender()
        self.rickbot_webhook = AlefAlertWebhook()  
        self.ma_webhooks = MultiAlert()
        self.mc_monitor = MarketcapMonitor()
        #self.x = Twitter()
        self.get_top_holders = HolderAmount()
        #scoring imports
        self.holderscore = HolderScore()
        self.tokenomicscore = TokenomicScore()
        self.trustscore = TrustScore()
        self.penalizescore = PenalizeScore()

        
        self.backup_mc = MarketcapFetcher()
        self.bd_trade_data = BuySellTradeUniqueData()
        self.bd_tokenomic_data = Tokenomics()
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

            multialert_found = False #should act more as a dict with bool val associated w ca
            """
            test_ca = "cSkk1aJBuXhAhgkwXt47tKDRFrLAbA8BVCq6FJTpump"
            if ca == test_ca:
                multialert_found = True
            """
            if ca in all_fresh and (ca in self.degen_cas or ca in all_swt): #associate ca w channel it was found in, pass it to print or webhook statements
                multialert_found = True

            if multialert_found:
                self.multi_alerted_cas.add(ca)
                print(f"\nMUlTI ALERT FOUND\n{"*" * 50}")

                
                #create two_x checker task
                asyncio.create_task(self.start_2x_monitoring(ca, token_name))

                try:
                #dex calls & processes:
                    dex_data = await self.dex.fetch_token_data_from_dex(ca) or {}
                except Exception as e:
                    print(str(e))
                try:
                    backup_bd_data = await self.bd_tokenomic_data.process(ca) or {}
                except Exception as e:
                    print(str(e))
                try:
                    unique_bd_data = await self.bd_trade_data.process(ca) or {}
                except Exception as e:
                    print(str(e))

                try:
                    token_name = dex_data.get('token_name') or backup_bd_data.get('name', 'Unknown Name')
                    print(f"Token Name: {token_name} CA: {ca}")
                    backup_mc = await self.backup_mc.calculate_marketcap(ca)
                    marketcap = backup_bd_data.get('marketcap', backup_mc)
                    print(f"Marketcap: ${marketcap:.2f}")
                    m5_vol = dex_data.get('token_5m_vol', 0)
                    print(f"5m volume: {m5_vol:.2f}")
                    if backup_bd_data:
                        m30_vol = backup_bd_data.get('30_min_vol', 0)
                        m30_vol_change = backup_bd_data.get('30_min_vol_percent_change', 0)
                        print(f"30m VOL: {m30_vol} || {m30_vol_change} % Change in vol")
                    liquidity = backup_bd_data.get('liquidity', 0)
                    print(f"Liquidity: {liquidity}")
                    pool_address = dex_data.get('pool_address', None)
                    if pool_address is None:
                        return None
                    print(f"Pool Addres: {pool_address}")
                except Exception as e:
                    print(str(e))

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
                
                # In the check_multialert function, replace this section:
                try:
                    if unique_bd_data:
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


                                
                #get servercount & buy/sell data
                print(f"\nFetching server data for CA: {ca}")
                self.serv_data.target_ca = ca

                # Check SWT data
                swt_data = await self.serv_data.swt_server_data()
                if not swt_data:
                    return

                # Check Degen data
                degen_data = await self.serv_data.degen_server_data()
                if not degen_data:
                    return

                # Check Fresh data
                fresh_data = await self.serv_data.fresh_server_data()
                if not fresh_data:
                    return
                    

                #trading links:
                links = swt_data['trading_links']
                if not links:
                    pass
                photon_link = links['photon']
                bull_x_link = links['bull_x']
                dexscreener_link = links['dex']
                print(f"Photon: {photon_link}")
                print(f"Bullx: {bull_x_link}")
                print(f"Dex Link: {dexscreener_link}")

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
                print(f"\nBuy Sell & Server Count Data for {ca}")
                print(f"SWT BUYS: {total_swt_buys}")
                print(f"SWT SELLS: {total_swt_sells}")
                print(f"Fresh Buys: {total_fresh_buys}")
                print(f"Fresh Sells: {total_fresh_sells}")
                print(f"SWT COUNT: {total_swt_count} || Fresh Count: {total_fresh_count}")

                #get last 5 txs (serverdata.py)
                last_swt = swt_data['latest_descriptions'][-1:] if swt_data else []
                last_degen = degen_data['latest_descriptions'][-1:] if degen_data else []
                last_fresh = fresh_data['latest_descriptions'][-1:] if fresh_data else []
                print(f"\nLast 3 Descriptions: ")
                print(last_swt)
                print(last_fresh)
                print(last_degen)

                #call tg evaluation
                try:
                    soul_data = await self.soul_scanner_bot.send_and_receive_message(ca)
                    if soul_data:
                        holder_count = unique_bd_data['holders']
                        #top_hold = soul_data['top_percentage']
                        dev_holding = soul_data['dev_holding']
                        sniper_percent = soul_data['sniper_percent']

                        tg_metrics = {
                            'token_migrated': False,
                            'holding_percentage': None,
                            'holder_count': holder_count,
                            #'top_holding_percentage': top_hold,
                            'dev_holding_percentage': dev_holding,
                            'sniper_percent': sniper_percent
                        }
                
                        if soul_data['passes']:
                            print(f"\nSOUL SCANNER TEST PASSED FOR: {ca}")
                        else:
                            print(f"Soul Scanner Failed")
                except Exception as e:
                    print(f"Error during soul scanner: {str(e)}")
                try:
                    bundle_data = await self.bundle_bot.send_and_receive_message(ca)
                    if bundle_data and bundle_data['passes']:
                            #await self.rickbot_webhook.full_send_ca_to_alefdao(ca)
                            #await self.slime_alert.send_message(ca)
                            print(f"\nBundle bot PASSED FOR: {ca}")
                            
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

                if soul_data['passes'] and bundle_data['passes']:
                    await self.rickbot_webhook.full_send_ca_to_alefdao(ca)
                    #await self.slime_alert.send_message(ca)
                elif soul_data['passes'] or bundle_data['passes']:
                    await self.rickbot_webhook.conditional_send_ca_to_alefdao(ca)


                print(f"Holder Count: {tg_metrics['holder_count']}")
                #print(f"Top Holders hold total of: {tg_metrics['top_holding_percentage']} %")
                print(f"Dev holds: {tg_metrics['dev_holding_percentage']} %" )
                print(f"Sniper Percent: {tg_metrics['sniper_percent']}")

                #dex paid check
                dex_paid = await self.wallet_pnl_tg.send_and_recieve_message_dex_paid(ca)
                print(f"Dex Paid? {dex_paid}")
                
                #get dex chat .png
                """
                dex_chart_data = await self.wallet_pnl_tg.send_and_recieve_dex_chart(ca)
                if dex_chart_data:
                    chart_image = dex_chart_data['image_data']
                """

                #token age
                token_age = await self.token_age.process_pair_age(ca)
                if not token_age:
                    return
                age_value = token_age['value']
                age_unit = token_age['unit']
                age = f"{age_value} {age_unit}"
                print(age)

                total_held = 0
                holders_over_5 = 0
                holder_criteria = False
                holder_data = await self.get_top_holders.calculate_holder_value(ca)
                if holder_data:
                    holder_values, holder_evaluation = holder_data  
                    if holder_values:  
                        metadata = holder_values.get('metadata', {})
                        if metadata:
                            holders_over_5 = metadata.get('holders_over_5_percent', 0)
                            total_held = metadata.get('total_percentage_held', 0)
                            print(f"\nHolder Analysis:")
                            print(f"Top 10 Wallets hold total of {total_held}%")
                            if holders_over_5:
                                print(f"Warning: {holders_over_5} Holders w/ over 5%")

                            #check criteria to run top wallet pnl analysis
                            if soul_data['passes'] and holders_over_5 < 4 and dev_holding < 5:
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
                                            wallet_pnl = await self.wallet_pnl.calculate_pnl(wallet_address)
                                            if wallet_pnl:
                                                wallet_analysis[wallet_address] = {
                                                'holding_percentage': wallet_info['percentage'],
                                                'pnl': wallet_pnl['last_100_tx_pnl'],
                                                'tokens_traded': wallet_pnl['tokens_traded'],
                                                'wins': wallet_pnl['trades_won'],
                                                'losses': wallet_pnl['trades_loss'],
                                                'avg_entry': wallet_pnl['average_entry_per_trade'] if wallet_pnl['average_entry_per_trade'] > 0 else None
                                            }
                                            wallets_processed += 1
                                            
                                                #print(f"\nWallet {wallet_address[:8]}...")
                                                #print(f"Holding: {wallet_info['percentage']}%")
                                                #print(f"Last 100 TX PNL: {wallet_pnl['last_100_tx_pnl']:.4f} SOL")
                                                #print(f"Tokens Traded: {wallet_pnl['tokens_traded']}")
                                                #print(f"Wins/Losses: {wallet_pnl['trades_won']}/{wallet_pnl['trades_loss']}")
                                                #print(f"Average Sol entry: {wallet_pnl['average_entry_per_trade']}")
                                                #print("-" * 30)
                                                #wallets_processed += 1
                                                
                all_transactions = []

                # Add transactions from each source
                if swt_data and swt_data['latest_descriptions']:
                    all_transactions.extend(swt_data['latest_descriptions'][-1:])
                if degen_data and degen_data['latest_descriptions']:
                    all_transactions.extend(degen_data['latest_descriptions'][-1:])
                if fresh_data and fresh_data['latest_descriptions']:
                    all_transactions.extend(fresh_data['latest_descriptions'][-1:])

                # Format for webhook
                if all_transactions:
                    tx_summary = "\n".join([f"• {tx}" for tx in all_transactions])
                else:
                    tx_summary = "No recent transactions"


                channel_metrics = {

                    'swt': {
                        'channels': swt_data['channels'],
                        'total_count': total_swt_count,
                        'total_buys': total_swt_buys,
                        'total_sells': total_swt_sells
                    },
                    'fresh': {
                        'channels': fresh_data['channels'],
                        'total_count': total_fresh_count,
                        'total_buys': total_fresh_buys,
                        'total_sells': total_fresh_sells
                    },
                    'degen': {
                        'channels': degen_data['channels'],
                        'total_count': degen_count,
                        'total_buys': degen_buys,
                        'total_sells': degen_sells
                    }
                }

                channels_ca_found_in = {}
                for channel_name, data in swt_data['channels'].items():
                    if data['buys'] > 0:
                        channels_ca_found_in[channel_name] = data['buys']
                if degen_data['channels']['Degen']['buys'] > 0:
                    channels_ca_found_in[channel_name] = data['buys']
                for channel_name, data in fresh_data['channels'].items():
                    if data['buys'] > 0:
                        channels_ca_found_in[channel_name] = data['buys']

                channel_text = "No active channels yet" if not channels_ca_found_in else "\n".join([f"• {channel} ({amount:.2f}sol)" for channel, amount in channels_ca_found_in.items() if amount > 0])                

                #----------------------------------------------------------------------------------

                holder_score = await self.holderscore.calculate_score(
                    token_age=token_age,
                    holder_count=holder_count,
                    top10holds=total_held,
                    holdersover5percent=holders_over_5,
                    devholds=dev_holding,
                    sniper_percent=sniper_percent,
                    wallet_data=wallet_analysis if holder_criteria else None
                )

                tokenomic_score, tokenomic_breakdown = await self.tokenomicscore.calculate_tokenomic_score(
                    token_age=token_age,
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
                )

                trust_score, trust_breakdown = await self.trustscore.calculate_trust_score(
                    token_age=token_age,
                    server_buys=total_swt_buys + total_fresh_buys,
                    server_sells=total_swt_sells + total_fresh_sells,
                    server_count=total_swt_count + total_fresh_count,
                    has_tg=telegram,
                    has_x=twitter,
                    dexpaid=dex_paid,
                    soulscannerpass=soul_data['passes'],
                    bundlebotpass=bundle_data['passes'],
                    buys_change=buy_percent_change_30m,
                    sells_change=sell_percent_change_30m
                )

                # Calculate penalties
                penalties = await self.penalizescore.calculate_penalties(
                    token_age=token_age,
                    liquidity=liquidity,
                    server_buys=total_swt_buys + total_fresh_buys,
                    server_sells=total_swt_sells + total_fresh_sells,
                    has_tg=telegram,
                    has_x=twitter,
                    holdersover5percent=holders_over_5,
                    sniper_percent=sniper_percent,
                    soulscannerpasses=soul_data['passes'],
                    bundlebotpasses=bundle_data['passes'],
                    dex_paid=dex_paid
                )

                # Calculate composite score
                total_score_before_penalties = 0

                if holder_score and isinstance(holder_score, dict):
                    total_score_before_penalties += holder_score.get('total_score', 0)

                if tokenomic_breakdown and isinstance(tokenomic_breakdown, dict):
                    total_score_before_penalties += tokenomic_breakdown.get('total_score', 0)

                if trust_breakdown and isinstance(trust_breakdown, dict):
                    total_score_before_penalties += trust_breakdown.get('total_score', 0)

                final_score = max(0, total_score_before_penalties - (penalties or 0))

                """
                #Twitter Analysis
                if final_score >= 75:
                    print(f"Running Twitter Analysis for: {ca}")
                    #extract twit user for twitter processing
                    if twitter:
                        username = twitter.split("/")[-1]
                        print(f"\nRunning Searchbar Analysis for: {ca} as well as token account analysis for @{username}")
                """
                
                await self.ma_webhooks.multialert_webhook(
                    token_name=token_name,
                    ca=ca,
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
                    token_migrated=tg_metrics['token_migrated'],
                    passes_soulscanner=soul_data['passes'],
                    passes_bundlebot=bundle_data['passes'] if bundle_data else False,
                    dex_paid=dex_paid,
                    token_age=token_age,
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
                    comp_score=final_score
                )     
                await self.ma_webhooks.score_webhook(
                    token_name=token_name,
                    ca=ca,
                    
                    holder_total=holder_score['total_score'],
                    holder_age_confluence=holder_score['holder_count_age_confluence'],
                    holder_security=holder_score['holder_security'],
                    holder_wallet_analysis=holder_score['wallet_score'],
                    
                    tokenomic_total=tokenomic_breakdown['total_score'],
                    tokenomic_vol_liq=tokenomic_breakdown['volume_marketcap_liquidity_confluence'],
                    tokenomic_30m_vol=tokenomic_breakdown['m30_age_volume_confluence'],
                    tokenomic_5m_vol=tokenomic_breakdown['m5_age_volume_confluence'],
                    tokenomic_trade_confluence=tokenomic_breakdown['total_trades_buy_confluence'],
                    tokenomic_buy_pressure=tokenomic_breakdown['buying_pressure'],
                    tokenomic_wallet_growth=tokenomic_breakdown['wallet_growth'],
                    
                    trust_total=trust_breakdown['total_score'],
                    trust_bs_confluence=trust_breakdown['server_buy_sell_pool_buy_sells_confluence'],
                    trust_age_count=trust_breakdown['age_server_count_confluence'],
                    trust_security=trust_breakdown['security_evaluation'],
                    trust_activity=trust_breakdown['server_activity_evaluation'],
                    trust_social=trust_breakdown['social_presence_evaluation'],
                    
                    total_before_penalties=total_score_before_penalties,
                    penalties=penalties,
                    final_score=final_score
                )

                age_minutes = self.age_converter.convert_token_age_to_minutes(token_age)
                if final_score >= 48:
                    marketcap_task = asyncio.create_task(self.mc_monitor.monitor_marketcap(token_name, ca, pool_address, age_minutes))
                dev_history_task = asyncio.create_task(self.dev_history.dev_report(ca=ca, token_name=token_name))

                if not hasattr(self, 'background_tasks'):
                    self.background_tasks = []
                self.background_tasks.append(marketcap_task)
                self.background_tasks.append(dev_history_task)

                self.background_tasks = [task for task in self.background_tasks if not task.done()]
        
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
        
    async def apply_penalities(composite_score, penalties):
        try:
            final_score = max(0, composite_score - penalties)
            return final_score
        except Exception as e:
            print(f"{str(e)}")
            return None
                    








            
                


                        


class Main:
    def __init__(self):
        self.ad_scraper = ScrapeAD(bot)
    
    async def run(self):
        @bot.event
        async def on_ready():
            print(f"Bot logged in as {bot.user}")
            await self.ad_scraper.initialize()

        async with aiohttp.ClientSession() as session:
            # Create all tasks including bot startup and continuous monitoring
            tasks = [
                bot.start(DISCORD_BOT_TOKEN),
                self.ad_scraper.swt_process_messages(session), 
                self.ad_scraper.fresh_process_messages(session),  
                self.ad_scraper.degen_fetch_and_process_messages(session)
                #self.ad_scraper.check_multialert(session, "test_name", 'cSkk1aJBuXhAhgkwXt47tKDRFrLAbA8BVCq6FJTpump', "test_channel")
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
