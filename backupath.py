import requests
import asyncio
import aiohttp
from marketcap import MarketcapFetcher
from env import MORALIS_API_KEY, BIRDEYE_API_KEY
from datetime import datetime, timedelta

class ATH:
    def __init__(self):
        self.time_frame = "1min"
        self.sol_rpc = MarketcapFetcher()  

    async def _get_bd_data(self, ca):
        try:
            bd_url = f"https://public-api.birdeye.so/defi/token_overview?address={ca}"
            headers = {
                "accept": "application/json",
                "x-chain": "solana",
                "X-API-KEY": BIRDEYE_API_KEY
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(bd_url, headers=headers) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    if not data or 'data' not in data:
                        print("No data in Birdeye response")
                        return None
                    
                    supply = data['data'].get('circulatingSupply')
                    if not supply:
                        print("No supply data found in Birdeye response")
                        return None
                    
                    print(f"BD Supply: {float(supply):.2f}")    
                    return float(supply)
                    
        except Exception as e:
            print(f"Birdeye API Error: {str(e)}")
            print(f"Full response data: {data if 'data' in locals() else 'No data received'}")
            return None
    

    async def calculate_all_time_high(self, ca, pair_address):
        try:
            url = f"https://solana-gateway.moralis.io/token/mainnet/pairs/{pair_address}/ohlcv"
            params = {
                "timeframe": "1min",  
                "currency": "usd",
                "fromDate": "2024-11-25",
                "toDate": "2025-11-26",
                "limit": 50
            }
            headers = {
                "Accept": "application/json",
                "X-API-Key": MORALIS_API_KEY
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    prices = data['result']
                    if not prices:
                        print("No price data available")
                        return None
                        
                    highs = [price['high'] for price in prices if 'high' in price]
                    if not highs:
                        print("No high prices found")
                        return None
                        
                    max_high = max(highs)
                    
                    token_supply = await self.sol_rpc.get_token_supply(ca)
                    if not token_supply:
                        token_supply = await self._get_bd_data(ca)
                        
                    if not token_supply:
                        print("Could not fetch token supply")
                        return None
                        
                    return max_high * token_supply

        except Exception as e:
            print(f"Error calculating ATH: {str(e)}")
            return None