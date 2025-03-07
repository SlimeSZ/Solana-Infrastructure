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
                # Return a default structure with empty values if no dev history found
                return {
                    'weekly_activity': [{
                        'week_start': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                        'week_end': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                        'total_tokens': 0,
                        'rugs': 0,
                        'successful_tokens': 0
                    }],
                    'general_stats': {
                        'total_tokens_created': 0,
                        'total_rugs': 0,
                        'total_successful': 0,
                        'rug_rate': 0
                    }
                }
            
            data, wallet = result
            
            token_data = {}
            rug_report = {}
            successful_token_report = {}
            t_data = data.get('tokens', [])
            tokens_created = data.get('total', 0)  # Use get() with default
            print(F"Created: {tokens_created} tokens")

            if tokens_created > 0:
                for token in t_data:
                    name = token.get('name', 'Unknown Name')
                    token_ca = token.get('mint', '')
                    total_tx = token.get('totalTransactions', 0)
                    creation_time = token.get('createdAt', 0)
                    token_created_at = datetime.fromtimestamp(creation_time / 1000, tz=timezone.utc)
                    
                    token_data[token_ca] = {
                        'name': name,
                        'total_tx': total_tx,
                        'created_at': token_created_at
                    }   
                latest_tokens = dict(sorted(token_data.items(), 
                                    key=lambda x: x[1]['created_at'], 
                                    reverse=True)[:10])

                for token_ca, token_info in token_data.items():
                    if token_ca == original_ca:
                        continue
                    
                    if 0 <= token_info['total_tx'] <= 20:
                        rug_report[token_ca] = {
                            'name': token_info['name'],
                            'total_tx': token_info['total_tx'],
                            'created_at': token_info['created_at']
                        }
                    elif token_info['total_tx'] > 260:
                        await asyncio.sleep(1)
                        ath = await self._get_dev_token_aths(token_ca)
                        successful_token_report[token_ca] = {
                            'name': token_info['name'],
                            'total_tx': token_info['total_tx'],
                            'created_at': token_info['created_at'],
                            'ath': float(ath) if ath else None
                        }

                weekly_analysis = await self._analyze_dev_weekly_activity(token_data, rug_report, successful_token_report)
                
                # Ensure weekly_analysis is not None
                if not weekly_analysis:
                    weekly_analysis = [{
                        'week_start': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                        'week_end': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                        'total_tokens': 0,
                        'rugs': 0,
                        'successful_tokens': 0
                    }]
                
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
                    'successful_tokens': dict(sorted(successful_token_report.items(), key=lambda x: x[1]['total_tx'], reverse=True))
                }

                print("\nDeveloper Analysis Report")
                print("------------------------")
                print(f"Total Tokens Created: {comprehensive_report['general_stats']['total_tokens_created']}")
                print(f"Rug Rate: {comprehensive_report['general_stats']['rug_rate']:.2%}")
                print(f"Successful tokens: {comprehensive_report['general_stats']['total_successful']}")

                # Only display successful tokens if there are any
                if comprehensive_report['general_stats']['total_successful'] > 0:
                    print("\nSuccessful Tokens:")
                    for token_ca, info in comprehensive_report['successful_tokens'].items():
                        print(f"\nToken: {info['name']} | {token_ca}")
                        print(f"ATH: ${info['ath']:.2f}" if info['ath'] else "ATH: Not available")
                else:
                    print("\nNo successful tokens found.")

                print("\nRugs:")
                for token_ca, info in comprehensive_report['rug_details'].items():
                    print(f"\nToken: {info['name']}")
                    print(f"Creation Date: {info['created_at'].strftime('%Y-%m-%d')}")
                
                print("\nLatest 10 Tokens:")
                for token_ca, info in comprehensive_report['latest_tokens'].items():
                    print(f"\nToken: {info['name']} | {token_ca}")
                    print(f"Status: {info['status']}")
                    print(f"Total Tx: {info['total_tx']}")
                    print(f"Created: {info['created_at'].strftime('%Y-%m-%d')}")

                return comprehensive_report

            # Default return if tokens_created is not > 0
            return {
                'weekly_activity': [{
                    'week_start': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                    'week_end': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                    'total_tokens': 0,
                    'rugs': 0,
                    'successful_tokens': 0
                }],
                'general_stats': {
                    'total_tokens_created': 0,
                    'total_rugs': 0,
                    'total_successful': 0,
                    'rug_rate': 0
                }
            }

        except Exception as e:
            print(f"Error in dev_report: {str(e)}")
            # Return a minimal valid structure instead of None
            return {
                'weekly_activity': [{
                    'week_start': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                    'week_end': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                    'total_tokens': 0,
                    'rugs': 0,
                    'successful_tokens': 0
                }],
                'general_stats': {
                    'total_tokens_created': 0,
                    'total_rugs': 0,
                    'total_successful': 0,
                    'rug_rate': 0
                }
            }
        
    async def _analyze_dev_weekly_activity(self, t_data, rug_report, successfull_token_report):
        try:
            # Fix: Initialize an empty list for weekly stats even if data is missing
            current_time = datetime.now(timezone.utc)
            weekly_stats = []
            
            # Check if each parameter is None, and provide default empty dictionaries if needed
            t_data = t_data or {}
            rug_report = rug_report or {}
            successfull_token_report = successfull_token_report or {}
            
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
            print(f"Error in weekly activity analysis: {str(e)}")
            # Return at least one empty week stats object instead of None
            return [{
                'week_start': (current_time - timedelta(weeks=1)).strftime('%Y-%m-%d'),
                'week_end': current_time.strftime('%Y-%m-%d'),
                'total_tokens': 0,
                'rugs': 0,
                'successful_tokens': 0
            }]
            
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

class Main:
    def __init__(self):
        self.d = DevHist()
    async def run(self):
        d = await self.d.dev_report(ca="5inUdhQXKPKiZeTChT1xTd1kLu7BJYk2tLwCxVszpump", token_name="")
        print(d)

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())