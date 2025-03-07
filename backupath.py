import requests
import asyncio
import aiohttp
from env import MORALIS_API_KEY, BIRDEYE_API_KEY
from datetime import datetime, timedelta
from marketcapfinal import Supply

class BATH:
    def __init__(self):
        self.time_frame = "5min"
        self.s = Supply()

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
                        return None
                        
                    highs = [price['high'] for price in prices if 'high' in price]
                    if not highs:
                        return None
                        
                    max_high = max(highs)
                    
                    token_supply = self.s.supply(ca)
                    if not token_supply:
                        print("Could not fetch token supply for ath calculations")
                        return None
                        
                    return max_high * token_supply

        except Exception as e:
            print(f"Error calculating ATH: {str(e)}")
            return None