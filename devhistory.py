import asyncio
import aiohttp
from env import SOLANA_TRACKER_API_KEY, BIRDEYE_API_KEY
from ath import ATH
from backupath import BATH
from dexapi import DexScreenerAPI
from marketcap import MarketcapFetcher

class DevTokenHistory:
    def __init__(self):
        self.ath = ATH()
        self.backup_ath = BATH()
        self.d = DexScreenerAPI()
        self.rpc = MarketcapFetcher()

    async def get_deployer(self, ca):
        url = f"https://public-api.birdeye.so/defi/token_security?address={ca}"
        headers = {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": BIRDEYE_API_KEY
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    if not data:
                        return None
                    sec_data = data.get('data', {})
                    deployer_wallet = sec_data.get('creatorAddress', '')
                    if not deployer_wallet:
                        print(f"Failed to get dep. wallet")
                    return deployer_wallet
        except Exception as e:
            print(str(e))
            return None

    
    async def get_deployer_history(self, ca):
        dev_wallet = await self.get_deployer(ca)
        url = f"https://data.solanatracker.io/deployer/{dev_wallet}"
        headers = {
            'X-API-KEY': SOLANA_TRACKER_API_KEY
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    if not data:
                        print(f"Error")
                        return None
                    total = data['total']
                    token_data = {}
                    if total > 1:
                        tokens = data.get('tokens', [])[:20]
                        for token in tokens:
                            name = token.get('name', 'Unknown Name')
                            ca = token.get('mint', '')
                            buys = token.get('buys', 0)
                            sells = token.get('sells', 0)
                            total_tx = token.get('totalTransactions', 0)
                            marketcap = await self.rpc.calculate_marketcap(ca)
                            token_data[name] = {
                                'ca': ca,
                                'buys': buys,
                                'sells': sells,
                                'total_tx': total_tx,
                                'current_mc': marketcap
                            }
                            # Add delay to avoid rate limiting
                            #await asyncio.sleep(1)
                        
                    rug_data = await self.rug_report(token_data)
                    return total, token_data, rug_data
        except Exception as e:
            print(str(e))
            return None
    
    async def rug_report(self, token_data):
        try:
            rug_report = {}
            aths = {}
            max_retries = 3
            retry_delay = 2
            total_rug_count = 0

            for name, data in token_data.items():
                if data.get('current_mc') and data['current_mc'] < 12000:
                    ca = data['ca']
                    
                    for attempt in range(max_retries):
                        try:
                            if attempt > 0:
                                await asyncio.sleep(retry_delay * (attempt + 1))
                            token_ath = await self.ath.get_ath(ca)
                            if not token_ath:
                                dex_data = await self.d.fetch_token_data_from_dex(ca)
                                if dex_data:
                                    pair_address = dex_data['pool_address']
                                    token_ath = await self.backup_ath.calculate_all_time_high(ca, pair_address)
                                
                                if token_ath is not None:
                                    aths[ca] = float(token_ath)
                                    if aths[ca] <= 50000:
                                        total_rug_count += 1
                                        rug_report[ca] = {
                                            'name': name,
                                            'ath': aths[ca],
                                            'current_mc': data['current_mc']
                                        }
                                    break
                                    
                        except aiohttp.ClientResponseError as e:
                            if e.status == 429 and attempt < max_retries - 1:
                                print(f"Rate limited, retrying in {retry_delay * (attempt + 1)} seconds...")
                                continue
                            print(f"Error fetching data for {ca}: {str(e)}")
                            break
                        except Exception as e:
                            print(f"Unexpected error for {ca}: {str(e)}")
                            break
                    
                    await asyncio.sleep(1)
                    
            return aths, rug_report, total_rug_count
        except Exception as e:
            print(f"Error in rug report: {str(e)}")
            return None, None, 0
    
    async def deployer_report(self, ca):
        try:
            dep_hist = await self.get_deployer_history(ca)
            if dep_hist and len(dep_hist) == 3:
                total, token_data, rug_data = dep_hist
                report = {}
                
                if total > 3:
                    total_buys = sum(data['buys'] for data in token_data.values())
                    total_sells = sum(data['sells'] for data in token_data.values())
                    
                    report['avg_stats'] = {
                        'avg_buys_per_token': total_buys / total,
                        'avg_sells_per_token': total_sells / total
                    }
                
                high_volume_tokens = {}
                for name, data in token_data.items():
                    if data['total_tx'] > 5000:
                        high_volume_tokens[name] = data
                
                report['high_volume_tokens'] = high_volume_tokens
                report['rug_data'] = rug_data
                
                print("\n=== DEVELOPER ANALYSIS REPORT ===")
                
                if 'avg_stats' in report:
                    placeholder = "Dev Created > 20 tokens!"
                    print(f"Total Tokens Created: {total}")
                    print(placeholder if total >= 20 else "")
                    print("\nAVERAGE STATS (>3 tokens created):")
                    print(f"Average buys per token: {report['avg_stats']['avg_buys_per_token']:.2f}")
                    print(f"Average sells per token: {report['avg_stats']['avg_sells_per_token']:.2f}")
                
                if high_volume_tokens:
                    print("\nHIGH VOLUME TOKENS (>5k transactions):")
                    highest_mc = 0
                    for name, token in high_volume_tokens.items():
                        ca = token['ca']
                        dex_data = await self.d.fetch_token_data_from_dex(ca)
                        if dex_data:
                            pair_address = dex_data['pool_address']
                            token_ath = await self.ath.get_ath(ca)
                            if not token_ath:
                                token_ath = await self.backup_ath.calculate_all_time_high(ca, pair_address)
                            
                            if token_ath and token_ath > highest_mc:
                                highest_mc = token_ath
                                
                            # Store ATH for this specific token
                            high_volume_tokens[name]['ath'] = token_ath if token_ath else 0
                        
                        print(f"\nName: {name}")
                        print(f"CA: {ca}")
                        print(f"Buys: {token['buys']}")
                        print(f"Sells: {token['sells']}")
                        print(f"Total TX: {token['total_tx']}")
                        print(f"Current MC: ${token['current_mc']:,.2f}")
                        if token.get('ath'):
                            print(f"Token ATH: ${token['ath']:,.2f}")
                    
                    if highest_mc > 0:
                        print(f"\nHighest MC Dev's tokens achieved: ${highest_mc:,.2f}")
                else:
                    print(f"\nNO high volume tokens detected")
                
                if rug_data and len(rug_data) == 3:
                    aths, rug_info, total_rug_count = rug_data  
                    print("\nRUG ANALYSIS:")
                    print(f"Total Rug Count: {total_rug_count}")  
                    
                    if rug_info:  
                        for ca, data in rug_info.items():
                            print(f"\nRug Tokens:")
                            for name, details in token_data.items():
                                if details['ca'] == ca:
                                    print(f"Current MC: ${details['current_mc']:,.2f}")
                                    drop = ((aths.get(ca, 0) - details['current_mc']) / aths.get(ca, 0)) * 100
                                    print(f"Price Drop: {drop:.2f}%")
                else:
                    print(f"NO RUG DATA AVAILABLE")
                
                return report
                
        except Exception as e:
            print(f"Fatal errors analyzing deployer hist & wallet data: {str(e)}")
            return None
    
class Main:
    def __init__(self):
        self.dev = DevTokenHistory()
        self.ca = "FTnCU6Q77beNH5bpgnQGtWmGxxJ1xzX3rsmkjBNTpump"
    async def run(self):
        await self.dev.deployer_report(ca=self.ca)

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())