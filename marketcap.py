import asyncio
import aiohttp
import requests
import json
from typing import Dict, Any, Tuple
from env import BIRDEYE_API_KEY

class MarketcapFetcher:
    def __init__(self, rpc_endpoint: str = "https://api.mainnet-beta.solana.com"):
        self.rpc_endpoint = rpc_endpoint
        self.gecko_base_url = "https://api.geckoterminal.com/api/v2/simple/networks"
        self.supply_backup = Supply()
        self.price = Price()

    async def get_token_supply(self, ca: str) -> float:
        payload = {
            "jsonrpc": "2.0", 
            "id": 1,
            "method": "getTokenSupply",
            "params": [ca]
        }
        
        try:
            if not ca:
                print("Invalid CA Not found, trying backup supply...")
                return await self.supply_backup.supply(ca)
                
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.rpc_endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 200:
                        print(f"RPC request failed with status: {response.status}, trying backup supply...")
                        return await self.supply_backup.supply(ca)
                        
                    data = await response.json()
                    
                    if 'error' in data:
                        print(f"RPC error: {data['error']}, trying backup supply...")
                        return await self.supply_backup.supply(ca)
                    
                    if 'result' not in data:
                        print(f"No result in RPC response: {data}, trying backup supply...")
                        return await self.supply_backup.supply(ca)
                        
                    if 'value' not in data['result']:
                        print(f"No value in RPC result: {data['result']}, trying backup supply...")
                        return await self.supply_backup.supply(ca)
                        
                    data_supply = float(data['result']['value']['amount'])
                    data_decimals = int(data['result']['value']['decimals'])
                    supply = data_supply / (10 ** data_decimals)
                    print(f"Got supply from RPC: {supply}")
                    return supply

        except Exception as e:
            print(f"Error fetching token supply: {str(e)}, trying backup supply...")
            return await self.supply_backup.supply(ca)

    async def backup_token_price(self, ca):
        url = f"https://public-api.birdeye.so/defi/v3/token/market-data?address={ca}"
        headers = {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": BIRDEYE_API_KEY
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        print(f"Birdeye request failed with status: {response.status}")
                        return None
                        
                    data = await response.json()
                    if not data:
                        print("No data in Birdeye response")
                        return None
                        
                    token_data = data.get('data', {})
                    price = token_data.get('price', 0)
                    if not price:
                        print("Unable to get price from Birdeye")
                        return None
                        
                    print(f"Got price: {price}")
                    return price
        except Exception as e:
            print(f"Error getting price from Birdeye: {str(e)}")
            return None

    async def calculate_marketcap(self, ca: str) -> float:
        """
        Calculate token marketcap by multiplying supply by price.
        Returns 0.0 on failure instead of None to prevent comparison errors.
        """
        if not ca or not isinstance(ca, str):
            print("Invalid CA provided")
            return 0.0
            
        try:
            # Normalize CA by trimming whitespace
            ca = ca.strip()
            
            # Get supply (this already includes backup attempt)
            supply = await self.get_token_supply(ca)
            
            # Handle None or non-positive supply
            if supply is None or supply <= 0:
                print(f"Failed to get valid supply for {ca}, defaulting to 0")
                return 0.0
                
            print(f"Supply obtained: {supply}")
                    
            # Get price
            price = await self.price.get_price_only(ca)
            
            # Handle None price
            if price is None:
                print(f"Failed to get price for {ca}, defaulting to 0")
                return 0.0
                
            # Ensure we have valid numerical values
            try:
                supply = float(supply)
                price = float(price)
            except (ValueError, TypeError):
                print(f"Error converting price or supply to float for {ca}")
                return 0.0
            
            # Calculate marketcap
            mc = price * supply
            print(f"Calculated MC for {ca}: {mc}")
            return mc
                
        except Exception as e:
            print(f"Error calculating marketcap for {ca}: {str(e)}")
            return 0.0  # Return 0 instead of None to prevent comparison errors

class Main:
    def __init__(self):
        self.rpc = MarketcapFetcher()
        self.ca = "CUUZJST5B8fs43ikm5adsQrw4qz5n4mAgEiTzii2pump"
    
    async def run(self):
        data = await self.rpc.calculate_marketcap(self.ca)
        if data:
            print(data)

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())
