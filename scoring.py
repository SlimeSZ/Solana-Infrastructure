import asyncio
import aiohttp

class HolderScore:  # 30% of total score
    def __init__(self):
        self.MAX_SCORE = 30.0
        self.HOLDER_AGE_MAX = 15.0  # 15% for holder/age confluence
        self.SECURITY_MAX = 15.0    # 15% for holder security metrics

    async def calculate_score(
        self, 
        token_age,
        marketcap,
        liquidity,
        server_buys,
        server_sells,
        server_count,
        has_tg,
        has_x,
        holder_count,
        dexpaid,
        top10holds,
        holdersover5percent,
        devholds,
        soulscannerpass,
        bundlebotpass,
        m30_vol,
        m30_vol_change,
        total_trade_change,
        buys_change,
        sells_change,
        sniper_percent,
        total_unique_wallets_30m,
        total_unique_wallets_1h,
        unique_wallet_change_30m,
        unique_wallet_change_1h,
        channel_metrics,
        wallet_data
    ):
        try:
            # Convert token age to minutes for consistent calculation
            age_in_minutes = self.convert_token_age_to_minutes(token_age)
            
            # Calculate both subscores
            holder_age_score = await self.holder_count_token_age_confluence(holder_count, age_in_minutes)
            security_score = await self.holder_security(top10holds, holdersover5percent, devholds, sniper_percent)
            
            if holder_age_score is None or security_score is None:
                return None

            # Normalize security score from 0-40 range to 0-15 range
            normalized_security_score = (security_score / 40) * self.SECURITY_MAX
            
            # Normalize holder age score to 0-15 range
            normalized_holder_age_score = (holder_age_score / 10) * self.HOLDER_AGE_MAX

            total_score = normalized_holder_age_score + normalized_security_score
            
            # Additional context data
            context = {
                'holder_age_score': normalized_holder_age_score,
                'security_score': normalized_security_score,
                'total_score': total_score,
                'breakdown': {
                    'holder_age_evaluation': self.get_holder_age_assessment(normalized_holder_age_score),
                    'security_evaluation': self.get_security_assessment(normalized_security_score)
                }
            }

            return total_score, context

        except Exception as e:
            print(f"Error in holder score calculation: {str(e)}")
            return None

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

    def get_holder_age_assessment(self, score):
        if score >= 13:
            return "Exceptional holder growth for token age"
        elif score >= 10:
            return "Strong holder growth"
        elif score >= 7:
            return "Good holder growth"
        elif score >= 4:
            return "Moderate holder growth"
        else:
            return "Slow holder growth"

    def get_security_assessment(self, score):
        """Get qualitative assessment of security score"""
        if score >= 13:
            return "Excellent holder distribution and security"
        elif score >= 10:
            return "Strong holder security metrics"
        elif score >= 7:
            return "Good holder security"
        elif score >= 4:
            return "Moderate security concerns"
        else:
            return "Significant security concerns"

    async def holder_count_token_age_confluence(self, holder_count, token_age):
        try:
            raw_score = (holder_count / (token_age + 3)) * 3

            if raw_score >= 100:
                return 10.0
            elif raw_score >= 90:
                return 9.0
            elif raw_score >= 80:
                return 8.0
            elif raw_score >= 70:
                return 7.0
            elif raw_score >= 60:
                return 6.0
            elif raw_score >= 50:
                return 5.0
            elif raw_score >= 40:
                return 4.0
            elif raw_score >= 30:
                return 3.0
            elif raw_score >= 20:
                return 2.0
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
                score += 10
            elif 0 < devholds < 3:
                score += 5
            elif 3 <= devholds <= 5:
                score += 2
            
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

    def get_summary(self, total_score):
        """Get overall summary of holder evaluation"""
        if total_score >= 25:
            return "Exceptional holder metrics and security"
        elif total_score >= 20:
            return "Very strong holder profile"
        elif total_score >= 15:
            return "Good holder metrics"
        elif total_score >= 10:
            return "Average holder metrics"
        else:
            return "Below average holder metrics"
        
