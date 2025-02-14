import requests
import asyncio
import aiohttp
from env import BIRDEYE_API_KEY

class BuySellTradeUniqueData:
    def __init__(self):
        pass

    async def fetch(self, ca):
        url = f"https://public-api.birdeye.so/defi/v3/token/trade-data/single?address={ca}"
        headers = {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": BIRDEYE_API_KEY
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    response_data = await response.json()
                    if not response_data:
                        return
                    data = response_data.get('data', {})
                return data
        except Exception as e:
            print(str(e))
            import traceback
            traceback.print_exc()
            return None
        
    async def process(self, ca):
       try:
           data = await self.fetch(ca)
           if not data:
               return

           holders = data.get('holder', 0)
           
           unique_wallet_30m = data.get('unique_wallet_30m', 0) #total unique wallets up to now
           
           unique_wallet_history_30m = data.get('unique_wallet_history_30m', 0) #new unique wallets in last 30 min
           
           unique_wallet_30m_change = data.get('unique_wallet_30m_change_percent', 0)
           
           unique_wallet_1h = data.get('unique_wallet_1h', 0)
           
           unique_wallet_history_1h = data.get('unique_wallet_history_1h', 0)
           
           unique_wallet_1h_change = data.get('unique_wallet_1h_change_percent', 0)
           
           unique_wallet_2h = data.get('unique_wallet_2h', 0)
           
           unique_wallet_history_2h = data.get('unique_wallet_history_2h', 0)
           
           unique_wallet_2h_change = data.get('unique_wallet_2h_change_percent', 0)
           
           unique_wallet_4h = data.get('unique_wallet_4h', 0)
           
           unique_wallet_history_4h = data.get('unique_wallet_history_4h', 0)
           
           unique_wallet_4h_change = data.get('unique_wallet_4h_change_percent', 0)
           
           unique_wallet_8h = data.get('unique_wallet_8h', 0)
           
           unique_wallet_history_8h = data.get('unique_wallet_history_8h', 0)
           
           unique_wallet_8h_change = data.get('unique_wallet_8h_change_percent', 0)
           
           unique_wallet_24h = data.get('unique_wallet_24h', 0)
           
           unique_wallet_history_24h = data.get('unique_wallet_history_24h', 0)
           
           unique_wallet_24h_change = data.get('unique_wallet_24h_change_percent', 0)

           trade_30m = data.get('trade_30m', 0) #int num of total trades
           
           trade_history_30m = data.get('trade_history_30m', 0) #new int trades in last 30 min only
           
           trade_30m_change = data.get('trade_30m_change_percent', 0) #trade increase/decrease %
           
           sell_30m_change = data.get('sell_30m_change_percent', 0)
           
           buy_30m = data.get('buy_30m', 0)
           
           buy_history_30m = data.get('buy_history_30m', 0)
           
           buy_30m_change = data.get('buy_30m_change_percent', 0)

           return {
                'holders': data.get('holder', 0),  # Should be 816 from API
                'new_unique_wallets_30_min_count': data.get('unique_wallet_history_30m', 0),  # Should be 425 from API
                'new_unique_wallets_30_min_percent_change': data.get('unique_wallet_30m_change_percent', 0),  # Should be 163.52%
                'trade_30_min_percent_change': data.get('trade_30m_change_percent', 0),  # Should be 54.83%
                'buy_30_min_percent_change': data.get('buy_30m_change_percent', 0),  # Should be 59.80%
                'sell_30_min_percent_change': data.get('sell_30m_change_percent', 0)  # Should be 49.11%
            }

       except Exception as e:
           print(str(e))
           return None
       
class Tokenomics:
    def __init__(self):
        pass

    async def fetch(self, ca: str):
        url = f"https://public-api.birdeye.so/defi/token_overview?address={ca}"
        headers = {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": BIRDEYE_API_KEY
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    response.raise_for_status()
                    response_data = await response.json()
                    if not response_data:
                        return
                    data = response_data.get('data', {})
                    return data
        except Exception as e:
            print(str(e))
            import traceback
            traceback.print_exc()
            return None
        
    async def process(self, ca: str):
        try:
            data = await self.fetch(ca)
            if not data:
                return
            token_name = data.get('name', '')
            marketcap = data.get('marketCap', 0)
            liquidity = data.get('liquidity', 0)
            m30_vol = data.get('v30mUSD', 0)
            m30_vol_change = data.get('v30mChangePercent', None)

            # Handle social links more safely
            extensions = data.get('extensions', {})
            if extensions is None:
                extensions = {}
                
            twitter = extensions.get('twitter', '')
            telegram = extensions.get('telegram', '')

            return {
                'name': token_name,
                'marketcap': marketcap,
                'liquidity': liquidity,
                '30_min_vol': m30_vol,
                '30_min_vol_percent_change': m30_vol_change,
                'twitter': twitter,
                'telegram': telegram
            }
        except Exception as e:
            print(str(e))
            import traceback
            traceback.print_exc()
            return None
            
            


class Main:
    def __init__(self):
        self.bstd = BuySellTradeUniqueData()
        self.tkn = Tokenomics()

        self.ca = ""
    
    async def run(self):
        data = await self.bstd.fetch(ca=self.ca)
        if data:
            print(data)

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())