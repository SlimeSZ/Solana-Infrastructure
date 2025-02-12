import asyncio
import discord
from discord.ext import commands
from process_descriptions import TX_ANALYZER
from env import DISCORD_BOT_TOKEN

intents = discord.Intents.all()
intents.message_content = True
intents.guild_messages = True

bot = commands.Bot(command_prefix='!', intents=intents)

class ServerData:
    def __init__(self, bot):
        self.bot = bot
        self.tx = TX_ANALYZER()
        self.target_ca = None
        #server counts
        self.swt_count = 0
        self.degen_count = 0
        self.fresh_count = 0
        #buy sell data
        self.swt_buy_amount = 0
        self.swt_sell_amount = 0
        self.degen_buy_amount = 0
        self.degen_sell_amount = 0
        self.fresh_buy_amount = 0
        self.fresh_sell_amount = 0
        
        

    def reset_counts(self):
        self.swt_count = 0
        self.degen_count = 0
        self.fresh_count = 0
        self.swt_buy_amount = 0
        self.swt_sell_amount = 0
        self.degen_buy_amount = 0
        self.degen_sell_amount = 0
        self.fresh_buy_amount = 0
        self.fresh_sell_amount = 0
        
    async def swt_server_data(self):
        if not self.target_ca:
            return
        server_data = {
            'count': 0,
            'buys': 0.0,
            'sells': 0.0,
            'channels': {},
            'latest_descriptions': []
        }
        for channel_id in self.swt_channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    channel_buys = 0.0
                    channel_sells = 0.0
                    channel_count = 0
                    async for message in channel.history(limit=500):
                        if message.embeds:
                            for embed in message.embeds:
                                if embed.fields:
                                    excluded_fields = ['sol:', 'useful links:', 'buy with bonkbot:']
                                    for field in embed.fields:
                                        if field.name.lower() not in excluded_fields:
                                            ca = field.value
                                            if ca.lower() == self.target_ca.lower():
                                                channel_count += 1
                                                if embed.description:
                                                    server_data['latest_descriptions'].append(embed.description)
                                                tx_data = await self.tx.extract_buys_sells(embed.description)
                                                if tx_data:
                                                    type = tx_data['type']
                                                    sol_amount = tx_data['sol_amount']
                                                    if type == "Buy":
                                                        channel_buys += sol_amount
                                                    else:
                                                        channel_sells += sol_amount
                    server_data['count'] += channel_count
                    server_data['buys'] += channel_buys
                    server_data['sells'] += channel_sells

                    server_data['channels'][channel.name] = {
                        'count': channel_count,
                        'buys': channel_buys,
                        'sells': channel_sells
                    }

                    print(f"Channel: {channel.name}")
                    print(f"Count: {channel_count}")
                    print(f"Buys: {channel_buys}")
                    print(f"Sells: {channel_sells}")
                    
                except Exception as e:
                    print(f"Error counting SWT messages in {channel.name}: {e}")
                
                await asyncio.sleep(1)
        
        server_data['latest_descriptions'] = server_data['latest_descriptions'][-5:] if server_data['latest_descriptions'] else []
        return server_data
                                        #print(f"{field.name} ---n--- {field.value}")

    async def degen_server_data(self):
        if not self.target_ca:
            return
        
        server_data = {
            'count': 0,
            'buys': 0.0,
            'sells': 0.0,
            'channels': {},
            'latest_descriptions': []
        }
        print(f"\nCounting Degen messages for CA: {self.target_ca}")
        
        channel = self.bot.get_channel(self.degen_channel_id)
        if channel:
            try:
                channel_buys = 0.0
                channel_sells = 0.0
                channel_count = 0
                async for message in channel.history(limit=500):
                    if message.embeds:
                        for embed in message.embeds:
                            if embed.fields:
                                # First verify if this embed is for our target CA
                                current_ca = None
                                is_target_tx = False
                                
                                # Check for CA first
                                for field in embed.fields:
                                    if "Token:" in field.value:
                                        try:
                                            current_ca = field.value.split('`')[1].strip()
                                            if current_ca.lower() == self.target_ca.lower():
                                                is_target_tx = True
                                                channel_count += 1
                                                print(f"\nFound target CA: {current_ca}")
                                                break
                                        except Exception as e:
                                            print(f"Error extracting CA: {e}")
                                            continue
                                
                                # Only process transaction if this is our target CA
                                if is_target_tx:
                                    for field in embed.fields:
                                        if field.value and ("swapped" in field.value.lower() or "transferred" in field.value.lower()):
                                            tx_desc = field.value
                                            if tx_desc:
                                                server_data['latest_descriptions'].append(tx_desc)
                                                print(f"Processing tx: {tx_desc}")
                                            
                                            tx_data = await self.tx.extract_degen_buys_sells(tx_desc)
                                            if tx_data:
                                                tx_type = tx_data['type']
                                                sol_amount = tx_data['sol_amount']
                                                
                                                if tx_type == "Buy":
                                                    channel_buys += sol_amount
                                                    print(f"Added Buy: {sol_amount} SOL")
                                                elif tx_type == "Sell":
                                                    channel_sells += sol_amount
                                                    print(f"Added Sell: {sol_amount} SOL")

                print("\nFinal Stats:")
                print(f"Total Count: {channel_count}")
                print(f"Total Buys: {channel_buys} SOL")
                print(f"Total Sells: {channel_sells} SOL")
                
                server_data['count'] = channel_count
                server_data['buys'] = channel_buys
                server_data['sells'] = channel_sells
                server_data['channels']["Degen"] = {
                    'count': channel_count,
                    'buys': channel_buys,
                    'sells': channel_sells
                }
                                            
            except Exception as e:
                print(f"Error in degen processing: {str(e)}")
                import traceback
                print(traceback.format_exc())
        
        server_data['latest_descriptions'] = server_data['latest_descriptions'][-5:] if server_data['latest_descriptions'] else []
        return server_data

        
    async def fresh_server_data(self):
        if not self.target_ca:
            return
        server_data = {
            'count': 0,
            'buys': 0.0,
            'sells': 0.0,
            'channels': {},
            'latest_descriptions': []
        }
            
        print(f"\nCounting Fresh messages for CA: {self.target_ca}")
        
        for channel_id in self.fresh_channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    channel_buys = 0.0
                    channel_sells = 0.0
                    channel_count = 0
                    async for message in channel.history(limit=500):
                        if message.embeds:
                            for embed in message.embeds:
                                if embed.fields:
                                    for field in embed.fields:
                                        if field.name.strip(':').lower() == "token address":
                                            ca = field.value.strip()
                                            if ca.lower() == self.target_ca.lower():
                                                channel_count += 1
                                                if embed.description:
                                                    server_data['latest_descriptions'].append(embed.description)
                                                tx_data = await self.tx.extract_buys_sells(embed.description)
                                                if tx_data:
                                                    tx_type = tx_data['type']
                                                    sol_amount = tx_data['sol_amount']
                                                    if tx_type == "Buy":
                                                        channel_buys += sol_amount
                                                    else:
                                                        channel_sells += sol_amount
                    server_data['count'] += channel_count
                    server_data['buys'] += channel_buys
                    server_data['sells'] += channel_sells

                    server_data['channels'][channel.name] = {
                        'count': channel_count,
                        'buys': channel_buys,
                        'sells': channel_sells
                    }
                    

                    
                    print(f"Channel: {channel.name}")
                    print(f"Final Buys: {channel_buys}")
                    print(f"Final Sells: {channel_sells}")
                    print(F"Final Count: {channel_count}")
                    
                except Exception as e:
                    print(f"Error counting Fresh messages in {channel.name}: {e}")
                
                await asyncio.sleep(1)
        server_data['latest_descriptions'] = server_data['latest_descriptions'][-5:] if server_data['latest_descriptions'] else []
        return server_data

@bot.event
async def on_ready():
    print(f"Bot is ready as {bot.user}")
    server_count = ServerData(bot)
    # Set the target CA first
    server_count.target_ca = "HiEmDV1ots8X3XoN6mhEN5fNZPa6BxKdxfvkXFFEDakQ"
    # Then call the method
    swt_data = await server_count.fresh_server_data()
    if swt_data:
        last_five = swt_data['latest_descriptions']
        for tx in last_five:
            print(tx)
    
bot.run('')  # Replace with your bot token