class TokenomicScore:  # 40% of total score
    def __init__(self):
        self.MAX_SCORE = 40.0

    async def calculate_tokenomic_score(
        self,
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
        holder_count
    ):
        try:
            scores = {
                'volume_liquidity': await self.evaluate_volume_liquidity(m30_vol, liquidity, marketcap),  # 10%
                'volume_dynamics': await self.evaluate_volume_dynamics(m30_vol_change, total_trade_change),  # 10%
                'buying_pressure': await self.evaluate_buying_pressure(buys_change, sells_change, holder_count),  # 10%
                'wallet_growth': await self.evaluate_wallet_growth(
                    total_unique_wallets_30m, total_unique_wallets_1h,
                    unique_wallet_change_30m, unique_wallet_change_1h,
                    holder_count
                )  # 10%
            }

            total_score = sum(scores.values())
            return min(total_score, self.MAX_SCORE)

        except Exception as e:
            print(f"Error in tokenomic score calculation: {str(e)}")
            return 0

    async def evaluate_volume_liquidity(self, m30_vol, liquidity, marketcap):
        try:
            score = 0
            max_subscore = 10.0

            # Volume to Liquidity ratio (healthy is 15-30% of liquidity)
            vol_liq_ratio = (m30_vol / liquidity) * 100 if liquidity > 0 else 0
            if 20 <= vol_liq_ratio <= 30:
                score += 5
            elif 15 <= vol_liq_ratio < 20:
                score += 4
            elif 30 < vol_liq_ratio <= 40:
                score += 3
            elif vol_liq_ratio > 40:
                score += 1

            # Marketcap to Liquidity ratio (looking for good backing)
            mc_liq_ratio = (marketcap / liquidity) if liquidity > 0 else 0
            if 2 <= mc_liq_ratio <= 4:
                score += 5
            elif 4 < mc_liq_ratio <= 6:
                score += 3
            elif 1 <= mc_liq_ratio < 2:
                score += 2

            return min(score, max_subscore)

        except Exception as e:
            print(f"Error in volume liquidity evaluation: {str(e)}")
            return 0

    async def evaluate_volume_dynamics(self, m30_vol_change, total_trade_change):
        try:
            score = 0
            max_subscore = 10.0

            # Volume change evaluation
            if 50 <= m30_vol_change <= 100:
                score += 5
            elif 100 < m30_vol_change <= 200:
                score += 4
            elif 200 < m30_vol_change <= 300:
                score += 3
            elif m30_vol_change > 300:
                score += 2

            # Trade count change evaluation
            if 30 <= total_trade_change <= 60:
                score += 5
            elif 60 < total_trade_change <= 100:
                score += 4
            elif 100 < total_trade_change <= 150:
                score += 3
            elif total_trade_change > 150:
                score += 2

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
            if 1.5 <= buy_sell_ratio <= 2.5:
                score += 5
            elif 2.5 < buy_sell_ratio <= 3.5:
                score += 4
            elif 3.5 < buy_sell_ratio <= 5:
                score += 3
            elif buy_sell_ratio > 5:
                score += 2

            # Holder growth confluence
            if holder_count > 0:
                holder_buy_ratio = buys_change / holder_count
                if 0.3 <= holder_buy_ratio <= 0.5:
                    score += 5
                elif 0.5 < holder_buy_ratio <= 0.8:
                    score += 4
                elif 0.8 < holder_buy_ratio <= 1.2:
                    score += 3
                elif holder_buy_ratio > 1.2:
                    score += 2

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
                if 30 <= unique_wallet_change_30m <= 50:
                    score += 5
                elif 50 < unique_wallet_change_30m <= 80:
                    score += 4
                elif 80 < unique_wallet_change_30m <= 120:
                    score += 3
                elif unique_wallet_change_30m > 120:
                    score += 2

                # Confluence with holder count
                wallet_holder_ratio = total_unique_wallets_30m / holder_count if holder_count > 0 else 0
                if 0.2 <= wallet_holder_ratio <= 0.4:
                    score += 5
                elif 0.4 < wallet_holder_ratio <= 0.6:
                    score += 4
                elif 0.6 < wallet_holder_ratio <= 0.8:
                    score += 3
                elif wallet_holder_ratio > 0.8:
                    score += 2

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

    async def calculate_trust_score(
        self,
        server_buys,
        server_sells,
        has_tg,
        has_x,
        dexpaid,
        soulscannerpass,
        bundlebotpass
    ):
        try:
            scores = {
                'security_checks': await self.evaluate_security(dexpaid, soulscannerpass, bundlebotpass),  # 15%
                'server_activity': await self.evaluate_server_activity(server_buys, server_sells),  # 10%
                'social_presence': await self.evaluate_social_presence(has_tg, has_x)  # 5%
            }

            total_score = sum(scores.values())
            return min(total_score, self.MAX_SCORE)

        except Exception as e:
            print(f"Error in trust score calculation: {str(e)}")
            return 0

    async def evaluate_security(self, dexpaid, soulscannerpass, bundlebotpass):
        try:
            score = 0
            max_subscore = 15.0

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
                score += 2  # Bonus points for passing all security checks
            
            # Partial confluence bonuses
            elif (dexpaid and soulscannerpass) or (dexpaid and bundlebotpass) or (soulscannerpass and bundlebotpass):
                score += 1  # Smaller bonus for passing 2/3 checks

            return min(score, max_subscore)

        except Exception as e:
            print(f"Error in security evaluation: {str(e)}")
            return 0

    async def evaluate_server_activity(self, server_buys, server_sells):
        try:
            score = 0
            max_subscore = 10.0

            total_transactions = server_buys + server_sells
            buy_sell_ratio = server_buys / server_sells if server_sells > 0 else server_buys

            # Evaluate total transaction volume
            if total_transactions >= 50:
                score += 4
            elif 30 <= total_transactions < 50:
                score += 3
            elif 15 <= total_transactions < 30:
                score += 2
            elif total_transactions > 0:
                score += 1

            # Evaluate buy/sell ratio
            if 1.5 <= buy_sell_ratio <= 2.5:
                score += 6  # Healthy buy pressure
            elif 2.5 < buy_sell_ratio <= 3.5:
                score += 4  # Strong but not excessive
            elif 3.5 < buy_sell_ratio <= 5:
                score += 3  # Getting a bit high
            elif buy_sell_ratio > 5:
                score += 2  # Potentially manipulated
            elif 1 <= buy_sell_ratio < 1.5:
                score += 3  # Balanced but needs more buy pressure
            else:
                score += 1  # More sells than buys

            return min(score, max_subscore)

        except Exception as e:
            print(f"Error in server activity evaluation: {str(e)}")
            return 0

    async def evaluate_social_presence(self, has_tg, has_x):
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

            return min(score, max_subscore)

        except Exception as e:
            print(f"Error in social presence evaluation: {str(e)}")
            return 0

    async def get_security_status(self, dexpaid, soulscannerpass, bundlebotpass):
        """Additional method to get a quick security status summary"""
        try:
            checks_passed = sum([dexpaid, soulscannerpass, bundlebotpass])
            
            if checks_passed == 3:
                return "High Trust - All Security Checks Passed"
            elif checks_passed == 2:
                return "Moderate Trust - Passed 2/3 Security Checks"
            elif checks_passed == 1:
                return "Low Trust - Only Passed 1 Security Check"
            else:
                return "Untrusted - Failed All Security Checks"

        except Exception as e:
            print(f"Error getting security status: {str(e)}")
            return "Error Evaluating Security Status"
        

