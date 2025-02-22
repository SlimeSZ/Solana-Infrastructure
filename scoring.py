import asyncio
import aiohttp
from typing import Dict, Tuple

class TokenAgeConvert:
    def __init__(self):
        pass

    def convert_token_age_to_minutes(self, token_age):
        """Convert token age to minutes regardless of input unit"""
        try:
            if token_age['unit'] == 'minutes':
                return token_age['value']
            elif token_age['unit'] == 'hours':
                return token_age['value'] * 60
            elif token_age['unit'] == 'days':
                return token_age['value'] * 24 * 60
            else:
                return token_age['value']  # Default case
        except Exception as e:
            print(f"Error converting token age: {str(e)}")
            return 0

class HolderScore:  # 30% of total score
    def __init__(self):
        self.MAX_SCORE = 30.0
        self.HOLDER_AGE_MAX = 10.0  # 10% of total score
        self.SECURITY_MAX = 10.0     # 10% of total score
        self.WALLET_ANALYSIS_MAX = 10.0  # 10% of total score
        self.age_conv = TokenAgeConvert()

    async def calculate_score(
        self, 
        token_age,
        holder_count,
        top10holds,
        holdersover5percent,
        devholds,
        sniper_percent,
        wallet_data: Dict  
    ):
        try:
            age_in_minutes = self.age_conv.convert_token_age_to_minutes(token_age)
            
            # Initialize wallet_score with default value
            wallet_score = 0
            if wallet_data:  # Only process if wallet_data exists and is not None
                wallet_score, metrics = await self.analyze_wallet_performance(wallet_data)
            
            # Compute subscores
            holder_count_token_age_confluence = await self.holder_count_token_age_confluence(holder_count, age_in_minutes)
            holder_security = await self.holder_security(top10holds, holdersover5percent, devholds, sniper_percent)

            # Use default values if any subscore returns None
            normalized_holder_count_token_age_confluence = (holder_count_token_age_confluence or 0 / 10) * self.HOLDER_AGE_MAX
            normalized_holder_security = (holder_security or 0 / 40) * self.SECURITY_MAX
            normalized_wallet_score = (wallet_score or 0) * self.WALLET_ANALYSIS_MAX

            # Total score calculation
            total_score = (
                normalized_holder_count_token_age_confluence + 
                normalized_holder_security + 
                normalized_wallet_score
            )
            total_score = min(total_score, self.MAX_SCORE)

            return {
                'total_score': total_score,
                'holder_count_age_confluence': normalized_holder_count_token_age_confluence,
                'holder_security': normalized_holder_security,
                'wallet_score': normalized_wallet_score
            }
        except Exception as e:
            print(f"Error in holder score calculation: {str(e)}")
            # Return default scores instead of None
            return {
                'total_score': 0,
                'holder_count_age_confluence': 0,
                'holder_security': 0,
                'wallet_score': 0
            }

    async def holder_count_token_age_confluence(self, holder_count, token_age):
        try:
            raw_score = (holder_count / (token_age + 3)) * 3

            if raw_score >= 100:
                return 10.0
            elif raw_score >= 80:
                return 9.0
            elif raw_score >= 70:
                return 8.0
            elif raw_score >= 60:
                return 7.0
            elif 40 < raw_score <= 60:
                return 6.0
            elif 20 <= raw_score <= 40:
                return 5.0
            elif 15 < raw_score < 20:
                return 4.0
            elif 10 < raw_score <= 15:
                return 3.0
            else:
                return 1.0
        
        except Exception as e:
            print(str(e))
            return None

    async def holder_security(self, top10holds, holdersover5percent, devholds, sniper_percent):
        score = 0
        try:
            #top10 holder count
            if 17 <= top10holds < 20:
                score += 2
            elif 15 <= top10holds < 17:
                score += 4
            elif 13 <= top10holds <= 15:
                score += 5
            elif 10 < top10holds < 13:
                score += 8
            elif top10holds <= 10:
                score += 10

            #holders over 5 percent
            if holdersover5percent == 3:
                score += 2
            elif holdersover5percent == 2:
                score += 5
            elif holdersover5percent == 0:
                score += 10
            elif holdersover5percent == 1:
                score += 8
            
            #dev holding
            if devholds == 0:
                score += 7
            elif 0 < devholds < 3:
                score += 3
            elif 3 <= devholds <= 5:
                score += 1
            
            #sniper percent
            if 40 < sniper_percent < 50:
                score += 1
            elif 20 < sniper_percent < 40:
                score += 3
            elif 10 < sniper_percent < 20:
                score += 5
            elif 5 < sniper_percent < 10:
                score += 7
            elif 0 < sniper_percent < 5:
                score += 8
            elif sniper_percent == 0:
                score += 10
            
            return score
        except Exception as e:
            print(str(e))
            return None
        
    async def analyze_wallet_performance(self, wallet_data: Dict) -> Tuple[float, Dict]:
        metrics = {
            'avg_pnl': 0,
            'total_wins': 0,
            'total_losses': 0,
            'win_rate': 0,
            'total_wallets': len(wallet_data)
        }

        total_pnl = 0
        for wallet, data in wallet_data.items():
            metrics['total_wins'] += data.get('wins', 0)
            metrics['total_losses'] += data.get('losses', 0)
            total_pnl += data.get('pnl', 0)

        total_trades = metrics['total_wins'] + metrics['total_losses']
        metrics['win_rate'] = (metrics['total_wins'] / total_trades) if total_trades > 0 else 0
        metrics['avg_pnl'] = total_pnl / len(wallet_data) if wallet_data else 0

        # Score components
        pnl_score = min(max(metrics['avg_pnl'] / 100, 0), 1)  # Normalize PnL score
        win_rate_score = min(max(metrics['win_rate'], 0), 1)  # Win rate is already 0-1

        # Final score
        final_score = (pnl_score + win_rate_score) / 2.0

        return final_score, metrics
            

