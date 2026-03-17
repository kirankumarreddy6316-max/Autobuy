import discord, json, os, random, requests, asyncio
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
from flask import Flask, request
from threading import Thread

# === Load sensitive keys from environment variables ===
TOKEN = os.getenv("DISCORD_TOKEN")
NOW_API_KEY = os.getenv("NOW_API_KEY")

# === Intents & bot setup ===
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# === Load config & credits ===
with open("config.json") as f:
    config = json.load(f)

def load_data(path):
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)

def save_data(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=4)

credits = load_data("data/credits.json")

# === Stock functions ===
def count_stock(file):
    try:
        with open(file) as f:
            return len(f.readlines())
    except:
        return 0

def get_stock_item(file):
    try:
        with open(file) as f:
            lines = f.readlines()
        if not lines:
            return "Out of Stock"
        item = lines[0]
        with open(file, "w") as f:
            f.writelines(lines[1:])
        return item.strip()
    except:
        return "Out of Stock"

# === Ready event ===
@bot.event
async def on_ready():
    await bot.tree.sync()
    print("Bot Ready")

# === /stock command ===
@bot.tree.command(name="stock")
async def stock(interaction: discord.Interaction):
    embed = discord.Embed(title="📦 Stock Status", color=0x00ff99)
    embed.add_field(
        name="Accounts",
        value=f"Netflix: {count_stock('stock/netflix.txt')}\nSpotify: {count_stock('stock/spotify.txt')}\nCanva: {count_stock('stock/canva.txt')}\nChatGPT: {count_stock('stock/chatgpt.txt')}",
        inline=False
    )
    embed.add_field(
        name="Digital",
        value=f"Robux: {config['robux_stock']}\nBoosts: {config['boost_stock']}",
        inline=False
    )
    embed.add_field(
        name="Services",
        value="Nitro Gen: ∞\nToken Gen: ∞\nCC Gen: ∞\nPayPal Gen: ∞",
        inline=False
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

# === /credits command ===
@bot.tree.command(name="credits")
async def credits_cmd(interaction: discord.Interaction):
    user = str(interaction.user.id)
    user_data = credits.get(user, {"online":0,"offline":0})
    embed = discord.Embed(title="💳 Your Credits", color=0x3498db)
    embed.add_field(name="Online", value=f"{user_data['online']}k")
    embed.add_field(name="Offline", value=f"{user_data['offline']}k")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# === /panel command ===
@bot.tree.command(name="panel")
async def panel(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("No permission", ephemeral=True)

    embed = discord.Embed(
        title="🛒 AutoBuy Shop",
        description="Fast • Secure • Automated",
        color=0x5865F2
    )
    embed.set_image(url=config["animated_gif_url"])

    view = View()

    async def buy_callback(i):
        await i.response.send_message("Select product (system continues…)", ephemeral=True)

    btn = Button(label="Buy", style=discord.ButtonStyle.green)
    btn.callback = buy_callback
    view.add_item(btn)

    await interaction.response.send_message(embed=embed, view=view)

# === Delivery function ===
async def deliver_product(user, product, stock_file=None):
    if stock_file:
        item = get_stock_item(stock_file)
    else:
        item = "Unlimited / Auto-generated item"

    embed = discord.Embed(title=f"✅ {product} Delivered", color=0x2ecc71)
    embed.add_field(name="Details", value=item, inline=False)
    embed.set_image(url=config["proof_gif_url"])

    await user.send(embed=embed)

# === Robux stock update ===
def remove_robux(amount):
    config["robux_stock"] -= amount
    with open("config.json", "w") as f:
        json.dump(config, f, indent=4)

# === Credits update ===
def add_credit(user, amount, type_):
    user = str(user)
    if user not in credits:
        credits[user] = {"online":0,"offline":0}
    credits[user][type_] += amount
    save_data("data/credits.json", credits)

# === NOWPayments create invoice ===
def create_nowpayment_charge(product, price, buyer_id):
    url = "https://api.nowpayments.io/v1/invoice"
    headers = {"x-api-key": NOW_API_KEY, "Content-Type":"application/json"}
    data = {
        "price_amount": price,
        "price_currency": "usd",
        "pay_currency": config["payment_currency"],
        "order_id": str(random.randint(1000,9999)),
        "order_description": f"{product} purchase by {buyer_id}",
        "ipn_callback_url": "https://autobuy-production.up.railway.app/webhook"
    }
    res = requests.post(url, json=data, headers=headers)
    return res.json()["invoice_url"]

# === Flask webhook ===
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json

    if data.get("payment_status") == "finished":
        user_id = int(data["order_description"].split()[-1])
        product = data["order_description"].split()[0]

        stock_file = None
        if product.lower() == "netflix":
            stock_file = "stock/netflix.txt"
        elif product.lower() == "spotify":
            stock_file = "stock/spotify.txt"
        elif product.lower() == "canva":
            stock_file = "stock/canva.txt"
        elif product.lower() == "chatgpt":
            stock_file = "stock/chatgpt.txt"

        # ✅ FIXED (IMPORTANT)
        user = asyncio.run(bot.fetch_user(user_id))
        asyncio.run(deliver_product(user, product, stock_file))

    return "OK"

# === Run Flask ===
def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

Thread(target=run_flask).start()

# === Run bot ===
bot.run(TOKEN)
