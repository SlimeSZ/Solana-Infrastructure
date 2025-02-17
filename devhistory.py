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
            "X-API-KEY": "d22b56521e3549b1a2ac74d5de237ee4"
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
                        tokens = data.get('tokens', [])
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
                            await asyncio.sleep(1)
                        
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

            for name, data in token_data.items():
                if data['current_mc'] < 12000:
                    ca = data['ca']
                    
                    for attempt in range(max_retries):
                        try:
                            if attempt > 0:
                                await asyncio.sleep(retry_delay * (attempt + 1))
                                
                            dex_data = await self.d.fetch_token_data_from_dex(ca)
                            if dex_data:
                                pair_address = dex_data['pool_address']
                                token_ath = await self.backup_ath.calculate_all_time_high(ca, pair_address)
                                
                                if token_ath:
                                    aths[ca] = token_ath
                                    if token_ath <= 50000:
                                        if ca not in rug_report:
                                            rug_report[ca] = {
                                                'name': name,
                                                'rug_count': 0,
                                                'ath': token_ath,
                                                'current_mc': data['current_mc']
                                            }
                                        rug_report[ca]['rug_count'] += 1
                                    break  # Success, exit retry loop
                                    
                        except aiohttp.ClientResponseError as e:
                            if e.status == 429:  # Too Many Requests
                                if attempt < max_retries - 1:
                                    print(f"Rate limited, retrying in {retry_delay * (attempt + 1)} seconds...")
                                    continue
                            print(f"Error fetching data for {ca}: {str(e)}")
                        except Exception as e:
                            print(f"Unexpected error for {ca}: {str(e)}")
                            break
                    
                    # Add delay between different tokens
                    await asyncio.sleep(1)
                    
            return aths, rug_report
        except Exception as e:
            print(f"Error in rug report: {str(e)}")
            return None, None
    
    async def deployer_report(self, ca):
        try:
            dep_hist = await self.get_deployer_history(ca)
            if dep_hist and len(dep_hist) == 3:  # We expect 3 values
                total, token_data, rug_data = dep_hist  # Unpack all three values
                report = {}
                
                # Only calculate averages if they've created more than 3 tokens
                if total > 3:
                    total_buys = sum(data['buys'] for data in token_data.values())
                    total_sells = sum(data['sells'] for data in token_data.values())
                    
                    report['avg_stats'] = {
                        'avg_buys_per_token': total_buys / total,
                        'avg_sells_per_token': total_sells / total
                    }
                
                # Find high transaction tokens (>5k)
                high_volume_tokens = {}
                for name, data in token_data.items():
                    if data['total_tx'] > 5000:
                        high_volume_tokens[name] = data
                
                report['high_volume_tokens'] = high_volume_tokens
                report['rug_data'] = rug_data
                
                # Print report
                print("\n=== DEVELOPER ANALYSIS REPORT ===")
                
                if 'avg_stats' in report:
                    print("\nAVERAGE STATS (>3 tokens created):")
                    print(f"Average buys per token: {report['avg_stats']['avg_buys_per_token']:.2f}")
                    print(f"Average sells per token: {report['avg_stats']['avg_sells_per_token']:.2f}")
                
                if high_volume_tokens:
                    print("\nHIGH VOLUME TOKENS (>5k transactions):")
                    for name, data in high_volume_tokens.items():
                        print(f"\n{name}")
                        print(f"CA: {data['ca']}")
                        print(f"Buys: {data['buys']}")
                        print(f"Sells: {data['sells']}")
                        print(f"Total TX: {data['total_tx']}")
                        print(f"Current MC: ${data['current_mc']:,.2f}")
                else:
                    print(f"\nNO high volume tokens detected")
                
                if rug_data and rug_data[1]:  # Check if rug_data exists and has entries
                    print("\nRUG ANALYSIS:")
                    aths, rug_info = rug_data
                    for ca, data in rug_info.items():
                        print(f"\nRug Tokens:")
                        #print(f"ATH MC: ${aths.get(ca, 0):,.2f}")
                        for name, details in token_data.items():
                            if details['ca'] == ca:

                                #print(f"Name: {name}")
                                print(f"Current MC: ${details['current_mc']:,.2f}")
                                #if aths.get(ca, 0) > 0:
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
        self.ca = "7J6p2HQXeATiby8YWgnzigRRMepCe5FrhAeNupuUpump"
    async def run(self):
        await self.dev.deployer_report(ca=self.ca)

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())