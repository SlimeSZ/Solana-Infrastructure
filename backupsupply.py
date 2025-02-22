import requests
import asyncio
import aiohttp
from env import BIRDEYE_API_KEY

class Supply:
    def __init__(self):
        pass

    async def supply(self, ca):
        url = f"https://public-api.birdeye.so/defi/token_overview?address={ca}"
        headers = {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": BIRDEYE_API_KEY
        }
        
        print(f"\n=== Starting Backup Supply Fetch ===")
        print(f"Fetching supply for: {ca}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url=url, headers=headers) as response:
                    if response.status == 200:
                        try:
                            data = await response.json()
                            print(f"Raw data received: {data}")
                            
                            if not data:
                                print("No data received from Birdeye")
                                return None
                                
                            if not isinstance(data, dict):
                                print(f"Invalid data format: {type(data)}")
                                return None
                                
                            token_data = data.get('data', {})
                            print(f"Token data: {token_data}")
                            
                            if not token_data:
                                print("No token data found in response")
                                return None
                                
                            supply = token_data.get('circulatingSupply', 0)
                            print(f"Found supply value: {supply}")
                            
                            if supply:
                                print(f"Successfully got supply: {supply}")
                                return supply
                            else:
                                print("No supply value in data")
                                return None
                                
                        except Exception as e:
                            print(f"Error parsing response: {str(e)}")
                            return None
                    else:
                        print(f"Bad response status: {response.status}")
                        return None
                        
        except Exception as e:
            print(f"Request error: {str(e)}")
            return None

class Main:
    def __init__(self):
        self.s = Supply()
        
    async def run(self):
        supply = await self.s.supply(ca="e7DX4nGxAnJcUNBNF2UTBPZYRseLXQfegh8Cxfstart")
        if supply:
            print(f"Supply: {supply}")

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())
