import discord, json, os, random, threading, requests
from discord.ext import commands
from flask import Flask, request

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- CONFIG ----------------
with open("config.json") as f:
    config = json.load(f)

BOT_TOKEN = os.getenv("TOKEN")
COINBASE_API = os.getenv("COINBASE_API")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

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
vouches = load_data("data/vouches.json")

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

# ---------------- COINBASE PAYMENT ----------------
def create_charge(product, price, user_id):
    url = "https://api.commerce.coinbase.com/charges"
    headers = {"X-CC-Api-Key": COINBASE_API, "Content-Type": "application/json"}
    data = {
        "name": product,
        "description": f"Purchase by {user_id}",
        "pricing_type": "fixed_price",
        "local_price": {"amount": str(price), "currency": "USD"},
        "metadata": {"user_id": str(user_id), "product": product}
    }
    res = requests.post(url, json=data, headers=headers)
    return res.json()["data"]["hosted_url"]

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
    embed.set_image(url="YOUR_ANIMATED_GIF_URL")
    view = discord.ui.View()
    async def open_ticket(i):
        guild = i.guild
        category = discord.utils.get(guild.categories, name="TICKETS")
        if category is None:
            category = await guild.create_category("TICKETS")
        channel = await guild.create_text_channel(name=f"ticket-{i.user.name}", category=category)
        await channel.set_permissions(i.user, read_messages=True, send_messages=True)
        await send_buy_panel(channel)
        await i.response.send_message("✅ Ticket created", ephemeral=True)
    btn = discord.ui.Button(label="Open Ticket", style=discord.ButtonStyle.green)
    btn.callback = open_ticket
    view.add_item(btn)
    await interaction.response.send_message(embed=embed, view=view)

# ---------------- BUY PANEL ----------------
async def send_buy_panel(channel):
    embed = discord.Embed(title="⚡ Auto Buy System", description="Select product below to buy", color=0x0ff0fc)
    embed.set_image(url="https://media.discordapp.net/attachments/1401055310512259235/1454885879066792207/offer.gif?ex=69ba3550&is=69b8e3d0&hm=bd2c4d97ae0e5754a3a55f5b1a47f6d4fbbaf55711317b6bf0498adb6743a490&width=540&height=216&")
    view = ProductView()
    await channel.send(embed=embed, view=view)

# ---------------- PRODUCT VIEW ----------------
class ProductView(discord.ui.View):
    def __init__(self):
        super().__init__()
        select = discord.ui.Select(placeholder="Select product", options=[discord.SelectOption(label=p) for p in prices.keys()])
        async def callback(interaction):
            product = select.values[0]
            price = prices[product]
            payment_link = create_charge(product, price, interaction.user.id)
            embed = discord.Embed(title="💳 Payment Info", description=f"{product} - ${price}\nPay here:\n{payment_link}", color=0x0ff0fc)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        select.callback = callback
        self.add_item(select)

# ---------------- VOUCH ×CD ----------------
@bot.tree.command(name="vouch")
async def vouch(interaction: discord.Interaction, user: discord.Member, amount: int = 1):
    uid = str(user.id)
    vouches.setdefault(uid, 0)
    vouches[uid] += amount
    save_data("data/vouches.json", vouches)
    await interaction.response.send_message(f"✅ Added {amount} ×cd for {user}", ephemeral=True)

# ---------------- STOCK ----------------
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

# ---------------- FLASK WEBHOOK ----------------
app = Flask(__name__)
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    event = data["event"]["type"]
    if event == "charge:confirmed":
        metadata = data["event"]["data"]["metadata"]
        user_id = int(metadata["user_id"])
        product = metadata["product"]
        user = bot.get_user(user_id)
        item = get_stock(product)
        if item and user:
            bot.loop.create_task(user.send(f"✅ Payment confirmed!\nYour item:\n{item}"))
            # PROOF CHANNEL
            ch = bot.get_channel(config["proof_channel"])
            proof = discord.Embed(title="📦 New Proof", description=f"User: {user.mention}\nProduct: {product}\nStatus: Delivered ✅\nPayment: Crypto\nOrder ID: {random.randint(1000,9999)}", color=0x00ff99)
            proof.set_image(url="https://media.discordapp.net/attachments/1401055310512259235/1454885879066792207/offer.gif")
            bot.loop.create_task(ch.send(embed=proof))
    return "ok"

def run_web():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_web).start()
bot.run(BOT_TOKEN)
