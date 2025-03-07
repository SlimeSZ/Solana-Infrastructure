from getohlcv import OH
from supportresistance import SupportResistance
import asyncio
import pandas as pd
import numpy as np
import aiohttp
from webhooks import TradeWebhook
from env import OB_WEBHOOK
from datetime import datetime
from marketcapfinal import Price, Supply, Marketcap

class OrderBlock:
    def __init__(self):
        self.sr = SupportResistance()  # for helper methods import
        self.o = OH()
        self.timeframe = "1min"  
        self.active_obs = []
        self.short_timeframes = ["1min", "5min", "10min"]  # Reduced set to avoid redundancy
        self.longer_timeframes = ["5min", "10min", "30min"]  # Reduced set to avoid redundancy
        self.data_cache = {}  # Cache for OHLCV data
        self.ob_cache = {}    # Cache for OB results
        self.last_analysis_time = {}  # Track when we last analyzed each token
        self.s = Supply()
        self.p = Price()
        self.mc = Marketcap()
        
    async def mark_ob(self, ca, data, supply):
        """Analyze OHLCV data to identify order blocks"""
        try:
            print("\n=== Starting mark_ob ===")
            if not ca or not data:
                print("Error: Missing required parameters")
                return None
            if not supply:
                try:
                    supply = await self.s.supply(ca)
                    if not supply:
                        print("Error: Could not get token supply from any source")
                        return None
                except Exception as e:
                    print(f"Error in backup supply: {str(e)}")
                    return None
                                
            df = await self.sr._convert(data, supply)
            
            if df is None:
                print("Error: Data conversion failed")
                return None
                
            if df.empty:
                print("Error: Empty DataFrame created")
                return None
                
            required_columns = ['high', 'low', 'open', 'close', 'volume']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                print(f"Error: DataFrame missing columns: {missing_columns}")
                return None

            # Continue with OB detection logic
            df['high_mc'] = df['high']
            df['low_mc'] = df['low']
            
            ob_top = []
            ob_bottom = []
            ob_volume = []
            ob_strength = []
            
            print("\n=== Beginning OB Detection ===")
            lookback = 150  # Only look at last 150 candles
            start_idx = max(3, len(df) - lookback)
            print(f"Analyzing last {lookback} candles...")
            
            # Calculate volume moving average
            df['vol_sum_3'] = df['volume'].rolling(window=3, min_periods=1).sum()

            ob_count = 0
            for i in range(start_idx, len(df)-1):
                curr_candle = df.iloc[i]
                prev_candle = df.iloc[i-3:i]
                next_candle = df.iloc[i+1]
                
                curr_vol = curr_candle['volume']
                prev_vol_mean = prev_candle['volume'].mean()
                high_vol = curr_vol > prev_vol_mean * 0.1  # 10% more vol than prev candle

                # Check for bullish order block
                if (next_candle['close'] > curr_candle['high'] 
                    and high_vol and curr_candle['close'] > curr_candle['open']):
                    ob_count += 1
                    print(f"\n🟢 Bullish Order Block #{ob_count} Detected!")
                    print(f"MC Range: ${curr_candle['low']:.8f} - ${curr_candle['high']:.8f}")
                    print(f"Volume: {curr_vol:.2f}")
                    
                    ob_top.append(curr_candle['high'])
                    ob_bottom.append(curr_candle['low'])
                    ob_volume.append(curr_candle['vol_sum_3'])
                    
                    strength = min(curr_vol, prev_vol_mean) / max(curr_vol, prev_vol_mean)
                    ob_strength.append(strength)
                    print(f"OB Strength: {strength:.2%}")

            return {
                'ob_top': ob_top,
                'ob_bottom': ob_bottom,
                'ob_volume': ob_volume,
                'ob_strength': ob_strength,
                'ob_count': ob_count,
                'total_candles_analyzed': len(df) - 4
            }

        except Exception as e:
            print(f"Error in mark_ob: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    


    async def update_order_blocks(self, ca, pair_address, token_name, supply, data, short_timeframes=None, longer_timeframes=None):
        try:
            if not pair_address:
                print("Error: No pair address provided")
                return None  # Return None instead of False for consistency
                
            # Extract CA from token name if it contains it
            if not ca and token_name and "(" in token_name:
                try:
                    ca_part = token_name.split("(")[1].split(")")[0]
                    if ca_part.startswith("0x") or len(ca_part) > 30:
                        ca = ca_part
                        print(f"Extracted CA from token name: {ca}")
                except:
                    print("Could not extract CA from token name")
            
            # If we STILL don't have a CA, use pair_address as CA to avoid errors
            if not ca:
                print(f"No CA available, using pair address as fallback: {pair_address}")
                ca = pair_address
                
            # Use provided timeframes or fall back to defaults
            _short_timeframes = short_timeframes or self.short_timeframes
            _longer_timeframes = longer_timeframes or self.longer_timeframes
                
            # Create cache key - use pair_address if no token_name
            cache_key = f"{pair_address}_{token_name if token_name else 'unknown'}"
            
            # Check if we've analyzed this recently (within 2 minutes)
            current_time = datetime.now()
            if cache_key in self.last_analysis_time:
                time_diff = (current_time - self.last_analysis_time[cache_key]).total_seconds()
                if time_diff < 120:  # 2 minutes
                    if cache_key in self.ob_cache:
                        print(f"Using cached OB results for {token_name} (age: {time_diff:.0f}s)")
                        return self.ob_cache[cache_key]
            
            # Process new order blocks
            if hasattr(self, 'active_obs') and self.active_obs:
                print(f"Processing potential new OBs for {token_name}")
                
                # Track new order blocks to add
                new_obs = []
                new_ob_found = False
                
                # Get the temporary OBs from timeframe selection
                temp_result = None
                for tf in _short_timeframes + _longer_timeframes:
                    temp_key = f"{pair_address}_{tf}"
                    if temp_key in self.ob_cache:
                        temp_result = self.ob_cache[temp_key]
                        break
                        
                if not temp_result:
                    # If we don't have cached results, get them now
                    temp_result = await self.mark_ob(ca=ca, data=data, supply=supply)
                
                if temp_result and temp_result.get('ob_count', 0) > 0:
                    # Check each detected order block
                    for i in range(temp_result['ob_count']):
                        new_ob = {
                            'top': temp_result['ob_top'][i],
                            'bottom': temp_result['ob_bottom'][i],
                            'volume': temp_result['ob_volume'][i],
                            'strength': temp_result['ob_strength'][i],
                            'time_found': datetime.now()
                        }
                        
                        # Check if this is a duplicate of an existing order block
                        is_duplicate = False
                        for existing_ob in self.active_obs:
                            # If top and bottom are within 1% of an existing OB, consider it a duplicate
                            top_match = abs(existing_ob['top'] - new_ob['top']) / existing_ob['top'] < 0.01
                            bottom_match = abs(existing_ob['bottom'] - new_ob['bottom']) / existing_ob['bottom'] < 0.01
                            
                            if top_match and bottom_match:
                                is_duplicate = True
                                break
                        
                        # Only add if not a duplicate
                        if not is_duplicate:
                            new_obs.append(new_ob)
                            new_ob_found = True
                            print(f"New unique order block added: ${new_ob['bottom']:.2f} - ${new_ob['top']:.2f}")
                    
                    # Add new OBs to active list
                    if new_obs:
                        self.active_obs.extend(new_obs)
                        
                        # Only send webhook if new OBs were found
                        if new_ob_found:
                            # Prepare webhook data with only new OBs
                            webhook_data = {
                                'ob_top': [ob['top'] for ob in new_obs],
                                'ob_bottom': [ob['bottom'] for ob in new_obs],
                                'ob_volume': [ob['volume'] for ob in new_obs],
                                'ob_strength': [ob['strength'] for ob in new_obs],
                                'ob_count': len(new_obs),
                            }
                            
                            # Send webhook alert for new OBs
                            webhook = TradeWebhook()
                            await webhook.send_ob_webhook(OB_WEBHOOK, webhook_data, token_name, ca=ca)
                            print(f"Sent webhook for {len(new_obs)} new order blocks")
                    else:
                        print("No new unique order blocks found")
                else:
                    # No OBs found, initialize if first run
                    if not hasattr(self, 'active_obs') or self.active_obs is None:
                        self.active_obs = []
                    print("No order blocks found in this analysis")
            else:
                # First run, initialize active_obs from scratch
                result = await self.mark_ob(ca=ca, data=data, supply=supply)
                
                if result and result.get('ob_count', 0) > 0:
                    # Create initial OBs
                    self.active_obs = []
                    for i in range(result['ob_count']):
                        self.active_obs.append({
                            'top': result['ob_top'][i],
                            'bottom': result['ob_bottom'][i],
                            'volume': result['ob_volume'][i],
                            'strength': result['ob_strength'][i],
                            'time_found': datetime.now()
                        })
                    
                    print(f"Successfully found {len(self.active_obs)} initial order blocks")
                    
                    # Send webhook for initial OBs
                    webhook_data = {
                        'ob_top': result['ob_top'],
                        'ob_bottom': result['ob_bottom'],
                        'ob_volume': result['ob_volume'],
                        'ob_strength': result['ob_strength'],
                        'ob_count': result['ob_count'],
                    }
                    
                    webhook = TradeWebhook()
                    await webhook.send_ob_webhook(OB_WEBHOOK, webhook_data, token_name, ca=ca)
                    print(f"Sent initial webhook for {result['ob_count']} order blocks")
                else:
                    print("No initial order blocks found")
                    self.active_obs = []
            
            # Cache the results and update timestamp
            result_data = {
                'active_obs': self.active_obs,
                'ob_count': len(self.active_obs)
            }
            self.ob_cache[cache_key] = result_data
            self.last_analysis_time[cache_key] = current_time
            
            # Return the complete OB data for multialert
            return result_data
            
        except Exception as e:
            print(f"Error in update_order_blocks: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
        
    async def monitor_ob_entry(self, token_name, ca, pair_address, current_mc):
        """Check if current marketcap is in any active order block zones"""
        try:
            if not self.active_obs:
                return False
                
            for ob in self.active_obs:
                ob_top = ob['top']
                ob_bottom = ob['bottom']
                
                # Check if current MC is within OB range (give 2% buffer)
                if ob_bottom * 0.98 <= current_mc <= ob_top * 1.02:
                    print(f"\n🎯 Price entered Order Block!")
                    print(f"OB Range: ${ob_bottom:.2f} - ${ob_top:.2f}")
                    print(f"Current MC: ${current_mc:.2f}")
                    print(f"OB Strength: {ob['strength']:.2%}")
                    
                    # Send webhook for OB entry
                    webhook = TradeWebhook()
                    await webhook.send_ob_entry_webhook(OB_WEBHOOK, {
                        'event': 'ob_zone_entered',
                        'current_mc': current_mc,
                        'ob_bottom': ob_bottom,
                        'ob_top': ob_top,
                        'ob_strength': ob['strength'],
                        'volume': ob['volume']
                    }, token_name, ca)
                    
                    return True
                    
            return False

        except Exception as e:
            print(f"Error in monitor_ob_entry: {str(e)}")
            return False