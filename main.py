import discord, json, os, random
from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- CONFIG ----------------
with open("config.json") as f:
    config = json.load(f)

# Load sensitive info from env variables
BOT_TOKEN = os.getenv("TOKEN")
LTC_ADDRESS = os.getenv("LTC_ADDRESS")

# ---------------- DATA ----------------
def load_data(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)

def save_data(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

credits = load_data("data/credits.json")
vouches = load_data("data/vouches.json")  # track ×cd

# ---------------- PRICES ----------------
prices = {
    "Netflix": 3,
    "Spotify": 2.5,
    "Canva": 5,
    "ChatGPT": 9,
    "Auto Advertise 1M": 3,
    "Auto Advertise 1M Reply": 5,
    "Auto Advertise Lifetime": 8,
    "Nitro Gen": 8,
    "Nitro Boosts 1M": 3,
    "Nitro Boosts 3M": 6,
    "Custom Bots": 5,
    "Self Bots": 5,
    "Token Gen": 5,
    "USDT Flasher": 5,
    "Auto Chat": 0.2,
    "Auto Vouch": 0.3,
    "Members": 1,
    "Robux": 5,
    "CC Gen": 5,
    "PayPal Gen": 5
}

# ---------------- STOCK ----------------
def get_stock(file):
    path = f"stock/{file.lower()}.txt"
    if not os.path.exists(path):
        return None
    with open(path) as f:
        lines = f.readlines()
    if not lines:
        return None
    item = lines[0]
    with open(path, "w") as f:
        f.writelines(lines[1:])
    return item.strip()

def count_stock(file):
    path = f"stock/{file.lower()}.txt"
    if not os.path.exists(path):
        return 0
    with open(path) as f:
        return len(f.readlines())

# ---------------- READY ----------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print("Bot Ready")

# ---------------- PANEL ----------------
@bot.tree.command(name="panel")
async def panel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("No permission", ephemeral=True)

    embed = discord.Embed(
        title="⚡ Auto Buy System",
        description="Click below to open ticket & start purchase",
        color=0x0ff0fc
    )
    embed.set_image(url="YOUR_AUTOBUY_GIF_URL")
    view = discord.ui.View()

    async def open_ticket(i):
        guild = i.guild
        category = discord.utils.get(guild.categories, name="TICKETS")
        channel = await guild.create_text_channel(
            name=f"ticket-{i.user.name}",
            category=category
        )
        await channel.set_permissions(i.user, read_messages=True, send_messages=True)
        await channel.send(i.user.mention)
        await send_buy_panel(channel)
        await i.response.send_message("✅ Ticket created", ephemeral=True)

    btn = discord.ui.Button(label="Open Ticket", style=discord.ButtonStyle.green)
    btn.callback = open_ticket
    view.add_item(btn)
    await interaction.response.send_message(embed=embed, view=view)

# ---------------- BUY PANEL ----------------
async def send_buy_panel(channel):
    embed = discord.Embed(
        title="⚡ Auto Buy System",
        description="Select product below to buy",
        color=0x0ff0fc
    )
    embed.set_image(url="YOUR_AUTOBUY_GIF_URL")
    view = ProductView()
    await channel.send(embed=embed, view=view)

# ---------------- PRODUCT VIEW ----------------
class ProductView(discord.ui.View):
    def __init__(self):
        super().__init__()
        select = discord.ui.Select(
            placeholder="Select product",
            options=[discord.SelectOption(label=p) for p in prices.keys()]
        )

        async def callback(interaction):
            product = select.values[0]
            price = prices[product]

            embed = discord.Embed(
                title="💳 Payment Info",
                description=f"{product} - ${price}\nClick button for LTC details",
                color=0x0ff0fc
            )
            view = discord.ui.View()

            async def pay(i):
                await i.response.send_message(
                    f"LTC Address: {LTC_ADDRESS}\nAmount: ${price}",
                    ephemeral=True
                )

            pay_btn = discord.ui.Button(label="Paste Details", style=discord.ButtonStyle.blurple)
            pay_btn.callback = pay

            async def confirm(i):
                item = get_stock(product)
                if not item:
                    return await i.response.send_message("❌ Out of stock", ephemeral=True)

                # DELIVERY DM
                embed2 = discord.Embed(title="✅ Delivered", color=0x00ff99)
                embed2.add_field(name="Account", value=item)
                await i.user.send(embed=embed2)

                # AUTO ADV ROLE
                if "Auto Advertise" in product:
                    role = i.guild.get_role(config["auto_adv_role"])
                    await i.user.add_roles(role)

                # PROOF
                ch = bot.get_channel(config["proof_channel"])
                proof = discord.Embed(
                    title="📦 New Proof",
                    description=f"User: {i.user.mention}\nProduct: {product}\nStatus: Delivered ✅\nPayment: LTC\nOrder ID: {random.randint(1000,9999)}",
                    color=0x00ff99
                )
                proof.set_image(url="https://media.discordapp.net/attachments/1401055310512259235/1454885879066792207/offer.gif")
                await ch.send(embed=proof)

                # LOGS
                log_ch = bot.get_channel(config.get("auto_adv_channel"))
                if log_ch:
                    await log_ch.send(f"{i.user} bought {product} for ${price}")

                # ADD CREDITS
                user = str(i.user.id)
                if "Members" in product:
                    credits.setdefault(user, {"online":0,"offline":0})
                    credits[user]["offline"] += int(price)  # Example
                    save_data("data/credits.json", credits)

                await i.response.send_message("✅ Delivered check DM", ephemeral=True)

            confirm_btn = discord.ui.Button(label="I Paid", style=discord.ButtonStyle.green)
            confirm_btn.callback = confirm
            view.add_item(pay_btn)
            view.add_item(confirm_btn)

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        select.callback = callback
        self.add_item(select)

# ---------------- VOUCH ×CD ----------------
@bot.tree.command(name="vouch")
async def vouch(interaction: discord.Interaction, user: discord.Member, amount: int = 1):
    """Add ×cd vouch for user"""
    uid = str(user.id)
    vouches.setdefault(uid, 0)
    vouches[uid] += amount
    save_data("data/vouches.json", vouches)
    await interaction.response.send_message(f"✅ Added {amount} ×cd for {user}", ephemeral=True)

# ---------------- STOCK COMMAND ----------------
@bot.tree.command(name="stock")
async def stock_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📦 Stock Status", color=0x00ff99)
    for p in ["Netflix","Spotify","Canva","ChatGPT"]:
        embed.add_field(name=p, value=count_stock(p), inline=False)
    embed.add_field(name="Digital", value=f"Robux: {config['robux_stock']}\nBoosts: {config['boost_stock']}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------------- CREDITS ----------------
@bot.tree.command(name="credits")
async def credits_cmd(interaction: discord.Interaction):
    user = str(interaction.user.id)
    data = credits.get(user, {"online":0,"offline":0})
    embed = discord.Embed(title="💳 Your Credits", color=0x3498db)
    embed.add_field(name="Online", value=data["online"])
    embed.add_field(name="Offline", value=data["offline"])
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------------- RUN ----------------
bot.run(BOT_TOKEN)