class TokenomicScore:
    def __init__(self):
        self.MAX_SCORE = 40.0
        self.VOLUME_LIQUIDITY_MAX = 8.0
        self.TOKEN_VOLUME_MAX = 4.0
        self.TOKEN_M5_MAX = 6.0
        self.BUY_TRADE_MAX = 6.0
        self.BUYING_PRESSURE_MAX = 6.0
        self.WALLET_GROWTH_MAX = 6.0
        self.age_conv = TokenAgeConvert()

    async def calculate_tokenomic_score(
        self,
        token_age,
        marketcap,
        m30_vol,
        m30_vol_change,
        liquidity,
        total_trade_change,
        buys_change,
        sells_change,
        total_unique_wallets_30m,
        total_unique_wallets_1h,
        unique_wallet_change_30m,
        unique_wallet_change_1h,
        holder_count,
        m5_vol
    ):
        try:
            age_in_minutes = self.age_conv.convert_token_age_to_minutes(token_age)
            
            # Calculate all individual scores
            volume_liquidity_score = await self.evaluate_volume_liquidity(m30_vol, liquidity, marketcap)
            m30_volume_score = await self.tokenage_volume_confluence_30m(age_in_minutes, m30_vol_change)
            m5_volume_score = await self.tokenage_volume_confluence_5m(age_in_minutes, m5_vol)
            buy_trade_score = await self.buy_total_trade_confluence(total_trade_change, buys_change)
            buying_pressure_score = await self.evaluate_buying_pressure(buys_change, sells_change, holder_count)
            wallet_growth_score = await self.evaluate_wallet_growth(
                total_unique_wallets_30m,
                total_unique_wallets_1h,
                unique_wallet_change_30m,
                unique_wallet_change_1h,
                holder_count
            )

            # Normalize scores
            normalized_scores = {
                'volume_marketcap_liquidity_confluence': (volume_liquidity_score / 10) * self.VOLUME_LIQUIDITY_MAX,
                'm30_age_volume_confluence': (m30_volume_score / 10) * self.TOKEN_VOLUME_MAX,
                'm5_age_volume_confluence': (m5_volume_score / 10) * self.TOKEN_M5_MAX,
                'total_trades_buy_confluence': (buy_trade_score / 10) * self.BUY_TRADE_MAX,
                'buying_pressure': (buying_pressure_score / 10) * self.BUYING_PRESSURE_MAX,
                'wallet_growth': (wallet_growth_score / 10) * self.WALLET_GROWTH_MAX
            }

            # Calculate total score
            total_score = sum(normalized_scores.values())
            total_score = min(total_score, self.MAX_SCORE)
            
            # Add total score to the breakdown
            normalized_scores['total_score'] = total_score

            return total_score, normalized_scores

        except Exception as e:
            print(f"Error in tokenomic score calculation: {str(e)}")
            return 0, {}  # Return empty dict as breakdown in case of error
    
    async def wallet_cluster_evaluation(self, channel_wallet_data: Dict) -> Tuple[float, Dict]:
        try:
            score = 0
            analysis = {}
            
            # Initialize channel presence tracking
            active_channels = set()
            
            # Track buy amounts for each channel type
            channel_buys = {
                'Kol Alpha': 0,
                'Kol Regular': 0,
                'Fresh': 0,
                'Whale': 0,
                'Smart': 0,
                'Legend': 0,
                'High Freq': 0,
                'Degen': 0
            }
            
            # Process SWT channels
            if 'swt' in channel_wallet_data:
                swt_channels = channel_wallet_data['swt']['channels']
                for channel_name, data in swt_channels.items():
                    buys = data.get('buys', 0)
                    channel_buys[channel_name] = buys
                    
                    if buys > 0:
                        active_channels.add(channel_name)
                        
                    # Penalize large KOL buys (potentially bearish)
                    if channel_name in ['Kol Alpha', 'Kol Regular'] and buys > 9.5:
                        score -= 5
                        analysis[f'{channel_name}_penalty'] = -5
            
            # Process Fresh channels
            if 'fresh' in channel_wallet_data:
                fresh_channels = channel_wallet_data['fresh']['channels']
                total_fresh_buys = 0
                for channel_name, data in fresh_channels.items():
                    buys = data.get('buys', 0)
                    total_fresh_buys += buys
                    if buys > 0:
                        active_channels.add('Fresh')
                        channel_buys['Fresh'] = total_fresh_buys
                
                # Penalty for too many fresh buys
                if total_fresh_buys > 10:
                    penalty = (total_fresh_buys - 10) * 0.5
                    score -= penalty
                    analysis['fresh_penalty'] = -penalty
            
            # Process Degen channel
            if 'degen' in channel_wallet_data:
                degen_channels = channel_wallet_data['degen']['channels']
                if 'Degen' in degen_channels:
                    buys = degen_channels['Degen'].get('buys', 0)
                    if buys > 0:
                        active_channels.add('Degen')
                        channel_buys['Degen'] = buys
            
            # Score channel combinations
            if len(active_channels) >= 2:
                combinations = set(map(frozenset, active_channels))
                
                # Bearish combinations (Fresh + KOL only)
                if active_channels == {'Fresh', 'Kol Alpha'} or active_channels == {'Fresh', 'Kol Regular'}:
                    score -= 8
                    analysis['bearish_combo_penalty'] = -8
                
                # High-scoring combinations
                elif 'Degen' in active_channels:
                    if 'Whale' in active_channels:
                        score += 7
                        analysis['degen_whale_bonus'] = 7
                    if 'Smart' in active_channels:
                        score += 6
                        analysis['degen_smart_bonus'] = 6
                    if 'Legend' in active_channels:
                        score += 8
                        analysis['degen_legend_bonus'] = 8
                
                # Legend combinations
                if 'Legend' in active_channels:
                    for other_channel in active_channels - {'Legend', 'Fresh', 'Kol Alpha', 'Kol Regular'}:
                        score += 5
                        analysis[f'legend_{other_channel.lower()}_bonus'] = 5
                
                # High Freq combinations
                if 'High Freq' in active_channels:
                    if {'Degen', 'Smart'} <= active_channels:
                        score += 6
                        analysis['high_freq_degen_smart_bonus'] = 6
                
                # Bonus for diverse activity (excluding bearish combos)
                if len(active_channels) >= 3 and not {'Fresh', 'Kol Alpha', 'Kol Regular'} <= active_channels:
                    diversity_bonus = len(active_channels) * 2
                    score += diversity_bonus
                    analysis['diversity_bonus'] = diversity_bonus
            
            # Store active channels and their buy amounts in analysis
            analysis['active_channels'] = list(active_channels)
            analysis['channel_buys'] = channel_buys
            analysis['final_score'] = score
            
            return score, analysis
            
        except Exception as e:
            print(f"Error in wallet cluster evaluation: {str(e)}")
            return 0, {'error': str(e)}

    async def evaluate_volume_liquidity(self, m30_vol, liquidity, marketcap):
        try:
            score = 0
            max_subscore = 10.0  

            # Avoid division errors
            if liquidity <= 0 or marketcap <= 0:
                return 0  

            # 1. Volume-to-Liquidity Ratio (VLR) (New Range: 60-500% is normal)
            vol_liq_ratio = (m30_vol / liquidity) * 100  

            if 100 <= vol_liq_ratio <= 300:  # Ideal range for memecoins
                score += 5  
            elif 60 <= vol_liq_ratio < 100 or 300 < vol_liq_ratio <= 400:
                score += 4  
            elif 400 < vol_liq_ratio <= 500:  
                score += 3  
            elif vol_liq_ratio > 500:  # Extreme volume compared to liquidity
                score += 1  

            # 2. Marketcap-to-Liquidity Ratio (MCR) (Adjusting for real backing)
            mc_liq_ratio = marketcap / liquidity  

            if 2 <= mc_liq_ratio <= 5:  # Healthy range
                score += 5  
            elif 1.5 <= mc_liq_ratio < 2 or 5 < mc_liq_ratio <= 7:
                score += 4  
            elif 1 <= mc_liq_ratio < 1.5 or 7 < mc_liq_ratio <= 10:
                score += 3  
            elif mc_liq_ratio > 10:  # High MC but low liquidity = exit risk
                score += 1  
                print(f"High MC low Liq risk: EXIT! ")

            return min(score, max_subscore)  

        except Exception as e:
            print(f"Error in volume liquidity evaluation: {str(e)}")
            return 0

    async def tokenage_volume_confluence_30m(self, token_age, m30_vol_change):
        try:
            score = 0
            max_subscore = 10.0
            
            #for new tokens < 60 min
            if 20 <= m30_vol_change <= 30 and token_age <= 30:
                score += 2
            elif 31 <= m30_vol_change <= 50 and token_age <= 30:
                score += 4
            elif 20 <= m30_vol_change <= 30 and token_age <= 60:
                score += 1
            elif 31 <= m30_vol_change <= 50 and token_age <= 60:
                score += 2
            
            elif 50 <= m30_vol_change <= 80 and token_age <= 30:
                score += 4
            elif 50 <= m30_vol_change <= 80 and token_age <= 60:
                score += 3
            
            elif 100 <= m30_vol_change <= 200 and token_age <= 30:
                score += 7
            elif 100 <= m30_vol_change <= 200 and token_age <= 60:
                score += 5
            
            elif m30_vol_change >= 201 and token_age <= 30:
                score += 9
            elif m30_vol_change >= 201 and token_age <= 60:
                score += 8
            #for relatively new tokens (1-2 hrs old)
            elif 31 <= m30_vol_change <= 50 and token_age <= 90:
                score += 1
            
            elif 50 <= m30_vol_change <= 80 and token_age <= 90:
                score += 3
            elif 50 <= m30_vol_change <= 80 and token_age <= 120:
                score += 2
            
            elif 100 <= m30_vol_change <= 200 and token_age <= 90:
                score += 5
            elif 100 <= m30_vol_change <= 200 and token_age <= 120:
                score += 4
            
            elif m30_vol_change >= 201 and token_age <= 90:
                score += 9
            elif m30_vol_change >= 201 and token_age <= 120:
                score += 7


            #general volume evaluation
            if 20 <= m30_vol_change <= 50:
                score += 2
            elif 51 <= m30_vol_change <= 80:
                score += 4
            elif 81 <= m30_vol_change <= 100:
                score += 6
            elif 100 < m30_vol_change <= 200:
                score += 8
            elif m30_vol_change > 200:
                score += 10
            
            return min(score, max_subscore)

        except Exception as e:
            print(str(e))
            return 0
        
    async def tokenage_volume_confluence_5m(self, token_age, m5_vol):
        try:
            score = 0
            max_subscore = 10.0
            
            #for fairly new tokens < 30 min
            if 10000 <= m5_vol <= 20000 and token_age <= 30:
                score += 2
            elif 20000 < m5_vol <= 30000 and token_age <= 30:
                score += 4
            elif 30000 < m5_vol <= 40000 and token_age <= 30:
                score += 5
            elif 40000 < m5_vol <= 60000 and token_age <= 30:
                score += 7
            elif 60000 < m5_vol <= 90000 and token_age <= 30:
                score += 8
            elif m5_vol > 90000 and token_age <= 30:
                score += 10
            #for somewhat new tokens < 60 min
            elif 20000 < m5_vol <= 30000 and token_age <= 60:
                score += 2
            elif 30000 < m5_vol <= 40000 and token_age <= 60:
                score += 3
            elif 40000 < m5_vol <= 60000 and token_age <= 60:
                score += 4
            elif 60000 < m5_vol <= 90000 and token_age <= 60:
                score += 6
            elif m5_vol > 90000 and token_age <= 60:
                score += 8
            #for tokens < 2 hrs w high 5m volume
            elif 30000 < m5_vol <= 40000 and token_age <= 120:
                score += 2
            elif 40000 < m5_vol <= 60000 and token_age <= 120:
                score += 4
            elif 60000 < m5_vol <= 90000 and token_age <= 120:
                score += 6
            elif m5_vol > 90000 and token_age <= 120:
                score += 7
            #general 5m checks
            elif m5_vol > 1000000:
                score += 10
            elif m5_vol > 500000:
                score += 8
            elif m5_vol > 300000:
                score += 6.5
            elif m5_vol > 100000:
                score += 4
            elif m5_vol > 50000:
                score += 3
            
            return min(score, max_subscore)
        except Exception as e:
            print(str(e))
            return 0

    async def buy_total_trade_confluence(self, total_trade_change, buys_change):
        try:
            score = 0
            max_subscore = 10.0

            #total trade & buy change in % confluence
            if 5 <= total_trade_change <= 10 and 10 <= buys_change <= 15:
                score += 1
            elif 11 <= total_trade_change <= 16 and 16 <= buys_change <= 20:
                score += 2
            elif 16 < total_trade_change <= 30 and 20 < buys_change <= 30:
                score += 4
            elif 30 < total_trade_change <= 50 and buys_change >= 30:
                score += 6
            elif total_trade_change > 50 and buys_change >= 30:
                score += 8
            elif total_trade_change > 50 and buys_change >= 49:
                score += 10
            
            

            #trade percentage change evaluation
            if 10 <= total_trade_change <= 20:
                score += 1
            elif 20 < total_trade_change <= 30:
                score += 2
            elif 30 < total_trade_change <= 50:
                score += 4
            elif 50 < total_trade_change <= 70:
                score += 5
            elif total_trade_change > 70:
                score += 7
            
            #buy change evaluation (percentage)
            if 5 <= buys_change <= 11:
                score += 1
            elif 11 < buys_change <= 15:
                score += 2
            elif 15 < buys_change <= 20:
                score += 3
            elif 20 < buys_change <= 35:
                score += 5
            elif 35 < buys_change <= 50:
                score += 7
            elif 50 < buys_change <= 80:
                score += 8
            elif buys_change > 80:
                score += 10

            return min(score, max_subscore)

        except Exception as e:
            print(f"Error in volume dynamics evaluation: {str(e)}")
            return 0
        
    async def evaluate_buying_pressure(self, buys_change, sells_change, holder_count):
        try:
            score = 0
            max_subscore = 10.0

            # Buy/Sell ratio confluence
            buy_sell_ratio = buys_change / sells_change if sells_change > 0 else buys_change
            if 0.7 <= buy_sell_ratio <= 1:
                score += 1
            elif 1 < buy_sell_ratio <= 1.5:
                score += 2
            elif 1.5 < buy_sell_ratio <= 2:
                score += 4
            elif 2 < buy_sell_ratio <= 3:
                score += 6
            elif 3 < buy_sell_ratio <= 4.5:
                score += 8
            elif buy_sell_ratio > 4.5:
                score += 10

            # Holder growth confluence
            if holder_count > 0:
                buys_int = (buys_change / 100) * holder_count
                holder_buy_ratio = buys_int / holder_count
                if 0.1 < holder_buy_ratio <= 0.17:
                    score += 1
                elif 0.17 < holder_buy_ratio <= 0.22:
                    score += 2
                elif 0.22 < holder_buy_ratio <= 0.3:
                    score += 3
                elif 0.3 < holder_buy_ratio <= 0.4:
                    score += 4
                elif 0.4 < holder_buy_ratio <= 0.55:
                    score += 5
                elif 0.55 < holder_buy_ratio <= 0.75:
                    score += 6
                elif holder_buy_ratio > 0.75:
                    score += 8

            return min(score, max_subscore)

        except Exception as e:
            print(f"Error in buying pressure evaluation: {str(e)}")
            return 0

    async def evaluate_wallet_growth(
        self,
        total_unique_wallets_30m,
        total_unique_wallets_1h,
        unique_wallet_change_30m,
        unique_wallet_change_1h,
        holder_count
    ):
        try:
            score = 0
            max_subscore = 10.0

            # Evaluate 30m metrics first
            if unique_wallet_change_30m > 0:
                if 20 < unique_wallet_change_1h <= 30:
                    score += 2
                elif 30 <= unique_wallet_change_30m <= 50:
                    score += 3
                elif 50 < unique_wallet_change_30m <= 80:
                    score += 5
                elif 80 < unique_wallet_change_30m <= 120:
                    score += 7
                elif unique_wallet_change_30m > 120:
                    score += 9

                # Confluence with holder count
                wallet_holder_ratio = total_unique_wallets_30m / holder_count if holder_count > 0 else 0
                if 0.2 <= wallet_holder_ratio <= 0.4:
                    score += 7
                elif 0.4 < wallet_holder_ratio <= 0.6:
                    score += 5
                elif 0.6 < wallet_holder_ratio <= 0.8:
                    score += 4
                elif 0.8 < wallet_holder_ratio <= 1.3:
                    score += 2
                elif wallet_holder_ratio > 1.3:
                    score += 0

            # Only evaluate 1h metrics if significantly different from 30m
            if (unique_wallet_change_1h != unique_wallet_change_30m and 
                total_unique_wallets_1h != total_unique_wallets_30m):
                # Add additional scoring here if needed
                pass

            return min(score, max_subscore)

        except Exception as e:
            print(f"Error in wallet growth evaluation: {str(e)}")
            return 0

