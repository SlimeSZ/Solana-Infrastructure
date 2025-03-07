import asyncio
import aiohttp
from collections import defaultdict
from env import BIRDEYE_API_KEY
from datetime import datetime, timedelta

class WalletPNL:
    def __init__(self):
        self.wsol_address = "So11111111111111111111111111111111111111112"
        # Define a minimum timestamp for filtering transactions
        # Set to 0 to get all transactions or adjust days_back as needed
        days_back = 0  # Set to 0 to disable time filtering
        self.min_timestamp = int((datetime.now() - timedelta(days=days_back)).timestamp()) if days_back > 0 else 0

    def is_memecoin(self, token_address, token_name=None, token_symbol=None):
        """Determine if a token is likely a memecoin based on various indicators"""
        # Check for "pump" in the address
        if "pump" in token_address:
            #print(f"✅ Identified memecoin by 'pump' in address: {token_address}")
            return True
            
        # Common memecoin indicators in name or symbol
        meme_indicators = ["dog", "cat", "shib", "inu", "elon", "moon", "doge", 
                           "pepe", "wojak", "chad", "bonk", "cope", "trump", 
                           "frog", "based", "meme", "coin"]
        
        # Check name and symbol if available
        if token_name and any(indicator.lower() in token_name.lower() for indicator in meme_indicators):
            #print(f"✅ Identified memecoin by name: {token_name}")
            return True
            
        if token_symbol and any(indicator.lower() in token_symbol.lower() for indicator in meme_indicators):
            #print(f"✅ Identified memecoin by symbol: {token_symbol}")
            return True
            
        return False

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


    async def calculate_pnl(self, wallet_address):
        try:
            # Get the transaction history only ONCE and store it
            tx_history_response = await self.get_tx_history(wallet_address)
            if not tx_history_response:
                print(f"No transaction data for wallet: {wallet_address[:8]}")
                return {
                    'pnl': 0,
                    'tokens_traded': 0,
                    'trades_won': 0,
                    'trades_loss': 0,
                    'average_entry_per_trade': 0
                }
            
            # Process the transaction data using the stored response
            tx_data = await self.process_tx_history_from_response(wallet_address, tx_history_response)
            if not tx_data:
                print(f"No processed transaction data for wallet: {wallet_address[:8]}")
                return {
                    'pnl': 0,
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
            
            # Extract CAs from the ALREADY FETCHED tx_history_response
            raw_txs = tx_history_response.get('data', {}).get('solana', [])
            if not raw_txs:
                print(f"No solana transactions in raw history for wallet: {wallet_address[:8]}")
                return None

            # Extract CAs in order of first appearance
            ca_order = []
            for tx in raw_txs:
                balance_changes = tx.get('balanceChange', [])
                for change in balance_changes:
                    if 'tokenAccount' in change and 'address' in change:
                        ca = change.get('address')
                        if ca and ca not in ca_order and ca != self.wsol_address:
                            ca_order.append(ca)
            
            # Track PnL details by token
            token_pnl_details = {}
            
            # Process PNL in order of CA appearance
            for ca in ca_order:
                if ca not in tx_data:
                    continue
                    
                # Limit to only most recent 15 trades for each token
                txs = sorted(tx_data[ca], key=lambda x: x['timestamp'], reverse=True)[:30]
                
                if not txs:  # Skip if no transactions after limiting
                    continue
                    
                total_tokens += 1
                # Resort txs in chronological order for processing
                txs = sorted(txs, key=lambda x: x['timestamp'])
                
                # Get token info from first transaction
                token_name = txs[0]['token_name'] if txs else "Unknown"
                token_symbol = txs[0]['token_symbol'] if txs else "Unknown"
                
                # Track buys and sells separately
                token_buys = []
                token_sells = []
                token_total_bought = 0
                token_total_sold = 0
                token_sol_spent = 0
                token_sol_received = 0
                
                for tx in txs:
                    if tx['tx_type'] == 'Buy':
                        token_buys.append(tx)
                        token_total_bought += tx['token_amount']
                        token_sol_spent += tx['sol_amount']
                        total_sol_spent += tx['sol_amount']
                    else:  # Sell
                        token_sells.append(tx)
                        token_total_sold += tx['token_amount']
                        token_sol_received += tx['sol_amount']
                        
                    total_trades += 1
                
                # Calculate token PnL
                token_pnl = token_sol_received - token_sol_spent
                
                # Calculate ROI safely
                token_roi = 0
                if token_sol_spent > 0:
                    token_roi = (token_pnl / token_sol_spent) * 100
                
                # Store detailed PnL information for this token
                token_pnl_details[ca] = {
                    'name': token_name,
                    'symbol': token_symbol,
                    'total_bought': token_total_bought,
                    'total_sold': token_total_sold,
                    'sol_spent': token_sol_spent,
                    'sol_received': token_sol_received,
                    'pnl': token_pnl,
                    'roi_percent': token_roi,
                    'tx_count': len(txs),
                    'remaining': token_total_bought - token_total_sold
                }
            
            # Filter out tokens with duplicate PnL values
            pnl_values = {}
            filtered_token_pnl_details = {}
            
            for ca, details in token_pnl_details.items():
                pnl = round(details['pnl'], 6)  # Round to avoid floating point issues
                if pnl in pnl_values:
                    continue
                
                pnl_values[pnl] = True
                filtered_token_pnl_details[ca] = details
            
            # Recalculate totals based on filtered tokens
            total_wallet_pnl = sum(details['pnl'] for details in filtered_token_pnl_details.values())
            total_sol_spent = sum(details['sol_spent'] for details in filtered_token_pnl_details.values())
            total_tokens = len(filtered_token_pnl_details)
            total_trades = sum(details['tx_count'] for details in filtered_token_pnl_details.values())
            
            # Recalculate wins and losses
            total_wins = sum(1 for details in filtered_token_pnl_details.values() if details['pnl'] > 0)
            total_losses = sum(1 for details in filtered_token_pnl_details.values() if details['pnl'] < 0)
            
            avg_sol_entry = total_sol_spent / total_trades if total_trades > 0 else 0
            
            # Sort by PnL (highest first)
            sorted_tokens = sorted(filtered_token_pnl_details.items(), key=lambda x: x[1]['pnl'], reverse=True)
            
            overall_roi = (total_wallet_pnl / total_sol_spent * 100) if total_sol_spent > 0 else 0
            
            return {
                'pnl': total_wallet_pnl,
                'tokens_traded': total_tokens,
                'trades_won': total_wins,
                'trades_loss': total_losses,
                'average_entry_per_trade': avg_sol_entry,
                'overall_roi': overall_roi,
                'token_details': filtered_token_pnl_details
            }   
        
        except Exception as e:
            print(f"Error in calculate_pnl for {wallet_address[:8]}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    # New helper method to process transaction history from an already fetched response
    async def process_tx_history_from_response(self, wallet_address, tx_history):
        try:
            if not tx_history or not isinstance(tx_history, dict):
                print(f"No valid tx history for wallet: {wallet_address}")
                return {}
            
            data = tx_history.get('data', {}).get('solana', [])
            if not data:
                print(f"No solana data in tx history for wallet: {wallet_address}")
                return {}
            
            # Store token info for lookup
            token_info_cache = {}

            # We'll track all transactions by token address
            tx_data = defaultdict(list)
            skipped_count = 0
            processed_count = 0
            
            for tx_index, tx in enumerate(data):
                # Get transaction hash
                hash = tx.get('txHash', '')
                if not hash:
                    continue
                
                timestamp = tx.get('blockTime', 0)
                # Convert timestamp to datetime object and integer timestamp
                date_str = "Unknown"
                try:
                    if isinstance(timestamp, str):
                        # Try ISO format timestamp parsing
                        date = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        date_str = date.strftime('%Y-%m-%d %H:%M')
                        timestamp = int(date.timestamp())
                    else:
                        # Assume it's a UNIX timestamp
                        date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
                except Exception as e:
                    print(f"  ⚠️ Warning: Could not parse timestamp {timestamp}: {str(e)}")
                    # Set a default timestamp to prevent comparison errors
                    timestamp = 0
                
                # Skip older transactions if desired (after converting to int)
                if timestamp < self.min_timestamp:
                    continue
                    
                # Get balance changes
                balance_change_fields = tx.get('balanceChange', [])
                if not balance_change_fields:
                    continue

                # Track SOL and token changes in this transaction
                sol_changes = []
                token_changes = []
                
                # Process each balance change in this transaction
                for change in balance_change_fields:
                    # Process SOL changes
                    if change.get('address') == self.wsol_address:
                        sol_lamports = change.get('amount', 0)
                        sol_decimals = change.get('decimals', 9)
                        sol_amount = sol_lamports / (10 ** sol_decimals)
                        sol_changes.append(sol_amount)
                    # Process token changes
                    elif 'tokenAccount' in change:
                        ca = change.get('address')
                        token_name = change.get('name', "Unknown")
                        token_symbol = change.get('symbol', "Unknown")
                        
                        # Skip wrapped SOL
                        if ca == self.wsol_address:
                            continue
                        
                        # Check if we've already determined if this is a memecoin
                        if ca not in token_info_cache:
                            # If we don't have token info yet, check if it's a memecoin
                            is_meme = self.is_memecoin(ca, token_name, token_symbol)
                            token_info_cache[ca] = {
                                'name': token_name,
                                'symbol': token_symbol,
                                'is_memecoin': is_meme
                            }
                        else:
                            is_meme = token_info_cache[ca]['is_memecoin']
                        
                        # Skip non-memecoins
                        if not is_meme:
                            continue
                        
                        token_lamports = change.get('amount', 0)
                        token_decimals = change.get('decimals', 6)
                        token_amount = token_lamports / (10 ** token_decimals)
                        
                        token_changes.append({
                            'ca': ca,
                            'amount': token_amount,
                            'name': token_name,
                            'symbol': token_symbol
                        })
                
                # Process transactions that have both SOL and token changes (likely swaps)
                if sol_changes and token_changes:
                    for token_change in token_changes:
                        ca = token_change['ca']
                        token_amount = token_change['amount']
                        token_name = token_change['name']
                        token_symbol = token_change['symbol']
                        
                        # If token amount is positive, it's a buy (received tokens, spent SOL)
                        # If token amount is negative, it's a sell (sent tokens, received SOL)
                        is_buy = token_amount > 0
                        
                        # Sum all SOL changes in this transaction
                        sol_amount = sum(sol_changes)
                        
                        # Validate if this looks like a legitimate swap
                        is_valid_swap = False
                        
                        # For buys: we get tokens (positive) and spend SOL (negative)
                        # For sells: we lose tokens (negative) and get SOL (positive)
                        if (is_buy and sol_amount < 0) or (not is_buy and sol_amount > 0):
                            is_valid_swap = True
                        
                        if not is_valid_swap:
                            skipped_count += 1
                            continue
                        
                        # Process valid swap
                        tx_type = 'Buy' if is_buy else 'Sell'
                        processed_count += 1
                        
                        tx_data[ca].append({
                            'hash': hash,
                            'timestamp': timestamp,
                            'date': date_str,
                            'token_ca': ca,
                            'token_name': token_name,
                            'token_symbol': token_symbol,
                            'tx_type': tx_type,
                            'sol_amount': abs(sol_amount),
                            'token_amount': abs(token_amount),
                            'raw_sol_amount': sol_amount,
                            'raw_token_amount': token_amount
                        })

            print(f"\n📊 Processed {processed_count} valid swaps across {len(tx_data)} tokens")
            print(f"⏭️ Skipped {skipped_count} invalid transactions")
            
            return tx_data

        except Exception as e:
            print(f"Error in process_tx_history: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}

    # The original process_tx_history method now calls the helper method
    async def process_tx_history(self, wallet_address):
        try:
            tx_history = await self.get_tx_history(wallet_address)
            return await self.process_tx_history_from_response(wallet_address, tx_history)
        except Exception as e:
            print(f"Error in process_tx_history: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}