import asyncio
import aiohttp
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import scipy.signal as signal
import mplfinance as mpf
import pytz
from getohlcv import OH
from marketcap import MarketcapFetcher
from webhooks import TradeWebhook

class SupportResistance:
    def __init__(self):
        self.supply = None
        self.rpc = MarketcapFetcher()
        self.ca = "CcvpTfPuqp6U1odAkwbxBZh47Tz2jACwvoJG7ma4pump"
    
    async def set_supply(self, ca):
        supply = await self.rpc.get_token_supply(ca)
        if supply:
            self.supply = supply
        else:
            print(f"Error in supply fetching")
    
    async def detect_rugs_farms(self):
        pass
    
    def price_formatter(self, x: float) -> str:
        return f'{x:.2f}'

    def price_to_mc(self, price): #indv formatting
        return price * self.supply

    def price_marketcap_convert(self, o, h, l, c, supply): #ohlc formatting
        return {
            'o': o * supply,
            'h': h * supply,
            'l': l * supply,
            'c': c * supply
        }

    def convert_to_est(self, utc_time):
        utc_dt = pd.to_datetime(utc_time)
        est_tz = pytz.timezone('America/New_York')
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=pytz.UTC)
        est_dt = utc_dt.astimezone(est_tz)
        return est_dt
    
    def analyze_levels(self, levels, other_mean=None, is_resistance=False):
        if not levels or len(levels) < 2:
            print(f"{'Resistance' if is_resistance else 'Support'} - Insufficient data points: {len(levels) if levels else 0}")
            return {
                'is_clustered': False,
                'mean': None,
                'range_low': None,
                'range_high': None
            }
        
        mean = np.mean(levels)
        std = np.std(levels)
        similar_threshold = 0.45
        
        similar_values = [x for x in levels if abs(x - mean) / mean < similar_threshold]
        clustering_threshold = 0.2
        
        print(f"\n{'Resistance' if is_resistance else 'Support'} Analysis:")
        print(f"Total points: {len(levels)}")
        print(f"Similar points: {len(similar_values)}")
        print(f"Clustering ratio: {len(similar_values) / len(levels):.2f}")
        print(f"Mean value: {mean:.2f}")
        
        if len(similar_values) > len(levels) * clustering_threshold:
            level_mean = np.mean(similar_values)
            
            if other_mean is not None:
                print(f"Distance to other level: {abs(level_mean - other_mean) / other_mean:.2f}")
            
            if other_mean is not None and abs(level_mean - other_mean) / other_mean < 0.5:  # Increased from 0.4
                if is_resistance:
                    return {
                        'is_clustered': True,
                        'mean': level_mean,
                        'range_low': level_mean * 0.97,  # Slightly wider range
                        'range_high': level_mean * 1.03
                    }
                return {
                    'is_clustered': True,
                    'mean': level_mean,
                    'range_low': level_mean * 0.94,
                    'range_high': level_mean * 1.06
                }
            return {
                'is_clustered': True,
                'mean': level_mean,
                'range_low': level_mean * 0.75,  # Wider range when levels are far apart
                'range_high': level_mean * 1.25
            }
        print("Not enough clustering found")
        return {'is_clustered': False}

    async def get_levels(self, data):
        try:
            df = pd.DataFrame(data['result'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['timestamp'] = df['timestamp'].apply(self.convert_to_est)
            
            df['high'] = pd.to_numeric(df['high'], errors='coerce')
            df['low'] = pd.to_numeric(df['low'], errors='coerce')

            df = df.dropna(subset=['high', 'low'])
            if df.empty:
                print(f"No valid price data available after cleaning")
                return None
            
            df['high_mc'] = df['high'].apply(self.price_to_mc)
            df['low_mc'] = df['low'].apply(self.price_to_mc)

            ath = self.price_to_mc(df['high'].max())
            
            price_range = df['high_mc'].max() - df['low_mc'].min()
            min_prominence = price_range * 0.01
            
            peak_params = {
                'distance': 2,
                'prominence': min_prominence,
                'width': 1,
                'height': (None, None)
            }
            
            strong_peaks, _ = signal.find_peaks(df['high_mc'].values, **peak_params)
            strong_troughs, _ = signal.find_peaks(-df['low_mc'].values, **peak_params)
            
            strong_peaks_values = df.iloc[strong_peaks]['high_mc'].values.tolist()
            strong_troughs_values = df.iloc[strong_troughs]['low_mc'].values.tolist()
            temp_resistance = self.analyze_levels(strong_peaks_values)
            temp_support = self.analyze_levels(strong_troughs_values)
            
            resistance_analysis = self.analyze_levels(strong_peaks_values, temp_support['mean'] if temp_support['is_clustered'] else None, is_resistance=True)
            support_analysis = self.analyze_levels(strong_troughs_values, temp_resistance['mean'] if temp_resistance['is_clustered'] else None)
            
            print("\n=== Level Analysis ===")
            
            if resistance_analysis['is_clustered']:
                print(f"\nResistance Zone: ${self.price_formatter(resistance_analysis['range_low'])} - ${self.price_formatter(resistance_analysis['range_high'])}")
                print(f"Mean Resistance: ${self.price_formatter(resistance_analysis['mean'])}")
            
            # If no support clustering found, implement fallback logic
            if not support_analysis['is_clustered']:
                print("\nNo support clustering found. Checking high volume range...")
                # Get high volume analysis
                high_vol_data = await self.get_high_vol_candles(data, self.supply)
                if high_vol_data:
                    # Get current marketcap
                    current_marketcap = await self.rpc.calculate_marketcap(ca=self.ca)
                    high_vol_range = high_vol_data['high_vol_range']
                    
                    # Set backup support based on marketcap position
                    if current_marketcap > high_vol_range['high']:
                        backup_support = {
                            'is_clustered': True,
                            'mean': high_vol_range['low'],
                            'range_low': high_vol_range['low'] * 0.95,
                            'range_high': high_vol_range['high'] * 1.05
                        }
                    else:
                        # Marketcap is below high vol range, set support 30% lower
                        backup_support_level = high_vol_range['low'] * 0.7
                        backup_support = {
                            'is_clustered': True,
                            'mean': backup_support_level,
                            'range_low': backup_support_level * 0.95,
                            'range_high': backup_support_level * 1.05
                        }
                    
                    print(f"\nBackup Support Zone: ${self.price_formatter(backup_support['range_low'])} - ${self.price_formatter(backup_support['range_high'])}")
                    print(f"Backup Mean Support: ${self.price_formatter(backup_support['mean'])}")
                    
                    support_analysis = backup_support
            else:
                print(f"\nSupport Zone: ${self.price_formatter(support_analysis['range_low'])} - ${self.price_formatter(support_analysis['range_high'])}")
                print(f"Mean Support: ${self.price_formatter(support_analysis['mean'])}")
            
            print("\n=== Level Analysis ===")
            final_support = None
            final_resistance = None
            
            # Get high volume data first since we'll need it for comparisons
            high_vol_data = await self.get_high_vol_candles(data, self.supply)
            if not high_vol_data:
                return None
                
            vol_weighted_mc = high_vol_data['vol_weighted_mc']
            high_vol_range = high_vol_data['high_vol_range']

            # Handle resistance analysis
            if resistance_analysis['is_clustered']:
                # Check if resistance is in similar range to high vol zone
                resistance_mean = resistance_analysis['mean']
                if abs(resistance_mean - vol_weighted_mc) / vol_weighted_mc < 0.3:  # 30% threshold for "sameish" range
                    final_resistance = resistance_analysis
                    print(f"\nResistance Zone (aligned with volume): ${self.price_formatter(final_resistance['range_low'])} - ${self.price_formatter(final_resistance['range_high'])}")
                else:
                    final_resistance = resistance_analysis
                    print(f"\nResistance Zone: ${self.price_formatter(final_resistance['range_low'])} - ${self.price_formatter(final_resistance['range_high'])}")
                    print(f"Mean Resistance: ${self.price_formatter(final_resistance['mean'])}")

            # Handle support analysis
            if not support_analysis['is_clustered']:
                print("\nNo support clustering found. Using fallback support...")
                # Get current marketcap
                current_marketcap = await self.rpc.calculate_marketcap(ca=self.ca)
                
                if current_marketcap > high_vol_range['high']:
                    final_support = {
                        'is_clustered': True,
                        'mean': high_vol_range['low'],
                        'range_low': high_vol_range['low'] * 0.95,
                        'range_high': high_vol_range['high'] * 1.05
                    }
                else:
                    backup_support_level = high_vol_range['low'] * 0.7
                    final_support = {
                        'is_clustered': True,
                        'mean': backup_support_level,
                        'range_low': backup_support_level * 0.95,
                        'range_high': backup_support_level * 1.05
                    }
            else:
                # Check if support is lower than high vol range mean
                if support_analysis['mean'] < vol_weighted_mc:
                    final_support = support_analysis
                else:
                    final_support = {
                        'is_clustered': True,
                        'mean': high_vol_range['low'],
                        'range_low': high_vol_range['low'] * 0.95,
                        'range_high': high_vol_range['high'] * 1.05
                    }

            print(f"\nFinal Support Zone: ${self.price_formatter(final_support['range_low'])} - ${self.price_formatter(final_support['range_high'])}")
            print(f"Final Mean Support: ${self.price_formatter(final_support['mean'])}")

            return {
                'resistance': final_resistance,
                'support': final_support,
                'price_range': price_range,
                'high_vol_data': high_vol_data
            }
            
            
        except Exception as e:
            print(f"FATAL error: {str(e)}")
            return None
        
    async def monitor_price_breaks(self, levels, ca):
        try:
            if not levels or not levels['resistance']:
                print("No resistance levels to monitor")
                return

            resistance_high = levels['resistance']['range_high']
            
            while True:
                current_mc = await self.rpc.calculate_marketcap(ca)  # This returns a float directly
                
                if current_mc > resistance_high:
                    print(f"\nALERT: Price broke above resistance zone!")
                    print(f"Current MC: ${self.price_formatter(current_mc)}")
                    print(f"Resistance Level: ${self.price_formatter(resistance_high)}")
                    break

                await asyncio.sleep(60)  # Wait 1 minute before next check

        except Exception as e:
            print(f"Error in price monitoring: {str(e)}")
    
    async def ape_token(self, levels, ca):
        try:
            if not levels or not levels['resistance'] or not levels['support']:
                print("Insufficient level data for aping")
                return

            resistance_mean = levels['resistance']['mean']
            support_mean = levels['support']['mean']
            
            # Check if resistance is >= 50% more than support
            if resistance_mean < support_mean * 1.1:
                print(f"Resistance/Support ratio insufficient for aping")
                print(f"Resistance: ${self.price_formatter(resistance_mean)}")
                print(f"Support: ${self.price_formatter(support_mean)}")
                return
                
            print("\n=== Starting Ape Analysis ===")
            print(f"Target Resistance: ${self.price_formatter(resistance_mean)}")
            print(f"Support Level: ${self.price_formatter(support_mean)}")
            
            # Get entry price
            entry_mc = await self.rpc.calculate_marketcap(ca)
            entry_time = datetime.now()
            print(f"Entry MC: ${self.price_formatter(entry_mc)}")
            
            webhook = TradeWebhook()
            stop_loss = entry_mc * 0.5  # 50% of entry
            
            while True:
                current_mc = await self.rpc.calculate_marketcap(ca)
                current_profit = ((current_mc - entry_mc) / entry_mc) * 100
                duration = datetime.now() - entry_time
                
                print(f"\nCurrent MC: ${self.price_formatter(current_mc)}")
                print(f"Current Profit: {current_profit:.2f}%")
                
                # Check for profit target (50% increase)
                if current_mc >= entry_mc * 1.5:
                    print("\n🎯 Profit target reached!")
                    await webhook.send_trade_result(
                        token_name="Token",  # You might want to add token name to your class
                        ca=ca,
                        entry_mc=entry_mc,
                        exit_mc=current_mc,
                        profit_percentage=current_profit,
                        trade_duration=str(duration),
                        reason="Profit target reached (50%+ gain)"
                    )
                    break
                    
                # Check for stop loss
                if current_mc <= stop_loss:
                    print("\n⚠️ Stop loss triggered!")
                    await webhook.send_trade_result(
                        token_name="Token",
                        ca=ca,
                        entry_mc=entry_mc,
                        exit_mc=current_mc,
                        profit_percentage=current_profit,
                        trade_duration=str(duration),
                        reason="Stop loss triggered (50% loss)"
                    )
                    break
                    
                await asyncio.sleep(60)  # Check every minute

        except Exception as e:
            print(f"Error in ape_token: {str(e)}")
    
    async def get_high_vol_candles(self, data, supply):
        try:
            df = pd.DataFrame(data['result'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['timestamp'] = df['timestamp'].apply(self.convert_to_est)
            results = []
            
            for i in range(len(df)):
                t_est = df['timestamp'].iloc[i]
                o = float(df['open'].iloc[i])
                h = float(df['high'].iloc[i])
                l = float(df['low'].iloc[i])
                c = float(df['close'].iloc[i])
                vl = float(df['volume'].iloc[i])
                converted = self.price_marketcap_convert(o, h, l, c, supply)
                results.append({
                    'timestamp': t_est,
                    **converted,
                    'volume': vl
                })
                
            result_df = pd.DataFrame(results)
            t15_vol = result_df.nlargest(10, 'volume')
            
            # Calculate volume-weighted average
            vol_weighted_mc = (
                (t15_vol['h'] * t15_vol['volume']).sum() + 
                (t15_vol['l'] * t15_vol['volume']).sum()
            ) / (t15_vol['volume'].sum() * 2)
            
            # Set fixed 20% range around volume-weighted price
            range_percent = 0.20  # 20% range
            high_vol_range_low = vol_weighted_mc * (1 - range_percent)
            high_vol_range_high = vol_weighted_mc * (1 + range_percent)
            
            print(f"\nHigh Volume Analysis:")
            print(f"Volume-Weighted MC: ${self.price_formatter(vol_weighted_mc)}")
            print(f"High Volume Range (±20%): ${self.price_formatter(high_vol_range_low)} - ${self.price_formatter(high_vol_range_high)}")
            
            print(f"\nDetailed Volume Levels:")
            for _, row in t15_vol.iterrows():
                print(f"${self.price_formatter(row['l'])} - ${self.price_formatter(row['h'])} | Vol: {row['volume']:.2f}")
            
            return {
                'results': results,
                'analyzed_pairs': len(results),
                't10_vol': t15_vol,
                'vol_weighted_mc': vol_weighted_mc,
                'high_vol_range': {
                    'low': high_vol_range_low,
                    'high': high_vol_range_high
                }
            }
        except Exception as e:
            print(f"Error getting high vol points: {str(e)}")
            return None
    
    async def mark_support_resistance(self, data, supply):
        high_vol_areas = await self.get_high_vol_candles(data, supply=self.supply)
        levels = await self.get_levels(data)
        if not high_vol_areas or not levels:
            pass
    




class Main:
    def __init__(self):
        self.sr = SupportResistance()
        self.ohlcv = OH()
    
    async def run(self):
        try:
            pair_address = "A3Pe4anukhpzL7J2uXYtKE7hi2ehhSvgryUFW8CcqaNg"
            await self.sr.set_supply(ca="CcvpTfPuqp6U1odAkwbxBZh47Tz2jACwvoJG7ma4pump")
            data = await self.ohlcv.fetch(timeframe="1min", pair_address=pair_address)
            
            levels = await self.sr.get_levels(data)
            if not levels:
                print("No significant levels detected")
                return
            
            # Start monitoring for trade opportunities
            await self.sr.ape_token(levels, ca="CcvpTfPuqp6U1odAkwbxBZh47Tz2jACwvoJG7ma4pump")
                
        except Exception as e:
            print(f"Error in main run: {str(e)}")
            raise e

if __name__ == "__main__":
    main = Main()
    asyncio.run(main.run())