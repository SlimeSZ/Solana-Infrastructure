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
                    response.raise_for_status()
                    return await response.json()
        except Exception as e:
            print(str(e))
            import traceback
            traceback.print_exc()
            return None
    
    async def process_tx_history(self, wallet_address):
        try:
            tx_history = await self.get_tx_history(wallet_address)
            if not tx_history:
                return
            
            data = tx_history.get('data', {}).get('solana', [])
            if not data:
                return
            
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

                        """
                        print(f"{"-" * 30}\nTx: {hash}")
                        print(f"Type: {'Buy' if is_buy else 'Sell'}")
                        print(f"Sol Amount: {sol_amount}")
                        print(f"Token Amount: {token_amount}")
                        print(f"Timestamp: {tx.get('blockTime')}")
                        print(f"{"-" * 30}")
                        """

            return tx_data
        except Exception as e:
            print(str(e))
            import traceback
            traceback.print_exc()
            return None
        
    async def calculate_pnl(self, wallet_address):
        try:
            tx_data = await self.process_tx_history(wallet_address)
            if not tx_data:
                return
                
            total_tokens = 0
            total_wallet_pnl = 0
            total_wins = 0
            total_losses = 0
            ca_order = []  

            total_sol_spent = 0
            
            # Get raw response to determine CA order
            raw_response = await self.get_tx_history(wallet_address)
            raw_txs = raw_response.get('data', {}).get('solana', [])

            
            # Extract CAs in order of first appearance
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
                total_sol_spent = 0
                total_sol_returned = 0
                total_trades = 0
                
                #print(f"\nToken CA: {ca}\n{'*' * 30}")
                
                for tx in txs:  # Use original order from response
                    if tx['tx_type'] == 'Buy':
                        total_sol_spent += tx['sol_amount']
                        total_sol_spent += tx['sol_amount']
                    else:
                        total_sol_returned += tx['sol_amount']
                    total_trades += 1
                    
                    """
                    print(f"Transaction: {tx['hash']}")
                    print(f"Type: {tx['tx_type']}")
                    print(f"SOL Amount: {tx['sol_amount']:.4f}")
                    print(f"Token Amount: {tx['token_amount']:.4f}")
                    print(f"Timestamp: {tx['timestamp']}")
                    print("-" * 30)
                    """
                
                token_pnl = total_sol_returned - total_sol_spent
                total_wallet_pnl += token_pnl

                if token_pnl > 0:
                    total_wins += 1
                else:
                    total_losses += 1
            
            avg_sol_entry = total_sol_spent / total_trades if total_trades > 0 else 0
            """
                print(f"\nToken Summary:")
                print(f"Total SOL Spent: {total_sol_spent:.4f}")
                print(f"Total SOL Returned: {total_sol_returned:.4f}")
                print(f"Token PNL: {token_pnl:.4f} SOL")
                print(f"Total Trades: {total_trades}")
                print("=" * 50)

            print(F"Total Trades Took (SHOWING UP-TO LAST 100): {total_tokens}")
            print(f"Trades won: {total_wins}")
            print(f"Trades lost: {total_losses}")
            """
                
            return {
                'last_100_tx_pnl': total_wallet_pnl,
                'tokens_traded': total_tokens,
                'trades_won': total_wins,
                'trades_loss': total_losses,
                'average_entry_per_trade': avg_sol_entry
            }   
        
        except Exception as e:
            print(f"Error in calculate_pnl: {str(e)}")
            import traceback
            traceback.print_exc()
                
"""
class Main:
    def __init__(self):
        self.w = WalletPNL()

    async def run(self):
        await self.w.calculate_pnl(wallet_address="wallet_address_here")
        
        #if data:
            #print(data)

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())
"""
        
        