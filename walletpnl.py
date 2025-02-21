import asyncio
import requests
import aiohttp
from collections import defaultdict
from env import BIRDEYE_API_KEY

class WAlletPNL:
    def __init__(self):
        self.wsol_address = "So11111111111111111111111111111111111111112"

    async def get_tx_history(self, wallet_address):
        url = f"https://public-api.birdeye.so/v1/wallet/tx_list?wallet={wallet_address}&limit=100"
        headers = {
            "accept": "application/json",
            "x-chain": "solana",
            "X-API-KEY": BIRDEYE_API_KEY
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and isinstance(data, dict):
                            return data
                        print(f"Invalid response data format: {data}")
                    else:
                        print(f"Bad status code: {response.status}")
                    return None
        except Exception as e:
            print(f"Error in get_tx_history: {str(e)}")
            return None
    
    async def process_tx_history(self, wallet_address):
        try:
            tx_history = await self.get_tx_history(wallet_address)
            if not tx_history or not isinstance(tx_history, dict):
                print(f"No valid tx history for wallet: {wallet_address}")
                return {}
            
            data = tx_history.get('data', {}).get('solana', [])
            if not data:
                print(f"No solana data in tx history for wallet: {wallet_address}")
                return {}
            
            tx_data = defaultdict(list)

            for tx in data:
                if tx.get('from') != wallet_address:
                    continue
                hash = tx.get('txHash', '')
                if not hash:
                    continue
                balance_change_fields = tx.get('balanceChange', [])
                if not balance_change_fields or len(balance_change_fields) < 2:
                    continue

                token_tx = None
                sol_amount = 0
                token_info = {}
                
                for change in balance_change_fields:
                    #GET SOL AMOUNT BOUGHT/SOL
                    if change.get('address') == self.wsol_address:
                        sol_lamports = change.get('amount', 0)
                        sol_decimals = change.get('decimals', 9)
                        sol_amount = abs(sol_lamports) / (10 ** sol_decimals)
                    #GET TOKEN AMOUNT BOUGHT/SOLD
                    elif 'tokenAccount' in change:
                        ca = change.get('address')
                        token_lamports = change.get('amount', 0)
                        token_decimals = change.get('decimals', 6)
                        token_amount = abs(token_lamports) / (10 ** token_decimals)
                        is_buy = token_lamports > 0
                        
                        token_info = {
                            'hash': hash,
                            'timestamp': tx.get('blockTime'),
                            'token_ca': ca,
                            'tx_type': 'Buy' if is_buy else 'Sell',
                            'sol_amount': sol_amount,
                            'token_amount': token_amount
                        }
                        tx_data[ca].append(token_info)

            print(f"Processed {len(tx_data)} tokens for wallet {wallet_address[:8]}...")
            return tx_data

        except Exception as e:
            print(f"Error in process_tx_history: {str(e)}")
            return {}
        
    async def calculate_pnl(self, wallet_address):
        try:
            tx_data = await self.process_tx_history(wallet_address)
            if not tx_data:
                print(f"No transaction data for wallet: {wallet_address[:8]}")
                return {
                    'last_100_tx_pnl': 0,
                    'tokens_traded': 0,
                    'trades_won': 0,
                    'trades_loss': 0,
                    'average_entry_per_trade': 0
                }
                
            total_tokens = 0
            total_wallet_pnl = 0
            total_wins = 0
            total_losses = 0
            total_trades = 0
            total_sol_spent = 0
            
            # Get raw response to determine CA order
            raw_response = await self.get_tx_history(wallet_address)
            if not raw_response:
                print(f"No raw transaction history for wallet: {wallet_address[:8]}")
                return None
                
            raw_txs = raw_response.get('data', {}).get('solana', [])
            if not raw_txs:
                print(f"No solana transactions in raw history for wallet: {wallet_address[:8]}")
                return None

            # Extract CAs in order of first appearance
            ca_order = []
            for tx in raw_txs:
                balance_changes = tx.get('balanceChange', [])
                for change in balance_changes:
                    if 'tokenAccount' in change:
                        ca = change.get('address')
                        if ca and ca not in ca_order:
                            ca_order.append(ca)
            
            # Process PNL in order of CA appearance
            for ca in ca_order:
                if ca not in tx_data:
                    continue
                    
                total_tokens += 1
                txs = tx_data[ca]
                
                for tx in txs:
                    if tx['tx_type'] == 'Buy':
                        total_sol_spent += tx['sol_amount']
                    else:  # Sell
                        total_wallet_pnl += tx['sol_amount']  # Add the SOL received from selling
                    total_trades += 1
                
                # Calculate if this token was profitable
                token_pnl = sum(tx['sol_amount'] if tx['tx_type'] == 'Sell' else -tx['sol_amount'] for tx in txs)
                if token_pnl > 0:
                    total_wins += 1
                else:
                    total_losses += 1
            
            avg_sol_entry = total_sol_spent / total_trades if total_trades > 0 else 0
            
            print(f"Calculated PNL for {wallet_address[:8]}: {total_wallet_pnl:.4f} SOL")
            return {
                'last_100_tx_pnl': total_wallet_pnl,
                'tokens_traded': total_tokens,
                'trades_won': total_wins,
                'trades_loss': total_losses,
                'average_entry_per_trade': avg_sol_entry
            }   
        
        except Exception as e:
            print(f"Error in calculate_pnl for {wallet_address[:8]}: {str(e)}")
            return None
                

class Main:
    def __init__(self):
        self.w = WAlletPNL()

    async def run(self):
        data = await self.w.calculate_pnl(wallet_address="4ET2AazzGBwZ5sRsQWoAFRFJPosRN3d4XkutTP3LZBtu")   
        if data:
            print(data)

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())

        
        