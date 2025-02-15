# webhooks.py
import asyncio
import aiohttp
from env import ALEF_ALERT_WEBHOOK
import discord
from alefalerts import MessageSender 
from env import MULTIALERT_WEBHOOK, SCORE_WEBHOOK, TWOX_WEBHOOK, SOL_10_5_WEBHOOK
import csv
import io

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

    async def multialert_webhook(self, token_name, ca, marketcap, liquidity, telegram, twitter, photon_link, bull_x_link, dex_link, swt_count, swt_buys, swt_sells, fresh_count, fresh_buys, fresh_sells, last_3_tx, holder_count, dev_holding_percentage, token_migrated, passes_soulscanner, passes_bundlebot, dex_paid, token_age, top_10_holding_percentage, holders_over_5, wallet_data, m30_vol, m30_vol_change, new_unique_wallets_30m, new_unique_wallet_30m_change, trade_change_30m, buy_change_30m, sell_change_30m, channel_text, sniper_percent):
        try:
            #place holders
            new_unique_wallet_30m_change = new_unique_wallet_30m_change or 0
            trade_change_30m = trade_change_30m or 0
            buy_change_30m = buy_change_30m or 0
            sell_change_30m = sell_change_30m or 0
            m30_vol = m30_vol or 0
            m30_vol_change = m30_vol_change or 0
            uniqueplaceholder = "Increase" if new_unique_wallet_30m_change > 0 else "Decrease"
            tradeplaceholder = "Increase" if trade_change_30m > 0 else "Decrease"
            buyplaceholder = "Increase" if buy_change_30m > 0 else "Decrease"
            sellplaceholder = "Increase" if sell_change_30m > 0 else "Decrease"
            sniperplaceholder = "❌" if sniper_percent >= 45 else "✅"

            embed = {
                "title": "🚨 Multi Ape Alert",
                "color": 0x00ff00,
                "fields": [
                    {
                        "name": f"{token_name}",
                        "value": (
                            f"CA: `{ca}`\n"
                            f"💰 Marketcap: ${marketcap:,.2f}\n"
                            f"💧 Liquidity: ${liquidity:,.2f}\n"
                            #f"📊 5m Volume: ${m5_vol:,.2f}\n"
                            f"📊 30m Volume: ${m30_vol:,.2f} -- Change of: {m30_vol_change:.2f}%\n"
                            f" Total Trades have {tradeplaceholder}d by {trade_change_30m:.2f}% in the last 30 min\n"
                            f" Buys have {buyplaceholder}d by {buy_change_30m:.2f} in the last 30 min \n"
                            f" Sells have {sellplaceholder}d by {sell_change_30m:.2f} in the last 30 min\n"
                            f"⏰ Age: {token_age['value']} {token_age['unit']}\n" 
                        ),
                        "inline": False
                    },
                    {
                        "name": "🔍 Server Activity",
                        "value": (
                            f"SWT Activity: ca has {swt_count} mentions ({swt_buys:.2f} SOL Buys, {swt_sells:.2f} SOL sells)\n"
                            f"Fresh Activity: ca has {fresh_count} mentions ({fresh_buys:.2f} buys, {fresh_sells:.2f} sells)\n"
                        ),
                        "inline": False
                    },
                    {
                        "name": f"{token_name} aped by wallets in:",
                        "value": f"{channel_text}",
                        "inline": False
                    },
                    {
                        "name": "📊 Holder Analysis",
                        "value": (
                            f"👥 Total Holders: {holder_count}\n"
                            f"📊 Top 10 Hold: {top_10_holding_percentage:.2f}%\n"
                            f"⚠️ Holders >5%: {holders_over_5}\n"
                            f"👨‍💼 Dev Holding: {dev_holding_percentage:.2f}%\n"
                            f" {new_unique_wallets_30m} New Unique Wallets in 30min. {uniqueplaceholder} of {new_unique_wallet_30m_change}%"
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
                        f"**Wallet {wallet_address[:8]}**...\n"
                        f"💰 Holding: {data['holding_percentage']:.2f}%\n"
                        f"📈 PNL: {data['pnl']:.4f} SOL\n"
                        f"🎯 Tokens Traded: {data['tokens_traded']}\n"
                        f"✅ Wins: {data['wins']}\n"
                        f"❌ Losses: {data['losses']}\n"
                        f"{'─' * 20}\n"
                    )
                if wallet_analysis:
                    embed["fields"].append({
                        "name": "Top Wallet Recent Trade Report",
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