class CompositeScorer:
    def __init__(self):
        self.holder_scorer = HolderScore()
        self.tokenomic_scorer = TokenomicScore()
        self.trust_scorer = TrustScore()

    async def run_scoring_analysis(self):
        try:
            # Dummy test values
            test_data = {
                'token_age': {'value': 120, 'unit': 'minutes'},
                'marketcap': 500000,
                'liquidity': 100000,
                'server_buys': 35,
                'server_sells': 20,
                'server_count': 55,
                'has_tg': True,
                'has_x': True,
                'holder_count': 800,
                'dexpaid': True,
                'top10holds': 12,
                'holdersover5percent': 1,
                'devholds': 2,
                'soulscannerpass': True,
                'bundlebotpass': True,
                'm30_vol': 30000,
                'm30_vol_change': 75,
                'total_trade_change': 45,
                'buys_change': 60,
                'sells_change': 30,
                'sniper_percent': 3,
                'total_unique_wallets_30m': 200,
                'total_unique_wallets_1h': 300,
                'unique_wallet_change_30m': 40,
                'unique_wallet_change_1h': 60,
                'channel_metrics': None,
                'wallet_data': None
            }

            # Run all scoring systems
            holder_score, holder_context = await self.holder_scorer.calculate_score(**test_data)
            
            tokenomic_score = await self.tokenomic_scorer.calculate_tokenomic_score(
                marketcap=test_data['marketcap'],
                m30_vol=test_data['m30_vol'],
                m30_vol_change=test_data['m30_vol_change'],
                liquidity=test_data['liquidity'],
                total_trade_change=test_data['total_trade_change'],
                buys_change=test_data['buys_change'],
                sells_change=test_data['sells_change'],
                total_unique_wallets_30m=test_data['total_unique_wallets_30m'],
                total_unique_wallets_1h=test_data['total_unique_wallets_1h'],
                unique_wallet_change_30m=test_data['unique_wallet_change_30m'],
                unique_wallet_change_1h=test_data['unique_wallet_change_1h'],
                holder_count=test_data['holder_count']
            )

            trust_score = await self.trust_scorer.calculate_trust_score(
                server_buys=test_data['server_buys'],
                server_sells=test_data['server_sells'],
                has_tg=test_data['has_tg'],
                has_x=test_data['has_x'],
                dexpaid=test_data['dexpaid'],
                soulscannerpass=test_data['soulscannerpass'],
                bundlebotpass=test_data['bundlebotpass']
            )

            # Calculate total score
            total_score = holder_score + tokenomic_score + trust_score

            # Print detailed analysis
            print("\n" + "="*50)
            print("COMPREHENSIVE SCORING ANALYSIS")
            print("="*50)

            print("\n🏆 TOTAL SCORE: {:.2f}/100".format(total_score))
            print("-"*50)

            print("\n📊 HOLDER METRICS (30% weight)")
            print(f"Score: {holder_score:.2f}/30")
            print(f"Holder Age Evaluation: {holder_context['breakdown']['holder_age_evaluation']}")
            print(f"Security Evaluation: {holder_context['breakdown']['security_evaluation']}")

            print("\n💰 TOKENOMICS (40% weight)")
            print(f"Score: {tokenomic_score:.2f}/40")
            print(f"Volume/Liquidity Ratio: {(test_data['m30_vol']/test_data['liquidity'])*100:.2f}%")
            print(f"Buy/Sell Change Ratio: {(test_data['buys_change']/test_data['sells_change']):.2f}")

            print("\n🔒 TRUST METRICS (30% weight)")
            print(f"Score: {trust_score:.2f}/30")
            security_status = await self.trust_scorer.get_security_status(
                test_data['dexpaid'],
                test_data['soulscannerpass'],
                test_data['bundlebotpass']
            )
            print(f"Security Status: {security_status}")

            # Provide overall assessment
            print("\n📝 OVERALL ASSESSMENT")
            if total_score >= 80:
                print("Excellent metrics across all categories")
            elif total_score >= 65:
                print("Strong performance with some room for improvement")
            elif total_score >= 50:
                print("Average performance - exercise caution")
            else:
                print("Below average metrics - high risk")

        except Exception as e:
            print(f"Error in scoring analysis: {str(e)}")

if __name__ == "__main__":
    scorer = CompositeScorer()
    asyncio.run(scorer.run_scoring_analysis())