class TrustScore:  # 30% of total score
    def __init__(self):
        self.MAX_SCORE = 30.0
        self.SERVER_BS_MAX = 5.0
        self.TOKEN_AGE_SERVER_MAX = 6.0
        self.SECURITY_MAX = 5.0
        self.SERVER_ACTIVITY_MAX = 5.0
        self.SOCIAL_PRESENCE_MAX = 5.0
        self.WALLET_CLUSTER_MAX = 4.0
        self.age_conv = TokenAgeConvert()

    async def calculate_trust_score(
        self,
        token_age,
        server_buys,
        server_sells,
        server_count,
        has_tg,
        has_x,
        dexpaid,
        soulscannerpass,
        bundlebotpass,
        buys_change,
        sells_change
    ):
        try:
            age_in_minutes = self.age_conv.convert_token_age_to_minutes(token_age)
            scores = {
                'server_buy_sell_pool_buy_sells_confluence': await self.server_bs_general_bs_confluence(server_buys, server_sells, buys_change, sells_change),
                'age_server_count_confluence': await self.token_age_server_count_confluence(server_count, age_in_minutes),
                'security_evaluation': await self.evaluate_security(dexpaid, soulscannerpass, bundlebotpass),
                'server_activity_evaluation': await self.evaluate_server_activity(age_in_minutes, server_buys, server_sells),
                'social_presence_evaluation': await self.evaluate_social_presence(dexpaid, soulscannerpass, bundlebotpass, has_tg, has_x)
            }
            normalized_scores = {
                'server_buy_sell_pool_buy_sells_confluence': (scores['server_buy_sell_pool_buy_sells_confluence'] / 10) * self.SERVER_BS_MAX,
                'age_server_count_confluence': (scores['age_server_count_confluence'] / 10) * self.TOKEN_AGE_SERVER_MAX,
                'security_evaluation': (scores['security_evaluation'] / 10) * self.SECURITY_MAX,
                'server_activity_evaluation': (scores['server_activity_evaluation'] / 10) * self.SERVER_ACTIVITY_MAX,
                'social_presence_evaluation': (scores['social_presence_evaluation'] / 10) * self.SOCIAL_PRESENCE_MAX
            }

            total_sscore = sum(normalized_scores.values())
            total_score = min(total_sscore, self.MAX_SCORE)
            normalized_scores['total_score'] = total_score

            return total_score, normalized_scores

        except Exception as e:
            print(f"Error in trust score calculation: {str(e)}")
            return 0
    
    async def server_bs_general_bs_confluence(self, server_buys, server_sells, buys_change, sells_change):
        try:
            score = 0
            max_subscore = 10

            server_buy_sell_ratio = server_buys / server_sells if server_sells > 0 else server_buys
            pool_buy_sell_ratio = buys_change / sells_change  if sells_change > 0 else buys_change

            #server buys > sell confluence relation w/ buys% > sells% from pool metadata
            if 1 <= server_buy_sell_ratio <= 1.3 and 1 <= pool_buy_sell_ratio <= 1.3:
                score += 1
            elif 1.3 < server_buy_sell_ratio <= 1.5 and 1.3 < pool_buy_sell_ratio <= 1.5:
                score += 3
            elif 1.5 < server_buy_sell_ratio <= 1.8 and 1.5 < pool_buy_sell_ratio <= 1.8:
                score += 4
            elif 1.8 < server_buy_sell_ratio <= 2.2 and 1.8 < pool_buy_sell_ratio <= 2.2:
                score += 5
            elif 2.2  < server_buy_sell_ratio <= 2.5 and 2.2 < pool_buy_sell_ratio <= 2.5:
                score += 7
            elif server_buy_sell_ratio > 2 and pool_buy_sell_ratio > 2:
                score += 10

            if server_buy_sell_ratio > 2.3 or pool_buy_sell_ratio > 2.3:
                score += 8
            
            return min(score, max_subscore)
        
        except Exception as e:
            print(str(e))
            return None

    async def token_age_server_count_confluence(self, server_count, token_age):
        score = 0.0
        max_subscore = 10
        try:
            if token_age < 60 and server_count > 10:
                score  += 8
            elif token_age < 60 and 5 < server_count <=10:
                score += 6
            elif token_age < 30 and server_count > 10:
                score += 10
            elif 70 < token_age < 120 and 10 < server_count < 19:
                score += 4
            elif 70 < token_age < 120 and server_count >= 19:
                score += 6
            elif 120 < token_age < 200 and 20 <= server_count < 40:
                score += 4
            elif token_age < 240 and server_count >= 40:
                score += 7

            return min(score, max_subscore)
            
        except ZeroDivisionError as e:
            print(str(e))
            return None
            

    async def evaluate_security(self, dexpaid, soulscannerpass, bundlebotpass):
        try:
            score = 0
            max_subscore = 10.0

            # Dex paid status (5 points)
            if dexpaid:
                score += 5
            
            # SoulScanner evaluation (5 points)
            if soulscannerpass:
                score += 5
            
            # BundleBot evaluation (5 points)
            if bundlebotpass:
                score += 5

            # Confluence bonus for passing all checks
            if dexpaid and soulscannerpass and bundlebotpass:
                score += 3  # Bonus points for passing all security checks
            
            # Partial confluence bonuses
            elif (dexpaid and soulscannerpass) or (dexpaid and bundlebotpass) or (soulscannerpass and bundlebotpass):
                score += 1  # Smaller bonus for passing 2/3 checks

            return min(score, max_subscore)

        except Exception as e:
            print(f"Error in security evaluation: {str(e)}")
            return 0

    async def evaluate_server_activity(self, token_age, server_buys, server_sells):
        try:
            score = 0
            max_subscore = 10.0

            total_transactions = server_buys + server_sells
            buy_sell_ratio = server_buys / server_sells if server_sells > 0 else server_buys

            # Evaluate total server buys & token age confluence
            if total_transactions >= 50 and token_age < 60:
                score += 8
            elif total_transactions >= 40 and token_age < 45:
                score += 8
            elif total_transactions >= 35 and token_age < 120:
                score += 5
            elif 20 <= total_transactions <= 50 and token_age < 30:
                score += 6
            elif 10 < total_transactions <= 20 and token_age < 45:
                score += 3
            elif  20 < total_transactions <= 30 and token_age < 60:
                score += 6
            elif 20 < total_transactions <= 50 and token_age < 90:
                score += 5
            elif 20 < total_transactions <= 50 and token_age < 140:
                score += 3
            elif 20 < total_transactions <= 50 and token_age < 230:
                score += 1
            elif total_transactions >= 35 and token_age < 200:
                score += 1
            elif 50 < total_transactions <= 100 and token_age < 200:
                score += 6
            elif 100 < total_transactions <= 200 and token_age < 600: 
                score += 4


            # Evaluate server buy/sell ratio
            if buy_sell_ratio > 2 and token_age < 720: #ensure for Heavy bpi, tokens under 12 hours old
                score += 10
            elif buy_sell_ratio > 2 and token_age >= 720:
                score += 6
            elif 1.5 <= buy_sell_ratio <= 2:
                score += 7  # Healthy buy pressure
            elif 1 < buy_sell_ratio < 1.5:
                score += 5  # Strong but not excessive
            elif  0.5 < buy_sell_ratio <= 1:
                score += 3  # Getting a bit high
            elif 0.3 < buy_sell_ratio < 0.5:
                score += 1

            return min(score, max_subscore)

        except Exception as e:
            print(f"Error in server activity evaluation: {str(e)}")
            return 0

    async def evaluate_social_presence(self, dexpaid, soulscannerpass, bundlebotpass, has_tg, has_x):
        try:
            score = 0
            max_subscore = 5.0

            # Both platforms present
            if has_tg and has_x:
                score += 5
            # Only one platform
            elif has_tg:
                score += 3  # Telegram slightly more important for crypto
            elif has_x:
                score += 2.5
            # No social presence
            else:
                score += 0

            if dexpaid and has_tg and has_x and soulscannerpass and bundlebotpass:
                score += 8

            if (has_tg and has_x) or (soulscannerpass and bundlebotpass) or (dexpaid and soulscannerpass and bundlebotpass) or (soulscannerpass and dexpaid and has_tg or has_x):
                score += 5

            return min(score, max_subscore)
        

        except Exception as e:
            print(f"Error in social presence evaluation: {str(e)}")
            return 0
    


