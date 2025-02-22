import asyncio
import aiohttp
from env import BIRDEYE_API_KEY
from backupsupply import Supply

class MarketcapFetcher:
    def __init__(self, rpc_endpoint: str = "https://api.mainnet-beta.solana.com"):
        self.rpc_endpoint = rpc_endpoint
        self.gecko_base_url = "https://api.geckoterminal.com/api/v2/simple/networks"
        self.supply_backup = Supply()
    
    async def get_token_supply(self, ca):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenSupply",
            "params": ca
        }
        headers = {"Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.rpc_endpoint,
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        return await self.supply_backup.supply(ca)
                    data = await response.json()
                    print(data) if data else print(f"Error getting data")
                    return data
        except Exception as e:
            print(str(e))
            return None

class Main:
    def __init__(self):
        self.sup = MarketcapFetcher()
    async def run(self):
        await self.sup.get_token_supply(ca="e7DX4nGxAnJcUNBNF2UTBPZYRseLXQfegh8Cxfstart")

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())
            