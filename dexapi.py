import asyncio
import aiohttp
import requests

class DexScreenerAPI:
    def __init__(self):
        self.reset_data()
    
    def reset_data(self):
        self.token_name = None
        self.token_ca = None
        self.token_mc = None
        self.token_created_at = None

        self.token_5m_vol = None
        self.token_1h_vol = None
        self.token_6h_vol = None
        self.token_24h_vol = None

        self.token_5m_buys = None
        self.token_5m_sells = None
        self.token_1h_buys = None
        self.token_1h_sells = None
        self.token_6h_buys = None
        self.token_6h_sells = None
        self.token_24h_buys = None
        self.token_24h_sells = None

        self.token_5m_price_change = None
        self.token_1h_price_change = None
        self.token_6h_price_change = None
        self.token_24h_price_change = None

        self.token_liquidity = None

        self.has_tg = False
        self.has_x = False
        self.x_link = None
        self.tg_link = None
        self.token_on_dex = False
        self.token_on_pump = False
        
        self.token_dex_url = None
        self.pair_created_at = None

        self.pool_address = None
        
    async def fetch_token_data_from_dex(self, ca):
        self.reset_data()
        print(f"\n=== Fetching DexScreener Data for {ca[:8]}... ===")

        url = f"https://api.dexscreener.com/latest/dex/search?q={ca}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        print(f"[ERROR] Dex Screener API Returned Status: {response.status}")
                        return
                    
                    json_data = await response.json()
                    if not json_data or 'pairs' not in json_data or not json_data['pairs']:
                        self.token_on_pump = True
                        return
                    
                    self.token_on_dex = True

                    found_pair = False
                    for pair in json_data['pairs']:
                        self.token_name = pair.get('baseToken').get('name')
                        
                        self.pool_address = pair.get('pairAddress', '')
                        print(f"Pair Add: {self.pool_address}")
                        self.pair_created_at = pair.get('pairCreatedAt')
                        found_pair = True
                        #get mc
                        self.token_mc = float(pair.get('fdv', 0))

                        #get volume
                        volume_data = pair.get('volume', {})
                        self.token_5m_vol = float(volume_data.get('m5', 0))
                        self.token_1h_vol = float(volume_data.get('h1', 0))
                        self.token_6h_vol = float(volume_data.get('h6', 0))
                        self.token_24h_vol = float(volume_data.get('h24', 0))

                        #get buys & sells
                        txns_data = pair.get('txns', {})
                        m5_txns = txns_data.get('m5', {})
                        self.token_5m_buys = int(m5_txns.get('buys', 0))
                        self.token_5m_sells = int(m5_txns.get('sells', 0))
                        h1_txns = txns_data.get('h1', {})
                        self.token_1h_buys = int(h1_txns.get('buys', 0))
                        self.token_1h_sells = int(h1_txns.get('sells', 0))
                        h24_txns = txns_data.get('h24', {})
                        self.token_24h_buys = int(h24_txns.get('buys', 0))
                        self.token_24h_sells = int(h24_txns.get('sells', 0))

                        #get price change
                        priceChange_data = pair.get('priceChange', {})
                        self.token_5m_price_change = priceChange_data.get('m5', 0)
                        self.token_1h_price_change = priceChange_data.get('h1', 0)
                        self.token_24h_price_change = priceChange_data.get('h24', 0)

                        #get liquidity
                        liquidity_data = pair.get('liquidity', {})
                        self.token_liquidity = float(liquidity_data.get('usd', 0))
                        
                        #x, tg, and dex url
                        info = pair.get('info', {})
                        socials = info.get('socials', [])
                        for social in socials:
                            if social['type'] == 'telegram':
                                self.has_tg = True
                                self.tg_link = social.get('url', 'No Telegram Link')
                            if social['type'] == 'twitter':
                                self.has_x = True
                                self.x_link = social.get('url', 'No Twitter Link')
                        self.token_dex_url = pair.get('url', '')
                        
                        break
                
                return {
                    'token_name': self.token_name,
                    'token_created_at': self.pair_created_at,
                    'pool_address': self.pool_address,
                    'token_mc': self.token_mc,
                    'token_5m_vol': self.token_5m_vol,
                    'self.token_1h_vol': self.token_1h_vol,
                    'token_liquidity': self.token_liquidity,
                    "socials": {
                        "telegram": self.tg_link if self.has_tg else None,
                        "twitter": self.x_link if self.has_x else None
                    },
                    "dex_url": self.token_dex_url
                }
                    
        except Exception as e:
            print(f"[ERROR] Error in fetching Data from Dex for {ca[:8]}...: \n{str(e)}")


async def main():
    async with aiohttp.ClientSession() as session:
        dex = DexScreenerAPI()
        ca = "HEZ6KcNNUKaWvUCBEe4BtfoeDHEHPkCHY9JaDNqrpump"
        result = await dex.fetch_token_data_from_dex(ca)
        print(result)

if __name__ == "__main__":
    asyncio.run(main())
