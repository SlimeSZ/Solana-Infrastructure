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
from compositescore import CompositeScore
from marketcap import MarketcapFetcher
from webhooks import AlefAlertWebhook, MultiAlert, ScoreReportWebhook

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
        self.get_top_holders = HolderAmount()
        self.score = CompositeScore()
        self.score_webhook_usage = ScoreReportWebhook()
        self.backup_mc = MarketcapFetcher()
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
                
                for message_id, message_data in data.items():
                    # Description extraction
                    if message_data["description"]:
                        tx_data = await self.description_processor.extract_buys_sells(message_data['description'])
                        if tx_data:
                            raw_tx = tx_data['raw_description']
                            tx_type = tx_data['type']
                            sol_amount = tx_data['sol_amount']
                            """
                            if sol_amount >= 10:
                                print(f"10+ Sol buy detected: {raw_tx}")
                                if ca not in self.ten_five_sol_alerts:
                                    self.ten_five_sol_alerts.add(ca)
                            elif 5 < sol_amount < 10:
                                print(f"5+ Sol buy detected: {raw_tx}")
                                self.ten_five_sol_alerts.add(ca)
                            """
                                    
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
            test_ca = "Bfh9xqBySk78yiEGAxTPtz6bwmfVnsQkTRLwBwF4pump"
            if ca == test_ca:
                multialert_found = True
            """
            if ca in all_fresh and ca in self.degen_cas: #associate ca w channel it was found in, pass it to print or webhook statements
                multialert_found = True
            if ca in all_swt and ca in self.degen_cas:
                multialert_found = True
            """

                
                

            
            if multialert_found:
                self.multi_alerted_cas.add(ca)
                print(f"\nMUlTI ALERT FOUND\n{"*" * 50}")

                
                #dex calls & processes:
                dex_data = await self.dex.fetch_token_data_from_dex(session, ca)
                if not dex_data:
                    return
                token_name = dex_data['token_name']
                backup_mc = await self.backup_mc.calculate_marketcap(ca)
                marketcap = dex_data['token_mc'] if dex_data['token_mc'] else backup_mc
                m5_vol = dex_data['token_5m_vol']
                liquidity = dex_data['token_liquidity']
                token_created_at = dex_data['token_created_at']
                pool_address = dex_data['pool_address']
                print(f"MC: {marketcap}")
                print(f"Liquidity: {liquidity}")
                print(f"5m Vol: {m5_vol}")
                print(f"Pool Addres: {pool_address}")

                telegram = dex_data['socials'].get('telegram', {}) or None
                twitter = dex_data['socials'].get('twitter', {}) or None
                dex_url = dex_data['dex_url']
                print(f"TG: {telegram}")
                print(f"X: {twitter}")

                                
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
                print(last_swt)
                print(last_fresh)
                print(last_degen)

                #call tg evaluation
                soul_data = await self.soul_scanner_bot.send_and_receive_message(ca)
                if not soul_data:
                    return
                
                holder_count = soul_data['holder_count']
                #top_hold = soul_data['top_percentage']
                dev_holding = soul_data['dev_holding']

                tg_metrics = {
                    'token_migrated': False,
                    'holding_percentage': None,
                    'holder_count': holder_count,
                    #'top_holding_percentage': top_hold,
                    'dev_holding_percentage': dev_holding
                }
                
                if soul_data['passes']:
                    print(f"\nSOUL SCANNER TEST PASSED FOR: {ca}\nRunning bundle bot check")
                bundle_data = await self.bundle_bot.send_and_receive_message(ca)
                if bundle_data:
                    passes = bundle_data['passes']
                    if passes:
                        await self.rickbot_webhook.full_send_ca_to_alefdao(ca)
                        await self.slime_alert.send_message(ca)
                        print(f"\nBundle bot ALSO PASSED FOR: {ca}")
                        """
                        tg_metrics['holding_percentage'] = ['holding_percentage']
                        if bundle_data['token_bonded']:
                            if isinstance(bundle_data['token_bonded'], bool):
                                tg_metrics['token_migrated'] = bundle_data['token_bonded']
                                print(f"Token Migrated")
                            else:
                                print(F"Token On Pump")
                        else:
                            await self.rickbot_webhooks.conditional_send_ca_to_alefdao(ca)
                            await self.slime_alert.send_message(ca)
                        """
                print(f"Holder Count: {tg_metrics['holder_count']}")
                #print(f"Top Holders hold total of: {tg_metrics['top_holding_percentage']} %")
                print(f"Dev holds: {tg_metrics['dev_holding_percentage']} %" )

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

                #get holder data
                holder_criteria = False
                holder_data = await self.get_top_holders.calculate_holder_value(ca)
                if holder_data:
                    holder_values, holder_evaluation = holder_data  # Unpack the tuple
                    if holder_values:  # Check if holder_values exists
                        metadata = holder_values.get('metadata', {})
                        if metadata:
                            holders_over_5 = metadata.get('holders_over_5_percent', 0)
                            total_held = metadata.get('total_percentage_held', 0)
                            print(f"\nHolder Analysis:")
                            print(f"Top 10 Wallets hold total of {total_held}%")
                            if holders_over_5:
                                print(f"Warning: {holders_over_5} Holders w/ over 5%")

                            #check criteria to run top wallet pnl analysis
                            #test: 
                            if holders_over_5 <= 5:
                            #iREAL: f holders_over_5 <= 2 and age_value != 'days' and soul_data['passes']:
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
                                            """
                                                print(f"\nWallet {wallet_address[:8]}...")
                                                print(f"Holding: {wallet_info['percentage']}%")
                                                print(f"Last 100 TX PNL: {wallet_pnl['last_100_tx_pnl']:.4f} SOL")
                                                print(f"Tokens Traded: {wallet_pnl['tokens_traded']}")
                                                print(f"Wins/Losses: {wallet_pnl['trades_won']}/{wallet_pnl['trades_loss']}")
                                                print(f"Average Sol entry: {wallet_pnl['average_entry_per_trade']}")
                                                print("-" * 30)
                                                wallets_processed += 1
                                                """
                last_3_transactions = {
                    'swt': swt_data['latest_descriptions'][-1:] if swt_data else [],
                    'degen': degen_data['latest_descriptions'][-1:] if degen_data else [],
                    'fresh': fresh_data['latest_descriptions'][-1:] if fresh_data else []
                }
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

                score_data = await self.score.calculate_score(
                    token_age=token_age,
                    telegram=telegram,
                    twitter=twitter,
                    holder_count=holder_count,
                    dex_paid=dex_paid,
                    top_10_holding_percentage=total_held,
                    holders_over_5_percent=holders_over_5,
                    dev_holding_percentage=dev_holding,
                    soul_scanner_pass=soul_data['passes'],
                    bundle_bot_pass=bundle_data['passes'] if bundle_data else False,
                    marketcap=marketcap,
                    m5_vol=m5_vol,
                    liquidity=liquidity,
                    server_buys=total_swt_buys + total_fresh_buys,
                    server_sells=total_swt_sells + total_fresh_sells,
                    server_count=total_swt_count + total_fresh_count,
                    wallet_data=wallet_analysis if holder_criteria else None,
                    channel_metrics=channel_metrics
                )
                if score_data:
                    await self.score_webhook_usage.send_score_report(ca, token_name, score_data)


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
                    last_3_tx=last_3_transactions,
                    holder_count=holder_count,
                    dev_holding_percentage=dev_holding,
                    token_migrated=tg_metrics['token_migrated'],
                    passes_soulscanner=soul_data['passes'],
                    passes_bundlebot=bundle_data['passes'] if bundle_data else False,
                    dex_paid=dex_paid,
                    token_age=token_age,
                    top_10_holding_percentage=total_held,
                    holders_over_5=holders_over_5,
                    wallet_data=wallet_analysis if holder_criteria else None

                )






                        
        
        except Exception as e:
            print(f"Error in running check for multialert: {str(e)}")
            import traceback
            print(traceback.format_exc())
                
                    








            
                


                        


class Main:
    def __init__(self):
        self.ad_scraper = ScrapeAD(bot)
    
    async def run(self):
        @bot.event
        async def on_ready():
            print(f"Bot logged in as {bot.user}")
            await self.ad_scraper.initialize()

        async with aiohttp.ClientSession() as session:
            # Create all tasks including bot startup
            tasks = [
                bot.start(DISCORD_BOT_TOKEN),
                self.ad_scraper.check_multialert(session, "test_name", 'Bfh9xqBySk78yiEGAxTPtz6bwmfVnsQkTRLwBwF4pump', "test_channel")
            ]
            
            try:
                await asyncio.gather(*tasks)  # Don't forget the * to unpack tasks
            except Exception as e:
                print(f"Error in main loop: {str(e)}")
                await asyncio.sleep(5)
                await self.run()


if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())
