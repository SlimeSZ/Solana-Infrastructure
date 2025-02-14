import asyncio
import aiohttp
from typing import Dict, Optional, Tuple, Union, Any

class CompositeScore:
    def __init__(self):
        self.score = 0
        
    def _calculate_buy_sell_ratio(self, buys: float, sells: float) -> Tuple[float, float]:
        """Calculate buy/sell ratio and pressure metrics"""
        if not isinstance(buys, (int, float)) or not isinstance(sells, (int, float)):
            return 0, 0
            
        # Avoid division by zero
        if sells == 0:
            return float('inf'), 1.0 if buys > 0 else 0  # Perfect ratio if buys exist
            
        ratio = buys / sells
        
        # Calculate pressure (normalized between 0-1)
        # Pressure increases with higher buy/sell ratio but caps at 1.0
        pressure = min(ratio / 2, 1.0)
        
        return ratio, pressure

    def _analyze_wallet_performance(self, wallet_data: Dict) -> Tuple[float, Dict]:
        """Analyze wallet performance metrics"""
        if not wallet_data:
            return 0, {}
            
        metrics = {
            'avg_pnl': 0,
            'total_wins': 0,
            'total_losses': 0,
            'win_rate': 0,
            'trading_experience': 0  # Based on tokens traded
        }
        
        total_pnl = 0
        total_tokens = 0
        wallet_count = 0
        
        for wallet, data in wallet_data.items():
            if not isinstance(data, dict):
                continue
                
            wallet_count += 1
            pnl = data.get('pnl', 0)
            total_pnl += pnl
            
            wins = data.get('wins', 0)
            losses = data.get('losses', 0)
            metrics['total_wins'] += wins
            metrics['total_losses'] += losses
            
            tokens_traded = data.get('tokens_traded', 0)
            total_tokens += tokens_traded
        
        if wallet_count > 0:
            metrics['avg_pnl'] = total_pnl / wallet_count
            
        total_trades = metrics['total_wins'] + metrics['total_losses']
        if total_trades > 0:
            metrics['win_rate'] = metrics['total_wins'] / total_trades
            
        # Calculate wallet performance score
        score = 0
        
        # PNL scoring
        if metrics['avg_pnl'] > 100:  # Extremely profitable
            score += 1.0
        elif metrics['avg_pnl'] > 50:
            score += 0.8
        elif metrics['avg_pnl'] > 20:
            score += 0.5
        elif metrics['avg_pnl'] > 10:
            score += 0.3
        elif metrics['avg_pnl'] < -20:  # Penalize significant losses
            score -= 0.3
            
        # Win rate scoring
        if metrics['win_rate'] > 0.8:
            score += 0.8
        elif metrics['win_rate'] > 0.6:
            score += 0.5
        elif metrics['win_rate'] > 0.5:
            score += 0.3
            
        # Trading experience (tokens traded) scoring
        avg_tokens = total_tokens / wallet_count if wallet_count > 0 else 0
        if avg_tokens > 500:
            score += 0.4
        elif avg_tokens > 200:
            score += 0.2
            
        # Normalize final score to 0-1 range
        final_score = min(max(score / 2.2, 0), 1)  # 2.2 is max possible score
        
        return final_score, metrics
        
    def _standardize_age(self, token_age: Dict) -> Optional[float]:
        """Convert token age to hours for standardized processing"""
        if not token_age or not isinstance(token_age, dict):
            return None
            
        value = token_age.get('value')
        unit = token_age.get('unit', '').lower()
        
        if not value or not unit:
            return None
            
        # Convert to hours
        if 'minute' in unit:
            return value / 60
        elif 'hour' in unit:
            return value
        elif 'day' in unit:
            return value * 24
        return None

    def _evaluate_channel_combinations(self, channel_metrics: Dict, age_hours: float) -> Tuple[float, Dict]:
        """Evaluate channel combinations and their significance"""
        if not channel_metrics:
            return 0, {}
            
        combination_score = 0
        insights = {}
        
        # Define channel weights and preferences
        preferred_channels = {
            'Smart': 1.4,
            'Legend': 1.3,
            'Whale': 1.3,
            'Fresh': 1.5,  # Higher weight for fresh
            'Fresh 5sol 1m MC': 1.4,
            'Fresh 1h': 1.3,
            'Degen': 1.2
        }
        
        # Penalize channels
        penalized_channels = {
            'Kol Alpha': -0.2,
            'Kol Regular': -0.2
        }
        
        swt_channels = channel_metrics.get('swt', {}).get('channels', {})
        fresh_channels = channel_metrics.get('fresh', {}).get('channels', {})
        degen_data = channel_metrics.get('degen', {}).get('channels', {})
        
        # Check for preferred combinations
        if any(channel in swt_channels for channel in ['Smart', 'Legend', 'Whale']):
            if fresh_channels:  # Any fresh channel presence
                combination_score += 0.8
                insights['strong_combo'] = "Found strong SWT + Fresh combination"
            if 'Degen' in degen_data:
                combination_score += 0.6
                insights['degen_combo'] = "Found strong SWT + Degen combination"
                
        # Age-based channel evaluation
        if age_hours <= 1:  # Ultra fresh
            for channel, data in fresh_channels.items():
                buy_pressure = data.get('buy_pressure', 0)
                if buy_pressure > 1.5:  # Strong buying in fresh channels
                    combination_score += 0.4
                    insights['fresh_pressure'] = f"Strong buying pressure in {channel}"
                    
        # Evaluate individual channel contributions
        for channel_type, channels in channel_metrics.items():
            for channel_name, data in channels.get('channels', {}).items():
                # Apply channel weights
                weight = preferred_channels.get(channel_name, 1.0)
                penalty = penalized_channels.get(channel_name, 0)
                
                buy_pressure = data.get('buy_pressure', 0)
                count = data.get('count', 0)
                
                # Calculate channel score
                channel_score = (
                    (weight * min(count / 50, 1.0)) +  # Base score from activity
                    (weight * min(buy_pressure / 2, 1.0))  # Buy pressure contribution
                ) + penalty  # Apply any penalties
                
                combination_score += channel_score
                
                # Add insights for significant channel activity
                if buy_pressure > 1.5 and count > 10:
                    insights[f'{channel_name}_activity'] = f"Strong activity in {channel_name}"
                    
        # Normalize final score
        final_score = min(max(combination_score / 5, 0), 1)  # Normalize to 0-1 range
        
        return final_score, insights

    async def calculate_score(
        self,
        token_age: Dict,
        telegram: Optional[str],
        twitter: Optional[str],
        holder_count: int,
        dex_paid: bool,
        top_10_holding_percentage: float,
        holders_over_5_percent: int,
        dev_holding_percentage: float,
        soul_scanner_pass: bool,
        bundle_bot_pass: bool,
        marketcap: float,
        m5_vol: float,
        liquidity: float,
        server_buys: float,
        server_sells: float,
        server_count: int,
        wallet_data: Optional[Dict] = None,
        channel_metrics: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Calculate comprehensive token score based on multiple metrics"""
        try:
            metrics = {
                'age_score': 0,
                'social_score': 0,
                'holder_metrics_score': 0,
                'volume_liquidity_score': 0,
                'server_activity_score': 0,
                'security_score': 0,
                'buy_pressure': 0,
                'age_hours': 0,
                'buy_sell_ratio': 0,
                'wallet_score': 0,
                'wallet_metrics': {},
                'channel_scores': {},
                'channel_metrics': channel_metrics or {}
            }
            
            # Standardize age
            age_hours = self._standardize_age(token_age)
            if age_hours is None:
                return None
            
            metrics['age_hours'] = age_hours
            
            # Calculate buy/sell metrics
            buy_sell_ratio, buy_pressure = self._calculate_buy_sell_ratio(server_buys, server_sells)
            metrics['buy_sell_ratio'] = buy_sell_ratio
            metrics['buy_pressure'] = buy_pressure

            # 1. Age-based scoring with server activity confluence
            if age_hours <= 1:  # Ultra fresh
                metrics['age_score'] = 1.0
                if server_count > 50:
                    metrics['age_score'] += 0.5
                if buy_sell_ratio > 2:
                    metrics['age_score'] += 0.3
            elif age_hours <= 6:  # Very fresh
                metrics['age_score'] = 0.8
                if server_count > 100:
                    metrics['age_score'] += 0.4
                if buy_sell_ratio > 2:
                    metrics['age_score'] += 0.2
            elif age_hours <= 24:  # Fresh
                metrics['age_score'] = 0.5
                if server_count > 200:
                    metrics['age_score'] += 0.3
                if buy_sell_ratio > 2:
                    metrics['age_score'] += 0.1
            
            # 2. Server activity score with channel-specific analysis
            metrics['server_activity_score'] = min(server_count / 1000, 1.0)  # Base score
            
            if channel_metrics:
                channel_scores = {}
                
                # Weight definitions for different channel types
                swt_weights = {
                    'Whale': 1.5,
                    'Smart': 1.4,
                    'Legend': 1.3,
                    'Kol Alpha': 1.2,
                    'Challenge': 1.1,
                    'High Freq': 1.0,
                    'Insider': 1.3
                }
                
                # Process SWT channels
                if 'swt' in channel_metrics:
                    for channel_name, data in channel_metrics['swt']['channels'].items():
                        weight = swt_weights.get(channel_name, 1.0)
                        channel_buy_pressure = data['buys'] / (data['sells'] + 0.0001)  # Avoid div by zero
                        channel_score = min((data['count'] / 100) * weight, 1.0)
                        
                        if channel_buy_pressure > 2:  # Strong buy pressure
                            channel_score *= 1.3
                        
                        channel_scores[channel_name] = channel_score
                
                # Process Fresh channels with time sensitivity
                if 'fresh' in channel_metrics:
                    fresh_channels = channel_metrics['fresh']['channels']
                    for channel_name, data in fresh_channels.items():
                        base_score = min((data['count'] / 50) * 1.2, 1.0)  # Higher weight for fresh
                        
                        # Higher score for active fresh channels with good buy pressure
                        if data['buys'] > data['sells'] * 1.5:
                            base_score *= 1.4
                            
                        channel_scores[channel_name] = base_score
                
                # Calculate weighted average of channel scores
                total_weight = sum(swt_weights.values())
                weighted_channel_score = sum(channel_scores.values()) / len(channel_scores) if channel_scores else 0
                
                # Update main server activity score with channel insights
                metrics['server_activity_score'] = (metrics['server_activity_score'] + weighted_channel_score) / 2
                metrics['channel_scores'] = channel_scores
                
            if buy_pressure > 0.7:  # Strong overall buy pressure
                metrics['server_activity_score'] *= 1.3  # Boost score
            
            # 3. Volume and liquidity evaluation
            if m5_vol and liquidity:
                vol_liq_ratio = m5_vol / liquidity if liquidity > 0 else 0
                if vol_liq_ratio > 0.5:  # High volume relative to liquidity
                    metrics['volume_liquidity_score'] = 0.8
                elif vol_liq_ratio > 0.3:
                    metrics['volume_liquidity_score'] = 0.5
                elif vol_liq_ratio > 0.1:
                    metrics['volume_liquidity_score'] = 0.3

            # 4. Holder metrics evaluation
            metrics['holder_metrics_score'] = 0
            if holder_count > 500:
                metrics['holder_metrics_score'] += 0.5
            if dev_holding_percentage <= 2:
                metrics['holder_metrics_score'] += 0.5
            if top_10_holding_percentage <= 15:
                metrics['holder_metrics_score'] += 0.5
            if holders_over_5_percent <= 2:
                metrics['holder_metrics_score'] += 0.5
                
            # 5. Security and verification score
            metrics['security_score'] = 0
            if soul_scanner_pass:
                metrics['security_score'] += 0.5
            if bundle_bot_pass:
                metrics['security_score'] += 0.5
            if dex_paid:
                metrics['security_score'] += 0.5
                
            # 6. Social presence score
            metrics['social_score'] = 0
            if telegram:
                metrics['social_score'] += 0.4
            if twitter:
                metrics['social_score'] += 0.4
            if telegram and twitter:  # Bonus for both
                metrics['social_score'] += 0.2
                
            if wallet_data:
                wallet_score, wallet_metrics = self._analyze_wallet_performance(wallet_data)
                metrics['wallet_score'] = wallet_score
                metrics['wallet_metrics'] = wallet_metrics
                
                # Add wallet insights
                if wallet_score > 0.7:
                    metrics['wallet_insights'] = "Top wallets show strong profitable trading history"
                elif wallet_score > 0.5:
                    metrics['wallet_insights'] = "Top wallets demonstrate decent trading performance"
                elif wallet_score > 0.3:
                    metrics['wallet_insights'] = "Top wallets show moderate trading success"
                else:
                    metrics['wallet_insights'] = "Top wallets show mixed or limited trading success"
            
            # Calculate channel combination score
            channel_score, channel_insights = self._evaluate_channel_combinations(channel_metrics, age_hours)
            metrics['channel_combination_score'] = channel_score
            metrics['channel_insights'] = channel_insights
            
            # Adjust server activity score based on channel combinations
            if channel_score > 0.7:
                metrics['server_activity_score'] *= 1.3  # Boost for strong channel combinations
            
            # Calculate final composite score with channel emphasis
            base_score = (
                metrics['age_score'] * 1.5 +  # Higher weight for age
                metrics['server_activity_score'] * 1.2 +  # Server activity
                metrics['channel_combination_score'] * 1.4 +  # High weight for channel combinations
                metrics['volume_liquidity_score'] * 1.1 +
                metrics['holder_metrics_score'] * 1.0 +
                metrics['security_score'] * 1.2 +
                metrics['social_score'] * 0.8
            )
            
            # Add wallet score if available
            if wallet_data:
                self.score = (base_score + (metrics['wallet_score'] * 1.4)) / 8.4  # Normalize including wallet weight
            else:
                self.score = base_score / 7  # Original normalization
            
            # Add bonus for exceptional confluence
            if (age_hours <= 6 and 
                buy_pressure > 0.8 and 
                metrics['security_score'] > 1.0 and 
                metrics['holder_metrics_score'] > 1.5):
                self.score *= 1.2  # 20% bonus for perfect confluence
                
            # Process metrics before returning
            processed_metrics = {}
            for k, v in metrics.items():
                if isinstance(v, (float, int)):
                    processed_metrics[k] = round(float(v), 3)
                elif isinstance(v, dict):
                    processed_metrics[k] = v  # Keep dictionaries as is
                else:
                    processed_metrics[k] = v  # Keep other types unchanged

            return {
                'total_score': round(self.score, 3),
                'metrics': processed_metrics
            }
            
        except Exception as e:
            print(f"Error calculating composite score: {str(e)}")
            return None