# webhooks.py
import asyncio
import aiohttp
from env import ALEF_ALERT_WEBHOOK
import discord
from alefalerts import MessageSender 
from env import MULTIALERT_WEBHOOK, SCORE_WEBHOOK, TWOX_WEBHOOK, SOL_10_5_WEBHOOK, SCORE_WEBHOOK, TRADE_WEBHOOK, LARGE_BUY_WEBHOOK
import csv
import io
from datetime import datetime
import logging

class AlefAlertWebhook:
    def __init__(self):
        self.message_sender = MessageSender() 

    async def full_send_ca_to_alefdao(self, ca: str):
        try:
            # First send webhook
            async with aiohttp.ClientSession() as session:
                await session.post(
                    ALEF_ALERT_WEBHOOK,
                    json={'content': 'CA Passed Both Soul Scan & Bundle Bot Check!'}
                )
            print("Sent full pass webhook notification")
            
            # Wait briefly
            await asyncio.sleep(3)
            
            # Then send Discord message
            await self.message_sender.send_message(ca)
            print(f"Sent CA to Discord channel: {ca}")
            
        except Exception as e:
            print(f"Error in full send sequence: {str(e)}")
            import traceback
            traceback.print_exc()

    async def conditional_send_ca_to_alefdao(self, ca: str):
        try:
            # First send webhook
            async with aiohttp.ClientSession() as session:
                await session.post(
                    ALEF_ALERT_WEBHOOK,
                    json={'content': 'CA passed Soul Scanner checker but failed bundle bot check/Bundle Bot down\nTrade w Caution!'}
                )
            print("Sent conditional pass webhook notification")
            
            # Wait briefly
            await asyncio.sleep(3)
            
            # Then send Discord message
            await self.message_sender.send_message(ca)
            print(f"Sent CA to Discord channel: {ca}")
            
        except Exception as e:
            print(f"Error in conditional send sequence: {str(e)}")
            import traceback
            traceback.print_exc()


