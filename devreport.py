import asyncio
import aiohttp
from ath import ATH
from backupath import BATH
from dexapi import DexScreenerAPI
from marketcap import MarketcapFetcher
from env import SOLANA_TRACKER_API_KEY, BIRDEYE_API_KEY
from datetime import datetime, timezone, timedelta
from webhooks import TradeWebhook

class DevHist:
    def __init__(self):
        self.ath = ATH()
        self.bath = BATH()
        self.dex = DexScreenerAPI()
        self.mc = MarketcapFetcher()
        self.webhook = TradeWebhook()

        self.max_retries = 3
        self.retry_delay = 2

    async def get_dev_wallet(self, ca):
        url  = f"https://public-api.birdeye.so/defi/token_security?address={ca}"
        headers = {
            'accept': 'application/json',
            'x-chain': 'solana',
            'X-API-KEY': BIRDEYE_API_KEY
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    if not data:
                        return None
                    dev_wallet = data.get('data', {}).get('creatorAddress', '')
                    if not dev_wallet:
                        return None
                    return dev_wallet
        except Exception as e:
            print(f"Error getting dev wallet for ca:{ca}\n {str(e)}")
            return None
    
    async def get_dev_history(self, ca):
        wallet = await self.get_dev_wallet(ca=ca)
        if not wallet:
            return None
        print(f"Data for Wallet: {wallet}\n")
        url = f"https://data.solanatracker.io/deployer/{wallet}"
        headers = {
            'X-API-KEY': SOLANA_TRACKER_API_KEY
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    if not data:
                        return None
                    #print(data)
                    return data, wallet
        except Exception as e:
            print(str(e))
            return None

    async def dev_report(self, ca, token_name):
        try:
            original_ca = ca
            result = await self.get_dev_history(ca)
            if not result:
                return None
            data, wallet = result
            
            token_data = {}
            rug_report = {}
            successful_token_report = {}
            t_data = data.get('tokens', [])
            tokens_created = data['total']

            if tokens_created > 0:
                for token in t_data:
                    name = token.get('name', 'Unknown Name')
                    ca = token.get('mint', '')
                    total_tx = token.get('totalTransactions', 0)
                    creation_time = token.get('createdAt', 0)
                    token_created_at = datetime.fromtimestamp(creation_time / 1000, tz=timezone.utc)
                    
                    token_data[ca] = {
                        'name': name,
                        'total_tx': total_tx,
                        'created_at': token_created_at
                    }   
                    latest_tokens = dict(sorted(token_data.items(), 
                                        key=lambda x: x[1]['created_at'], 
                                        reverse=True)[:10])

                for ca, data in token_data.items():
                    if 0 <= data['total_tx'] <= 20:
                        rug_report[ca] = {
                            'name': data['name'],
                            'total_tx': data['total_tx'],
                            'created_at': data['created_at']
                        }
                    elif data['total_tx'] > 260:
                        await asyncio.sleep(1)
                        ath = await self._get_dev_token_aths(ca)
                        successful_token_report[ca] = {
                            'name': data['name'],
                            'total_tx': data['total_tx'],
                            'created_at': data['created_at'],
                            'ath': float(ath) if ath else None
                        }

                weekly_analysis = await self._analyze_dev_weekly_activity(token_data, rug_report, successful_token_report)
                
                comprehensive_report = {
                    'general_stats': {
                        'total_tokens_created': tokens_created,
                        'total_rugs': len(rug_report),
                        'total_successful': len(successful_token_report),
                        'rug_rate': len(rug_report) / tokens_created if tokens_created > 0 else 0,
                        'dev_wallet': wallet
                    },
                    'token_name': token_name,
                    'token_ca': original_ca,
                    'latest_tokens': {ca: {
                    'name': data['name'],
                    'total_tx': data['total_tx'],
                    'created_at': data['created_at'],
                    'status': 'Potential Rug' if data['total_tx'] < 90 else 'Active'} for ca, data in latest_tokens.items()},
                    'weekly_activity': weekly_analysis,
                    'rug_details': dict(sorted(rug_report.items(), key=lambda x: x[1]['created_at'], reverse=True)[:5]),
                    'successful_tokens': dict(sorted(successful_token_report.items(), key=lambda x: x[1]['total_tx'], reverse=True)[:10])
                }

                print("\nDeveloper Analysis Report")
                print("------------------------")
                print(f"Total Tokens Created: {comprehensive_report['general_stats']['total_tokens_created']}")
                print(f"Rug Rate: {comprehensive_report['general_stats']['rug_rate']:.2%}")
                print(f"Successful tokens: {comprehensive_report['general_stats']['total_successful']}")

                print("\nLatest 10 Successful Tokens:")
                for ca, info in comprehensive_report['successful_tokens'].items():
                    print(f"\nToken: {info['name']} | {ca}")
                    print(f"ATH: ${info['ath']:.2f}" if info['ath'] else "ATH: Not available")

                print("\nRugs:")
                for ca, info in comprehensive_report['rug_details'].items():
                    print(f"\nToken: {info['name']}")
                    print(f"Creation Date: {info['created_at'].strftime('%Y-%m-%d')}")
                
                print("\nLatest 10 Tokens:")
                for ca, info in comprehensive_report['latest_tokens'].items():
                    print(f"\nToken: {info['name']} | {ca}")
                    print(f"Status: {info['status']}")
                    print(f"Total Tx: {info['total_tx']}")
                    print(f"Created: {info['created_at'].strftime('%Y-%m-%d')}")

                await self.webhook.send_dev_history_webhook(comprehensive_report)
                return comprehensive_report

            return None

        except Exception as e:
            print(f"{str(e)}")
            return None
        
    async def _analyze_dev_weekly_activity(self, t_data, rug_report, successfull_token_report):
        try:
            if not (t_data and rug_report and successfull_token_report):
                print(f"Error in passing one of the 3 datasets to weekly activity analysis")
                return None
            current_time = datetime.now(timezone.utc)
            weekly_stats = []
            for week in range(7):
                week_start = current_time - timedelta(weeks=week+1)
                week_end = current_time - timedelta(weeks=week)
                week_stats = {
                    'week_start': week_start.strftime('%Y-%m-%d'),
                    'week_end': week_end.strftime('%Y-%m-%d'),
                    'total_tokens': 0,
                    'rugs': 0,
                    'successful_tokens': 0
                }
                for ca, data in t_data.items():
                    if week_start <= data['created_at'] < week_end:
                        week_stats['total_tokens'] += 1
                        if ca in rug_report:
                            week_stats['rugs'] += 1
                        if ca in successfull_token_report:
                            week_stats['successful_tokens'] += 1
                weekly_stats.append(week_stats)
            return weekly_stats
        except Exception as e:
            print(f"{str(e)}")
            return None
    async def _get_dev_token_aths(self, ca):
        try:
            ath = await self.ath.get_ath(ca)
            if not ath:
                dex_data = await self.dex.fetch_token_data_from_dex(ca)
                if not dex_data:
                    return
                pair_address = dex_data.get('pairAddress')
                ath = await self.bath.calculate_all_time_high(pair_address=pair_address)
                if not ath:
                    return None
            return ath
        except Exception as e:
            print(str(e))
            return None