class PenalizeScore:
    def __init__(self):
        self.penalty_score = 0
        self.age_conv = TokenAgeConvert()

    async def calculate_penalties(
            self,
            token_age,
            liquidity,
            server_buys,
            server_sells,
            has_tg,
            has_x,
            holdersover5percent,
            sniper_percent,
            soulscannerpasses,
            bundlebotpasses,
            dex_paid
    ):
        try:
            penalties = 0
            
            # Convert token age to minutes first
            age_in_minutes = self.age_conv.convert_token_age_to_minutes(token_age)
            
            # Token age penalty - now using converted minutes
            if age_in_minutes >= 2200:
                penalties += 4

            # Rest of penalties calculation remains the same
            if liquidity <= 20000:
                penalties += 4

            try:
                server_buy_sell_ratio = server_buys / server_sells if server_sells > 0 else server_buys
                if 0.5 <= server_buy_sell_ratio < 1:
                    penalties += 1
                elif 0 < server_buy_sell_ratio < 0.5:
                    penalties += 3
            except ZeroDivisionError:
                pass

            if not has_tg and not has_x:
                penalties += 3
            elif not has_tg or not has_x:
                penalties += 1
            if not has_tg and not has_x and not dex_paid:
                penalties += 4

            if holdersover5percent > 5:
                penalties += 5
            elif 3 <= holdersover5percent <= 5:
                penalties += 2
            elif holdersover5percent < 3:
                penalties += 1

            if 50 <= sniper_percent < 70:
                penalties += 4
            elif sniper_percent >= 70:
                penalties += 6

            if not bundlebotpasses or not soulscannerpasses:
                penalties += 0.7
            elif not bundlebotpasses and not soulscannerpasses:
                penalties += 1.5

            if (not has_tg and not has_x) and (not bundlebotpasses and not soulscannerpasses) and not dex_paid:
                penalties += 6

            return penalties

        except Exception as e:
            print(f"Error calculating penalties: {str(e)}")
            return 0