class MultiAlert:
    def __init__(self):
        pass

    async def multialert_webhook(self, token_name, ca, marketcap, m5_vol, liquidity, telegram, twitter, photon_link, bull_x_link, dex_link, swt_count, swt_buys, swt_sells, fresh_count, fresh_buys, fresh_sells, last_3_tx, holder_count, dev_holding_percentage, token_migrated, passes_soulscanner, passes_bundlebot, dex_paid, token_age, top_10_holding_percentage, holders_over_5, wallet_data, m30_vol, m30_vol_change, new_unique_wallets_30m, new_unique_wallet_30m_change, trade_change_30m, buy_change_30m, sell_change_30m, channel_text, sniper_percent, comp_score):
        try:
            #place holders
            new_unique_wallet_30m_change = new_unique_wallet_30m_change or 0
            trade_change_30m = trade_change_30m or 0
            buy_change_30m = buy_change_30m or 0
            sell_change_30m = sell_change_30m or 0
            m5_vol = m5_vol or 0
            m30_vol = m30_vol or 0
            m30_vol_change = m30_vol_change or 0
            uniqueplaceholder = "Increase" if new_unique_wallet_30m_change > 0 else "Decrease"
            tradeplaceholder = "Increase" if trade_change_30m > 0 else "Decrease"
            buyplaceholder = "Increase" if buy_change_30m > 0 else "Decrease"
            sellplaceholder = "Increase" if sell_change_30m > 0 else "Decrease"
            sniperplaceholder = "❌" if sniper_percent >= 45 else "✅"
            score_emoji = "🏆" if comp_score > 60 else "⚠️"

            embed = {
                "title": "🚨 Multi Ape Alert",
                "color": 0x00ff00,
                "fields": [
                    {
                        "name": f"`{token_name}`",
                        "value": (
                            f"CA: `{ca}`\n"
                            f"💰 Marketcap: $`{marketcap:,.2f}`\n"
                            f"💧 Liquidity: $`{liquidity:,.2f}`\n"
                            f"📊 5m Volume: $`{m5_vol:,.2f}`\n"
                            f"📊 30m Volume: $`{m30_vol:,.2f}` -- Change of: {m30_vol_change:.2f}%\n"
                            f" `Total Trades have {tradeplaceholder}d by {trade_change_30m:.2f}% in the last 30 min`\n"
                            f" `Buys have {buyplaceholder}d by {buy_change_30m:.2f} in the last 30 min `\n"
                            f" `Sells have {sellplaceholder}d by {sell_change_30m:.2f} in the last 30 min`\n"
                            f"⏰ `Age`: {token_age['value']} {token_age['unit']}\n" 
                        ),
                        "inline": False
                    },
                    {
                        "name": "🔍 Server Activity",
                        "value": (
                            f"SWT Activity: token has `{swt_count}` mentions (`{swt_buys:.2f}` SOL Buys, `{swt_sells:.2f}` SOL sells)\n"
                            f"Fresh Activity: ca has `{fresh_count}` mentions (`{fresh_buys:.2f}` SOL buys, `{fresh_sells:.2f}` SOL sells)\n"
                        ),
                        "inline": False
                    },
                    {
                        "name": f"`Token aped by wallets in:`",
                        "value": f"{channel_text}",
                        "inline": False
                    },
                    {
                        "name": "📊 Holder Analysis",
                        "value": (
                            f"👥 Total Holders: `{holder_count}`\n"
                            f"📊 Top 10 Hold: `{top_10_holding_percentage:.2f}`%\n"
                            f"⚠️ Holders >5%: `{holders_over_5}`\n"
                            f"👨‍💼 Dev Holding: `{dev_holding_percentage:.2f}`%\n"
                            f" `{new_unique_wallets_30m} Total Unique Wallets in last 30 min. {uniqueplaceholder} of {new_unique_wallet_30m_change:.2f}`%"
                        ),
                        "inline": False
                    },
                    {
                        "name": "🛡️ Security Checks",
                        "value": (
                            f"🔒 Soul Scanner: {'✅' if passes_soulscanner else '❌'}\n"
                            f"🔍 Bundle Bot: {'✅' if passes_bundlebot else '❌'}\n"
                            f"💰 DEX Paid: {'✅' if dex_paid else '❌'}\n"
                            f"🔄 Token Migrated: {'⚠️' if token_migrated else '✅'}\n"
                            f"🎯 Sniper Percent: {sniper_percent:.2f}% {sniperplaceholder}\n"
                        ),
                        "inline": False
                    }
                ]
            }

            # Add Wallet Analysis if available
            if wallet_data and isinstance(wallet_data, dict):  # Extra type check for safety
                wallet_analysis = ""
                for wallet_address, data in wallet_data.items():
                    wallet_analysis += (
                        f"`Wallet {wallet_address[:8]}`...\n"
                        f"💰 Holding: {data['holding_percentage']:.2f}%\n"
                        f"📈 PNL: {data['pnl']:.4f} SOL\n"
                        f"🎯 Tokens Traded: {data['tokens_traded']}\n"
                        f"✅ Wins: {data['wins']}\n"
                        f"❌ Losses: {data['losses']}\n"
                        f"{'─' * 20}\n"
                    )
                if wallet_analysis:
                    embed["fields"].append({
                        "name": "Top 3 Wallets Latest Trade Report",
                        "value": wallet_analysis[:1024],
                        "inline": False
                    })

            if last_3_tx:
                tx_summary = ""
                for tx in last_3_tx:
                    tx_summary += f"• {tx}\n"
                if tx_summary:
                    embed["fields"].append({
                        "name": "🔄 Recent Transactions",
                        "value": tx_summary[:1024],
                        "inline": False
                    })

            links = (
                f"🔗 DexScreener: [Chart]({dex_link})\n"
                f"📱 Photon: [Trade]({photon_link})\n"
                f"🐂 BullX: [Trade]({bull_x_link})\n"
            )
            if telegram:
                links += f"💬 Telegram: [Join]({telegram})\n"
            if twitter:
                links += f"🐦 Twitter: [Follow]({twitter})\n"
            
            embed["fields"].append({
                "name": "Links",
                "value": links,
                "inline": False
            })
            embed["fields"].append({
                "name": "",
                "value": f"`{ca}`",
                "inline": False
            })
            embed["fields"].append({
                "name": "Final Composite Score",
                "value": f"{score_emoji}{comp_score:.2f}%",
                "inline": False
            })

            data = {
                "username": "Multi Alert Bot",
                "embeds": [embed]
            }

            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(MULTIALERT_WEBHOOK, json=data) as response:
                    if response.status == 204:
                        print(f"Successfully sent Multi Alert for {ca}")
                    else:
                        error_text = await response.text()
                        print(f"Failed to send multialert webhook: {response.status}")
                        print(f"Error details: {error_text}")

        except Exception as e:
            print(f"Error in multialert webhook: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def twox_multialert_webhook(self, token_name, ca, initial_mc, new_mc, increase_percentage, x_val, time_elapsed):
        try:
            data = {
                "username": "Marketcap Increase Alert",
                "embeds": [
                    {
                        "title": "🚀 2x+ Alert!",
                        "description": (
                            f"Token `{token_name}` has done a {x_val}X! Increase of {increase_percentage:.2f}"
                            f"CA: `{ca}`"
                        ),
                        "fields": [
                            {
                                "name": "Initial MC",
                                "value": f"${initial_mc:,.2f}",
                                "inline": False
                            },
                            {
                                "name": "New MC",
                                "value": f"${new_mc:,.2f}",
                                "inline": False
                            },
                            {
                                "name": f"Increase of {increase_percentage:.2f}",
                                "value": f"{x_val}X !!!",
                                "inline": False
                            }
                        ]
                    }
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(TWOX_WEBHOOK, json=data) as response:
                    if response.status == 204:
                        print(f"2x+ Alert Sent SUCCESSFULLLYYY")
                    else:
                        print(f"Error sending 2x alert :(((((((((((())))))))))))")
        except Exception as e:
            print(str(e))

    async def tensolbuywebhook(self, token_name, ca, channel_name):
        try:
            data = {
                "username": "Ten sol + Buy Alert",
                "embeds": [
                    {
                        "title": "10+ SOL BUY DETECTED",
                        "fields": [
                            {
                                "name": f"Token: {token_name}",
                                "value": f"CA: {ca}",
                                "inline": False
                            },
                            {
                                "name": "Aped By wallet(s) in:",
                                "value": channel_name,
                                "inline": False
                            }
                        ]
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(SOL_10_5_WEBHOOK, json=data) as response:
                    if response.status == 204:
                        print("Alert for 10+ SOL buy SENT")
                    else:
                        print(f"Failed to send webhook, status code: {response.status}")
        except Exception as e:
            print(f"Failed to send webhook: {str(e)}")

    async def score_webhook(
        self,
        token_name: str,
        ca: str,
        # Holder Score Components
        holder_total: float,
        holder_age_confluence: float,
        holder_security: float,
        holder_wallet_analysis: float,
        # Tokenomic Score Components
        tokenomic_total: float,
        tokenomic_vol_liq: float,
        tokenomic_30m_vol: float,
        tokenomic_5m_vol: float,
        tokenomic_trade_confluence: float,
        tokenomic_buy_pressure: float,
        tokenomic_wallet_growth: float,
        # Trust Score Components
        trust_total: float,
        trust_bs_confluence: float,
        trust_age_count: float,
        trust_security: float,
        trust_activity: float,
        trust_social: float,
        # Final Calculations
        total_before_penalties: float,
        penalties: float,
        final_score: float

    ):
        total_holder_percentage = (holder_total / 30) * 100 
        total_tokenomic_percentage = (tokenomic_total / 40) * 100
        total_trust_percentage = (trust_total / 30) * 100
        try:
            data = {
                "embeds": [
                    {
                        "title": f"Composite Score Report for {token_name}",
                        "description": f"CA: `{ca}`",
                        "color": await self.get_score_color(final_score),  # Helper method to determine color based on score
                        "fields": [
                            {
                                "name": "🏆 Final Score",
                                "value": f"**{final_score:.2f}/100**\nBefore Penalties: {total_before_penalties:.2f}%\nPenalties: -{penalties:.2f}%",
                                "inline": False
                            },
                            {
                                "name": f"👥 Holder Score ({total_holder_percentage:.2f}%)",
                                "value": f"Total: **{holder_total:.2f}/30**\n" + 
                                    f"• Age Holder Count Relation: {holder_age_confluence:.2f}/10\n" +
                                    f"• Security: {holder_security:.2f}/10\n" +
                                    f"• Wallet Analysis: {holder_wallet_analysis:.2f}/10",
                                "inline": True
                            },
                            {
                                "name": f"📊 Tokenomic Score ({total_tokenomic_percentage:.2f}%)",
                                "value": f"Total: **{tokenomic_total:.2f}/40**\n" +
                                    f"• Vol & MC/Liq Relations: {tokenomic_vol_liq:.2f}/8\n" +
                                    f"• 30m Vol: {tokenomic_30m_vol:.2f}/4\n" +
                                    f"• 5m Vol: {tokenomic_5m_vol:.2f}/6\n" +
                                    f"• Trade Confluence: {tokenomic_trade_confluence:.2f}/6\n" +
                                    f"• Buy Pressure: {tokenomic_buy_pressure:.2f}/6\n" +
                                    f"• Wallet Growth: {tokenomic_wallet_growth:.2f}/6",
                                "inline": True
                            },
                            {
                                "name": f"🔒 Trust Score ({total_trust_percentage:.2f}%)",
                                "value": f"Total: **{trust_total:.2f}/30**\n" +
                                    f"• BS Confluence: {trust_bs_confluence:.2f}/5\n" +
                                    f"• Age/Count: {trust_age_count:.2f}/6\n" +
                                    f"• Security: {trust_security:.2f}/5\n" +
                                    f"• Activity: {trust_activity:.2f}/5\n" +
                                    f"• Social: {trust_social:.2f}/4",
                                "inline": True
                            },
                        ],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(SCORE_WEBHOOK, json=data) as response:
                    if response.status == 204:
                        print(f"Sent Score Report Alert for {token_name}")
                    else:
                        print(f"Webhook failed with status {response.status}")

        except Exception as e:
            print(f"Failed to send Score Report Webhook: {str(e)}")
    
    async def get_score_color(self, score: float) -> int:
        """Helper method to determine embed color based on score"""
        if score >= 80:
            return 0x00FF00  # Green
        elif score >= 65:
            return 0xFFFF00  # Yellow
        elif score >= 50:
            return 0xFFA500  # Orange
        else:
            return 0xFF0000  # Red

class ScoreReportWebhook:
    def __init__(self):
        pass

    async def send_score_report(self, ca, token_name, score_data):
        try:
            # Create CSV in memory
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Metric', 'Value', 'Description', 'Weight', 'Contribution'])
            
            # Write basic info
            writer.writerow(['Token Name', token_name, 'Target token name', '-', '-'])
            writer.writerow(['Contract Address', ca, 'Target contract address', '-', '-'])
            writer.writerow(['Final Score', score_data['total_score'], 'Final composite score', '-', '-'])
            writer.writerow(['-', '-', '-', '-', '-'])  # Separator
            
            metrics = score_data['metrics']
            
            # Age metrics
            writer.writerow(['Age Metrics', '-', '-', '-', '-'])
            writer.writerow(['Age (Hours)', metrics['age_hours'], 'Token age in hours', '1.5', f"{metrics['age_score'] * 1.5:.3f}"])
            writer.writerow(['Age Base Score', metrics['age_score'], 'Base age evaluation', '-', '-'])
            
            # Channel metrics
            writer.writerow(['-', '-', '-', '-', '-'])  # Separator
            writer.writerow(['Channel Metrics', '-', '-', '-', '-'])
            for channel_name, score in metrics.get('channel_scores', {}).items():
                writer.writerow([f'Channel: {channel_name}', f"{score:.3f}", 'Individual channel score', '-', '-'])
            writer.writerow(['Channel Combination Score', metrics.get('channel_combination_score', 0), 'Combined channel evaluation', '1.4', f"{metrics.get('channel_combination_score', 0) * 1.4:.3f}"])
            
            # Server activity
            writer.writerow(['-', '-', '-', '-', '-'])
            writer.writerow(['Server Activity Metrics', '-', '-', '-', '-'])
            writer.writerow(['Server Activity Score', metrics['server_activity_score'], 'Overall server activity', '1.2', f"{metrics['server_activity_score'] * 1.2:.3f}"])
            writer.writerow(['Buy/Sell Ratio', metrics['buy_sell_ratio'], 'Ratio of buys to sells', '-', '-'])
            writer.writerow(['Buy Pressure', metrics['buy_pressure'], 'Buy pressure metric', '-', '-'])
            
            # Volume & Liquidity
            writer.writerow(['-', '-', '-', '-', '-'])
            writer.writerow(['Volume & Liquidity', '-', '-', '-', '-'])
            writer.writerow(['Volume/Liquidity Score', metrics['volume_liquidity_score'], 'Volume to liquidity evaluation', '1.1', f"{metrics['volume_liquidity_score'] * 1.1:.3f}"])
            
            # Holder metrics
            writer.writerow(['-', '-', '-', '-', '-'])
            writer.writerow(['Holder Metrics', '-', '-', '-', '-'])
            writer.writerow(['Holder Metrics Score', metrics['holder_metrics_score'], 'Overall holder evaluation', '1.0', f"{metrics['holder_metrics_score']:.3f}"])
            
            # Security metrics
            writer.writerow(['-', '-', '-', '-', '-'])
            writer.writerow(['Security Metrics', '-', '-', '-', '-'])
            writer.writerow(['Security Score', metrics['security_score'], 'Security evaluation', '1.2', f"{metrics['security_score'] * 1.2:.3f}"])
            
            # Social metrics
            writer.writerow(['-', '-', '-', '-', '-'])
            writer.writerow(['Social Metrics', '-', '-', '-', '-'])
            writer.writerow(['Social Score', metrics['social_score'], 'Social presence evaluation', '0.8', f"{metrics['social_score'] * 0.8:.3f}"])
            
            # Wallet metrics if available
            if metrics.get('wallet_score'):
                writer.writerow(['-', '-', '-', '-', '-'])
                writer.writerow(['Wallet Analysis', '-', '-', '-', '-'])
                writer.writerow(['Wallet Score', metrics['wallet_score'], 'Wallet performance evaluation', '1.4', f"{metrics['wallet_score'] * 1.4:.3f}"])
                
                wallet_metrics = metrics.get('wallet_metrics', {})
                for metric_name, value in wallet_metrics.items():
                    writer.writerow([f'Wallet {metric_name}', f"{value:.3f}", f'Wallet {metric_name} metric', '-', '-'])
            
            # Channel insights
            if metrics.get('channel_insights'):
                writer.writerow(['-', '-', '-', '-', '-'])
                writer.writerow(['Channel Insights', '-', '-', '-', '-'])
                for insight_key, insight_value in metrics['channel_insights'].items():
                    writer.writerow([insight_key, insight_value, 'Channel insight', '-', '-'])

            csv_data = output.getvalue()
            output.close()

            form = aiohttp.FormData()
            form.add_field('file', 
                         csv_data,
                         filename='score_report.csv',
                         content_type='text/csv')
            form.add_field('content', 
                         f"📊 Score Report for {token_name} ({ca})\nFinal Score: {score_data['total_score']:.3f}")

            # Send webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(SCORE_WEBHOOK, data=form) as response:
                    if response.status == 204:
                        print(f"Successfully sent score report for {ca}")
                    else:
                        error_text = await response.text()
                        print(f"Failed to send score report webhook: {response.status}")
                        print(f"Error details: {error_text}")

        except Exception as e:
            print(f"Error sending score report: {str(e)}")
            import traceback
            traceback.print_exc()

class TradeWebhook:
    def __init__(self):
        self.TRADE_WEBHOOK = TRADE_WEBHOOK  # Add your webhook URL
        
    def get_profit_color(self, profit_percentage):
        if profit_percentage >= 50:
            return 0x00ff00  # Green
        elif profit_percentage > 0:
            return 0xffff00  # Yellow
        else:
            return 0xff0000  # Red
            
    async def send_trade_result(
        self,
        token_name: str,
        ca: str,
        entry_mc: float,
        exit_mc: float,
        profit_percentage: float,
        trade_duration: str,
        reason: str
    ):
        try:
            data = {
                "embeds": [
                    {
                        "title": f"Trade Result for {token_name}",
                        "description": f"Contract: `{ca}`",
                        "color": self.get_profit_color(profit_percentage),
                        "fields": [
                            {
                                "name": "💰 Trade Summary",
                                "value": f"**Profit/Loss: {profit_percentage:.2f}%**\nDuration: {trade_duration}",
                                "inline": False
                            },
                            {
                                "name": "📊 Entry/Exit Details",
                                "value": f"Entry MC: ${entry_mc:,.2f}\nExit MC: ${exit_mc:,.2f}",
                                "inline": True
                            },
                            {
                                "name": "📝 Exit Reason",
                                "value": reason,
                                "inline": True
                            }
                        ],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                ]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.TRADE_WEBHOOK, json=data) as response:
                    if response.status == 204:
                        print(f"Sent Trade Result Alert for {token_name}")
                    else:
                        print(f"Trade webhook failed with status {response.status}")

        except Exception as e:
            print(f"Failed to send Trade Result Webhook: {str(e)}")

    async def send_trade_webhook(self, webhook_url, result, new_metrics, new_buyers_with_pnl):
        """
        Format and send trade data to Discord webhook
        """
        try:
            print(f"Attempting to send webhook to {webhook_url}")
            
            # Calculate total buys and sells
            total_buys = result['metrics']['buy_metrics']['count']
            total_sells = result['metrics']['sell_metrics']['count']
            total_buy_sol = result['metrics']['buy_metrics']['total_sol']
            total_sell_sol = result['metrics']['sell_metrics']['total_sol']
            
            # Build message with proper formatting
            message = [
                "🚨 **Trade Scanner Alert** 🚨",
                f"**Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                "",
                "📊 **Current Statistics**",
                f"• Total Trades: `{result['metrics']['total_trades']}`",
                f"• Net SOL Flow: `{result['metrics']['sol_net_flow']:.2f} SOL`",
                f"• New Trades: `{new_metrics['total_trades']}`",
                f"• Total Buys: `{total_buys}` ({total_buy_sol:.2f} SOL)",
                f"• Total Sells: `{total_sells}` ({total_sell_sol:.2f} SOL)",
                ""
            ]

            # Add large buys section if any
            if new_metrics['large_buys'] > 0 and new_buyers_with_pnl:
                message.append("🔵 **New Large Buys**")
                for buy_data in new_buyers_with_pnl:
                    buy_info = [
                        f"• Wallet: `{buy_data['wallet'][:8]}...`",
                        f"  Amount: `{buy_data['amount_sol']:.2f} SOL (${buy_data['amount_usd']:.2f})`"
                    ]
                    
                    if 'pnl_data' in buy_data and buy_data['pnl_data']:
                        pnl = buy_data['pnl_data']
                        buy_info.extend([
                            f"  PNL: `{pnl['last_100_tx_pnl']:.2f} SOL`",
                            f"  W/L: `{pnl['trades_won']}/{pnl['trades_loss']}`",
                            f"  Tokens Traded: `{pnl['tokens_traded']}`",
                            f"  Avg Entry: `{pnl['average_entry_per_trade']:.2f} SOL`",
                            ""
                        ])
                    message.extend(buy_info)
            else:
                message.append("🔵 No large buys detected")
                message.append("")

            # Add large sells section if any
            if new_metrics['large_sells'] > 0:
                message.append("🔴 **New Large Sells**")
                for sell in result['wallet_analysis']['large_trades']['large_sellers'][-new_metrics['large_sells']:]:
                    message.extend([
                        f"• Wallet: `{sell['wallet'][:8]}...`",
                        f"  Amount: `{sell['amount_sol']:.2f} SOL (${sell['amount_usd']:.2f})`",
                        ""
                    ])
            else:
                message.append("🔴 No large sells detected")
                message.append("")

            # Add top 5 buyers section
            if result['wallet_analysis'].get('top_5_buyers'):
                message.append("📊 **Top 5 Buyers**")
                for buy in result['wallet_analysis']['top_5_buyers']:
                    message.extend([
                        f"• Wallet: `{buy['wallet'][:8]}...`",
                        f"  Total Amount: `{buy['buy_sol']:.2f} SOL (${buy['buy_usd']:.2f})`"
                    ])
                    
                    # Add holding status if available
                    if result.get('top_buyers_analysis'):
                        buyer_analysis = next((b for b in result['top_buyers_analysis'] if b['wallet'] == buy['wallet']), None)
                        if buyer_analysis:
                            status = buyer_analysis['status']
                            current_holding = buyer_analysis['current_holding']
                            current_value = buyer_analysis['current_value_usd']
                            message.append(f"  Status: `{status}` | Current Holdings: `${current_value:.2f}`")
                    message.append("")  # Add empty line after each wallet

            # Join all parts with newlines
            formatted_message = "\n".join(message)
            
            # Print formatted message for debugging
            print("Formatted webhook message:")
            print(formatted_message)

            # Send webhook
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(webhook_url, json={"content": formatted_message}) as response:
                        if response.status == 204:
                            print("Successfully sent webhook")
                            return True
                        else:
                            response_text = await response.text()
                            print(f"Webhook failed with status {response.status}")
                            print(f"Response: {response_text}")
                            return False
                except Exception as post_error:
                    print(f"Error posting webhook: {str(post_error)}")
                    return False

        except Exception as e:
            print(f"Error preparing webhook: {str(e)}")
            import traceback
            traceback.print_exc()
            return False