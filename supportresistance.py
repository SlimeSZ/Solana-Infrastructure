import asyncio
import aiohttp
import pandas as pd
import numpy as np
import pytz
from getohlcv import OH
from basecg import CoinGeckoTerminal
from datetime import datetime
from collections import defaultdict
import scipy.signal as signal
from env import BIRDEYE_API_KEY, SR_WEBHOOK
from webhooks import TradeWebhook
from dexapi import DexScreenerAPI
from backupohlcv import OHLCV
#from scientificnotation import SN

from marketcapfinal import Supply, Price, Marketcap

class SupportResistance:
    def __init__(self):
        self.ohlcv = OH()
        self.dex = DexScreenerAPI()
        self.s = Supply()
        self.p = Price()
        self.mc = Marketcap()

        self.backupohlcv = OHLCV()
        self.current_mc = None
        self.supply = None
        

    
    def _price_formatter(self, x: float) -> str:
        return f'{x:.2f}'
    
    def _price_to_mc(self, **kwargs):
        price = kwargs.get('price')
        supply = kwargs.get('supply')
        if price is None or supply is None:
            raise ValueError(f"Both Price & Supply were not provided...")
        # Ensure price is treated as float
        price = float(price)
        return price * supply

    def convert_to_est(self, time):
        utc_dt = pd.to_datetime(time)
        est_tz = pytz.timezone('America/New_York')
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=pytz.UTC)
        est_dt = utc_dt.astimezone(est_tz)
        return est_dt
    
    async def _set_mc(self, ca):
        try:
            self.current_mc = await self.mc.marketcap(ca)
        except Exception as e:
            print(f"Error setting marketcap {str(e)}")

    async def _convert(self, data, supply):
        """
        Convert OHLCV data to a pandas DataFrame with market cap calculations.
        Returns None if any critical error occurs.
        """
        try:
            if data is None:
                print("Error: Input data is None")
                return None
                
            if supply is None or supply <= 0:
                print("Error: Invalid supply value")
                return None

            #print("\nReceived data structure:")
            #print(f"Data type: {type(data)}")
            #print("Data keys:", data.keys() if isinstance(data, dict) else "Not a dictionary")
            #print("First few items:", data)

            if isinstance(data, dict):
                if 'result' in data:
                    df = pd.DataFrame(data['result'])
                elif 'oclhv' in data:
                    df = pd.DataFrame(data['oclhv'])
                elif isinstance(data.get('ohlcv'), list):  # New format check
                    df = pd.DataFrame(data['ohlcv'])
                elif 'ohlcv' in data:  # Alternative format check
                    df = pd.DataFrame(data['ohlcv'])
                else:
                    print("Error: Unrecognized data format - available keys:", list(data.keys()))
                    return None
            else:
                print(f"Error: Data must be dict, got {type(data)}")
                return None

            if df.empty:
                print("Error: Empty DataFrame created")
                return None

            #print("\nDataFrame info before processing:")
            #print(df.info())
            #print("\nFirst few rows:")
            #print(df.head())

            required_columns = ['open', 'high', 'low', 'close', 'volume']
            rename_map = {
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume'
            }
                
            df = df.rename(columns=rename_map)
                
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                print(f"Error: Missing required columns: {missing_cols}")
                return None

            pd.set_option('display.float_format', lambda x: '{:.20f}'.format(x))
                
            for col in ['open', 'high', 'low', 'close']:
                try:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                        
                    if df[col].isna().any():
                        #print(f"Warning: NaN values found in {col} column")
                        df[col] = df[col].fillna(method='ffill').fillna(method='bfill')
                        
                    if df[col].iloc[0] is not None:
                        #print(f"First {col} value after conversion: {df[col].iloc[0]}")
                            
                        df[col] = df[col] * supply
                        #print(f"First {col} marketcap: {df[col].iloc[0]}")
                    else:
                        #print(f"Error: First value in {col} is None")
                        return None
                        
                except Exception as e:
                    print(f"Error processing column {col}: {str(e)}")
                    return None

            # Final validation
            if df.isnull().values.any():
                print("Warning: DataFrame contains null values after processing")
                    
            return df

        except Exception as e:
            print(f"Error in _convert: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    async def get_sr(self, data, ca, supply):
        try:
            if data is None:
                print("Error: Input data is None")
                return None
                
            if not ca:
                print("Error: Contract address is empty")
                return None
            
            if not supply:
                supply = self.s.supply(ca)
            
            self.supply = supply
            await self._set_mc(ca)


            df = await self._convert(data, supply)
            if df is None:
                print("Error: Data conversion failed")
                return None

            # Rest of your existing code...

            # Continue only if we have valid DataFrame
            if not df.empty and all(col in df.columns for col in ['high', 'low']):
                # Calculate market cap values
                df['high_mc'] = df['high']  # Already in marketcap terms
                df['low_mc'] = df['low']    # Already in marketcap terms
                
                # Calculate ATH and price range
                ath = df['high'].max()
                if pd.isna(ath):
                    print("Error: ATH calculation resulted in NaN")
                    return None
                    
                price_range = df['high_mc'].max() - df['low_mc'].min()
                if pd.isna(price_range) or price_range <= 0:
                    print("Error: Invalid price range calculated")
                    return None

                min_prominence = price_range * 0.01
                
                # Find peaks and troughs
                peak_params = {
                    'distance': 2,
                    'prominence': min_prominence,
                    'width': 1,
                    'height': (None, None)
                }
                
                # Ensure we have valid data for peak finding
                if not df['high_mc'].isnull().all() and not df['low_mc'].isnull().all():
                    strong_peaks, _ = signal.find_peaks(df['high_mc'].values, **peak_params)
                    strong_troughs, _ = signal.find_peaks(-df['low_mc'].values, **peak_params)
                    
                    strong_peak_values = df.iloc[strong_peaks]['high_mc'].values.tolist()
                    strong_troughs_values = df.iloc[strong_troughs]['low_mc'].values.tolist()
                    
                    # Only proceed if we found some peaks and troughs
                    if strong_peak_values and strong_troughs_values:
                        temp_r = await self.analyze_sr(strong_peak_values)
                        temp_s = await self.analyze_sr(strong_troughs_values)
                        
                        resistance_analysis = await self.analyze_sr(
                            strong_peak_values, 
                            temp_s['mean'] if temp_s and temp_s['is_clustered'] else None, 
                            is_resistance=True
                        )
                        
                        support_analysis = await self.analyze_sr(
                            strong_troughs_values, 
                            temp_r['mean'] if temp_r and temp_r['is_clustered'] else None
                        )
                        
                        # Process resistance
                        final_r = {
                            'is_clustered': True,
                            'mean': resistance_analysis['mean'] if resistance_analysis['is_clustered'] else ath,
                            'range_low': (resistance_analysis['mean'] if resistance_analysis['is_clustered'] else ath) * 0.90,
                            'range_high': (resistance_analysis['mean'] if resistance_analysis['is_clustered'] else ath) * 1.10
                        }
                        
                        # Process support
                        final_s = None
                        if support_analysis['is_clustered']:
                            support_mean = support_analysis['mean']
                            if support_mean < self.current_mc * 0.30:
                                final_s = support_analysis
                                
                        if final_s is None:
                            support_mean = np.mean(strong_troughs_values)
                            final_s = {
                                'is_clustered': True,
                                'mean': support_mean,
                                'range_low': support_mean * 0.97,
                                'range_high': support_mean * 1.03
                            }
                        
                        # Calculate strengths
                        resistance_strength = len([x for x in strong_peak_values 
                                                if abs(x - final_r['mean']) / final_r['mean'] < 0.3]) / len(strong_peak_values)
                        support_strength = len([x for x in strong_troughs_values 
                                            if abs(x - final_s['mean']) / final_s['mean'] < 0.3]) / len(strong_troughs_values)
                        
                        return {
                            'resistance': final_r,
                            'support': final_s,
                            'resistance_strength': resistance_strength,
                            'support_strength': support_strength
                        }
                else:
                    print("Error: No valid data for peak finding")
                    return None
            else:
                print("Error: DataFrame validation failed")
                return None

        except Exception as e:
            print(f"Fatal Error in get_sr: \n{str(e)}")
            import traceback
            traceback.print_exc()
            return None

    
    async def analyze_sr(self, levels, other_level_mean=None, is_resistance=False):
        if not levels or len(levels) == 0:
            print (f"Insufficient Data Points for calculating support or resistance")
            return {
                'is_clustered': False,
                'mean': None,
                'range_low': None,
                'range_high': None
            }
        levels = [x for x in levels if np.isfinite(x)]
        if not levels or len(levels) < 2:
            return {
                'is_clustered': False,
                'mean': None,
                'range_low': None,
                'range_high': None
            }
        
        mean = np.mean(levels)
        std = np.std(levels)
        similar_threshold = 0.3
        similar_points = [x for x in levels if abs(x - mean) / mean < similar_threshold]

        cluster_mean = np.mean(similar_points) if similar_points else mean
        # Check if we have any similar points
        if not similar_points:
            return {
                'is_clustered': False,
                'mean': mean,
                'range_low': mean * 0.95,
                'range_high': mean * 1.05
            }
        clustering_threshold = 0.5 #need 50% of points to be within 30% marketcap of each other (+-)
        total_points = len(levels)
        total_similar_points = len(similar_points)
        if total_similar_points / total_points >= clustering_threshold:
            cluster_mean = np.mean(similar_points)
            return {
                'is_clustered': True,
                'mean': cluster_mean,
                'range_low': cluster_mean * 0.97, #s/r level is 3% below mean
                'range_high': cluster_mean * 1.03 #& 3% above it
            }
        if other_level_mean is not None:
            distance = abs(cluster_mean - other_level_mean) / other_level_mean
            print(f"Distance from {"support" if not is_resistance else "resistance"} to {"resistance" if is_resistance else "support"} is: {distance:.2f}%")
            if distance < 0.5: #if support & resistance are within 50% of each other
                if is_resistance:
                    return {
                        'is_clustered': True,
                        'mean': cluster_mean,
                        'range_low': cluster_mean * 0.95,
                        'range_high': cluster_mean * 1.05
                    }
                return { #set support range
                    'is_clustered': True,
                    'mean': cluster_mean,
                    'range_low': cluster_mean * 0.97,
                    'range_high': cluster_mean * 1.03
                }
            return { #if levels are already far apart       
                'is_clustered': True,
                'mean': cluster_mean,
                'range_low': cluster_mean * 0.9,
                'range_high': cluster_mean * 1.10
            }
        print(f"Similar Value Cluster not found for support or resistance")
        return {
            'is_clustered': False,
            'mean': mean,
            'range_low': mean * 0.95,
            'range_high': mean * 1.05
        }
    
    async def get_high_vol_zones(self, data, ca, supply):
        try:
            if not supply:
                supply = await self.s.supply(ca)
            self.supply = supply
            df = await self._convert(data, supply)
            if df is None:
                return None
            #df = pd.DataFrame(data['result'])
            results = []
            #convert to pd to extract individual ohlcv data
            for i in range(len(df)):
                o = float(df['open'].iloc[i])
                h = float(df['high'].iloc[i])
                l = float(df['low'].iloc[i])
                c = float(df['close'].iloc[i])
                vl = float(df['volume'].iloc[i])
                results.append({
                    'open': o,
                    'high': h,
                    'low': l,
                    'close': c,
                    'volume': vl
                })
            result_df = pd.DataFrame(results)
            
            unique_ranges = []
            t10_vol = result_df.nlargest(len(df), 'volume')
            for idx, row in t10_vol.iterrows():
                current_low = row['low']
                current_high = row['high']
                range_exists = False

                for existing_range in unique_ranges:
                    if (abs(current_low - existing_range['low'])/existing_range['low'] < 0.2 and 
                        abs(current_high - existing_range['high'])/existing_range['high'] < 0.2):
                        range_exists = True
                        break
                if not range_exists:
                    unique_ranges.append({
                        'low': current_low,
                        'high': current_high,
                        'volume': row['volume']
                    })
            
            print("\n=== Unique Price Ranges (20% Threshold) ===")
            for i, range_data in enumerate(unique_ranges, 1):
                print(f"\nRange #{i}")
                print(f"MC Range: {range_data['low']:.8f} - {range_data['high']:.8f}")
                print(f"Volume: {range_data['volume']:.2f}")
                print("-" * 40)
            return unique_ranges
                
            
        except Exception as e:
            print(str(e))
            return None
        

    async def get_sr_zones(self, token_name, ca, supply, ohlcv_data):
        try:
            if not ohlcv_data:
                print(F"Error passing ohlcv data bot.py --> get_sr_zones")
                return None
                
            levels = await self.get_sr(ohlcv_data, ca, supply)
            if not levels:
                print("Failed to get SR levels")
                return None
                
            unique_ranges = await self.get_high_vol_zones(ohlcv_data, ca, supply)
            
            support_zone = levels['support']
            resistance_zone = levels['resistance']
            support_mean = support_zone['mean']
            resistance_mean = resistance_zone['mean']

            volume_support_zones = []
            volume_resistance_zones = []

            for range_data in unique_ranges:
                range_high = range_data['high']
                range_low = range_data['low']
                
                # Check for support zones
                if range_high < support_mean and (range_high / support_mean) > 0.7:
                    volume_support_zones.append(range_data)
                
                # Check for resistance zones
                if range_low > resistance_mean and (range_low / resistance_mean) < 1.3:
                    volume_resistance_zones.append(range_data)

            # Send webhook
            webhook = TradeWebhook()
            await webhook.send_sr_webhook(SR_WEBHOOK, {
                'sr_levels': levels,
                'volume_supports': volume_support_zones,
                'volume_resistances': volume_resistance_zones
            }, token_name, ca)

            return {
                'sr_levels': levels,
                'volume_supports': volume_support_zones,
                'volume_resistances': volume_resistance_zones
            }

        except Exception as e:
            print(f"Error in get_sr_zones: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

            
      