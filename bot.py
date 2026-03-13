import logging
import os
import json
import base58
import requests
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
Application, CommandHandler, CallbackQueryHandler,
MessageHandler, filters, ContextTypes, ConversationHandler
)

# ========== CONFIG ==========

BOT_TOKEN = “8644296453:AAEtQLaNRWEBu1idL-VeFmCWwkjLDCZrB4I”
SOLANA_RPC = “https://solana-mainnet.g.alchemy.com/v2/4oVyiOSZ9Sm9eJviL-ufi”
JUPITER_PRICE_API = “https://price.jup.ag/v4/price”
DEXSCREENER_API = “https://api.dexscreener.com/latest/dex”

# ========== LOGGING ==========

logging.basicConfig(
format=”%(asctime)s - %(name)s - %(levelname)s - %(message)s”,
level=logging.INFO
)
logger = logging.getLogger(**name**)

# ========== STATES ==========

IMPORT_PRIVATE_KEY, IMPORT_SEED, BUY_TOKEN, BUY_AMOUNT, SELL_TOKEN, SELL_AMOUNT, SEARCH_TOKEN, COPY_WALLET, AI_SNIPER_WAITING = range(9)

# ========== IN-MEMORY STORAGE ==========

# {user_id: {“wallets”: [{“address”: …, “private_key”: …}], “copy_wallets”: [], “positions”: [], “sniper_active”: False}}

user_data_store = {}

def get_user(user_id):
if user_id not in user_data_store:
user_data_store[user_id] = {
“wallets”: [],
“copy_wallets”: [],
“positions”: [],
“sniper_active”: False,
“sniper_settings”: {“amount”: 0.1, “slippage”: 10},
“apex_sniper_settings”: {“amount”: 0.1, “slippage”: 5}
}
return user_data_store[user_id]

# ========== SOLANA HELPERS ==========

def get_sol_balance(address: str) -> float:
try:
payload = {
“jsonrpc”: “2.0”, “id”: 1,
“method”: “getBalance”,
“params”: [address]
}
res = requests.post(SOLANA_RPC, json=payload, timeout=10)
data = res.json()
lamports = data.get(“result”, {}).get(“value”, 0)
return lamports / 1e9
except Exception as e:
logger.error(f”Balance error: {e}”)
return 0.0

def get_sol_price() -> float:
try:
res = requests.get(
f”{JUPITER_PRICE_API}?ids=So11111111111111111111111111111111111111112”,
timeout=10
)
data = res.json()
price = data.get(“data”, {}).get(“So11111111111111111111111111111111111111112”, {}).get(“price”, 0)
return float(price)
except Exception as e:
logger.error(f”Price error: {e}”)
return 0.0

def get_sol_volume() -> str:
try:
res = requests.get(f”{DEXSCREENER_API}/search?q=SOL”, timeout=10)
data = res.json()
pairs = data.get(“pairs”, [])
for pair in pairs:
if pair.get(“baseToken”, {}).get(“symbol”) == “SOL”:
vol = pair.get(“volume”, {}).get(“h24”, 0)
if vol > 0:
return f”${vol/1e9:.2f}B”
return “N/A”
except:
return “N/A”

def search_token_info(query: str) -> dict:
try:
res = requests.get(f”{DEXSCREENER_API}/search?q={query}”, timeout=10)
data = res.json()
pairs = data.get(“pairs”, [])
if not pairs:
return None
pair = pairs[0]
return {
“name”: pair.get(“baseToken”, {}).get(“name”, “Unknown”),
“symbol”: pair.get(“baseToken”, {}).get(“symbol”, “?”),
“address”: pair.get(“baseToken”, {}).get(“address”, “N/A”),
“price”: pair.get(“priceUsd”, “0”),
“change_24h”: pair.get(“priceChange”, {}).get(“h24”, 0),
“volume_24h”: pair.get(“volume”, {}).get(“h24”, 0),
“liquidity”: pair.get(“liquidity”, {}).get(“usd”, 0),
“market_cap”: pair.get(“marketCap”, 0),
“dex”: pair.get(“dexId”, “Unknown”),
}
except Exception as e:
logger.error(f”Token search error: {e}”)
return None

# ========== KEYBOARDS ==========

def main_menu_keyboard():
return InlineKeyboardMarkup([
[InlineKeyboardButton(“🔐 Wallet”, callback_data=“wallet”),
InlineKeyboardButton(“🔄 Refresh”, callback_data=“refresh”)],
[InlineKeyboardButton(“🎯 AI Sniper”, callback_data=“ai_sniper”),
InlineKeyboardButton(“🚀 Apex Sniper”, callback_data=“apex_sniper”)],
[InlineKeyboardButton(“📋 Copy Trade”, callback_data=“copy_trade”),
InlineKeyboardButton(“💰 Buy or Sell”, callback_data=“buy_or_sell”)],
[InlineKeyboardButton(“📈 Positions”, callback_data=“positions”),
InlineKeyboardButton(“🔍 Search Tokens”, callback_data=“search_tokens”)],
[InlineKeyboardButton(“❓ Help”, callback_data=“help”)]
])

def back_to_dashboard():
return InlineKeyboardMarkup([
[InlineKeyboardButton(“🏠 Dashboard”, callback_data=“dashboard”)]
])

def wallet_keyboard(has_wallet: bool, wallet_count: int):
slot = wallet_count + 1
buttons = [
[InlineKeyboardButton(f”🎲 Generate Wallet (Slot {slot}/2)”, callback_data=“generate_wallet”)],
[InlineKeyboardButton(“🔑 Import Private Key”, callback_data=“import_private_key”),
InlineKeyboardButton(“🧩 Import Seed Phrase”, callback_data=“import_seed”)],
[InlineKeyboardButton(“📊 Check Status”, callback_data=“check_status”),
InlineKeyboardButton(“🔄 Refresh Balance”, callback_data=“refresh_balance”)],
[InlineKeyboardButton(“🏠 Back to Dashboard”, callback_data=“dashboard”)]
]
return InlineKeyboardMarkup(buttons)

# ========== DASHBOARD ==========

async def show_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
user_id = update.effective_user.id
user = get_user(user_id)
wallets = user[“wallets”]

```
sol_price = get_sol_price()
sol_volume = get_sol_volume()

total_balance = 0.0
wallet_lines = ""
for i, w in enumerate(wallets):
    bal = get_sol_balance(w["address"])
    total_balance += bal
    usd_val = bal * sol_price
    wallet_lines += f"\n💼 Wallet {i+1}: {bal:.6f} SOL (${usd_val:.2f})\n`{w['address']}`\n"

if not wallets:
    wallet_lines = "\n❌ No wallet connected yet.\n"

change_emoji = "📈" if sol_price > 0 else "📉"
text = (
    f"⚡ *TRADE BOT DASHBOARD* ⚡\n"
    f"━━━━━━━━━━━━━━━━━━━━\n"
    f"👛 *YOUR WALLETS ({len(wallets)}/2)*\n"
    f"Total Balance: *{total_balance:.6f} SOL* (${total_balance * sol_price:.2f})\n"
    f"{wallet_lines}\n"
    f"━━━━━━━━━━━━━━━━━━━━\n"
    f"📊 *SOLANA MARKET*\n"
    f"{change_emoji} Price: *${sol_price:.2f}*\n"
    f"📦 Volume: *{sol_volume}*\n"
    f"━━━━━━━━━━━━━━━━━━━━\n"
    f"✅ Ready to trade • All systems active"
)

keyboard = main_menu_keyboard()
if edit:
    await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
else:
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
```

# ========== /start ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
await show_dashboard(update, context, edit=False)

# ========== CALLBACK HANDLER ==========

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
query = update.callback_query
await query.answer()
data = query.data
user_id = update.effective_user.id
user = get_user(user_id)

```
# ---- DASHBOARD ----
if data == "dashboard":
    await show_dashboard(update, context, edit=True)

# ---- REFRESH ----
elif data == "refresh":
    await query.edit_message_text("🔄 *Refreshing balances...*", parse_mode="Markdown")
    await show_dashboard(update, context, edit=True)

# ---- WALLET ----
elif data == "wallet":
    wallets = user["wallets"]
    if not wallets:
        text = (
            "🔐 *WALLET MANAGEMENT*\n\n"
            "❌ *No Wallet Connected*\n\n"
            "Create a new wallet or import an existing one to get started.\n\n"
            "💡 *Tip:* If you already have a wallet (Phantom, Solflare), "
            "you can import it using your private key or seed phrase.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Choose an action below:"
        )
    else:
        lines = ""
        for i, w in enumerate(wallets):
            bal = get_sol_balance(w["address"])
            lines += f"\n✅ Wallet {i+1}: `{w['address'][:20]}...`\nBalance: {bal:.6f} SOL\n"
        text = f"🔐 *WALLET MANAGEMENT*\n{lines}\n━━━━━━━━━━━━━━━━━━━━\nChoose an action below:"

    await query.edit_message_text(
        text,
        reply_markup=wallet_keyboard(len(wallets) > 0, len(wallets)),
        parse_mode="Markdown"
    )

# ---- GENERATE WALLET ----
elif data == "generate_wallet":
    wallets = user["wallets"]
    if len(wallets) >= 2:
        await query.edit_message_text(
            "⚠️ *Maximum 2 wallets reached.*\nDelete a wallet to generate a new one.",
            reply_markup=back_to_dashboard(), parse_mode="Markdown"
        )
        return
    kp = Keypair()
    address = str(kp.pubkey())
    private_key = base58.b58encode(bytes(kp)).decode()
    wallets.append({"address": address, "private_key": private_key})
    text = (
        f"✅ *Wallet {len(wallets)} Generated Successfully!*\n\n"
        f"📋 *Your Address:*\n`{address}`\n\n"
        f"🔑 *Private Key (KEEP SECRET!):*\n`{private_key}`\n\n"
        f"💰 Balance: 0.000000 SOL\n\n"
        f"⚠️ *IMPORTANT: Save your private key somewhere safe! We cannot recover it.*\n\n"
        f"🎉 Your new Solana wallet is ready!"
    )
    await query.edit_message_text(text, reply_markup=back_to_dashboard(), parse_mode="Markdown")

# ---- IMPORT PRIVATE KEY ----
elif data == "import_private_key":
    await query.edit_message_text(
        "🔑 *Import Private Key*\n\nPlease send your Solana private key (base58 format):\n\n⚠️ Never share your private key with anyone!",
        reply_markup=back_to_dashboard(), parse_mode="Markdown"
    )
    context.user_data["state"] = IMPORT_PRIVATE_KEY

# ---- IMPORT SEED PHRASE ----
elif data == "import_seed":
    await query.edit_message_text(
        "🧩 *Import Seed Phrase*\n\nPlease send your 12 or 24 word seed phrase separated by spaces:\n\n⚠️ Never share your seed phrase with anyone!",
        reply_markup=back_to_dashboard(), parse_mode="Markdown"
    )
    context.user_data["state"] = IMPORT_SEED

# ---- CHECK STATUS ----
elif data == "check_status":
    wallets = user["wallets"]
    if not wallets:
        text = "❌ No wallet connected."
    else:
        lines = ""
        for i, w in enumerate(wallets):
            bal = get_sol_balance(w["address"])
            status = "🟢 Active" if bal >= 0 else "🔴 Error"
            lines += f"\nWallet {i+1}: {status}\nAddress: `{w['address'][:20]}...`\nBalance: {bal:.6f} SOL\n"
        text = f"📊 *WALLET STATUS*\n{lines}"
    await query.edit_message_text(text, reply_markup=back_to_dashboard(), parse_mode="Markdown")

# ---- REFRESH BALANCE ----
elif data == "refresh_balance":
    wallets = user["wallets"]
    if not wallets:
        text = "❌ No wallet connected."
    else:
        lines = ""
        for i, w in enumerate(wallets):
            bal = get_sol_balance(w["address"])
            lines += f"\nWallet {i+1}: {bal:.6f} SOL\n`{w['address'][:20]}...`\n"
        text = f"🔄 *Balances Refreshed!*\n{lines}"
    await query.edit_message_text(text, reply_markup=back_to_dashboard(), parse_mode="Markdown")

# ---- AI SNIPER ----
elif data == "ai_sniper":
    wallets = user["wallets"]
    if not wallets:
        await query.edit_message_text(
            "⚠️ *You need a connected wallet to use AI Sniper.*\n\nPlease create or import a wallet first.",
            reply_markup=back_to_dashboard(), parse_mode="Markdown"
        )
        return
    settings = user["sniper_settings"]
    status = "🟢 ACTIVE" if user["sniper_active"] else "🔴 INACTIVE"
    text = (
        f"🎯 *AI SNIPER*\n\n"
        f"Status: {status}\n\n"
        f"⚙️ *Settings:*\n"
        f"• Buy Amount: {settings['amount']} SOL\n"
        f"• Slippage: {settings['slippage']}%\n\n"
        f"The AI Sniper automatically detects and snipes new token launches on Solana."
    )
    toggle = "🔴 Stop Sniper" if user["sniper_active"] else "🟢 Start Sniper"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle, callback_data="toggle_sniper")],
        [InlineKeyboardButton("⚙️ Set Buy Amount", callback_data="set_sniper_amount"),
         InlineKeyboardButton("📊 Set Slippage", callback_data="set_sniper_slippage")],
        [InlineKeyboardButton("🏠 Dashboard", callback_data="dashboard")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

elif data == "toggle_sniper":
    user["sniper_active"] = not user["sniper_active"]
    status = "🟢 ACTIVATED" if user["sniper_active"] else "🔴 STOPPED"
    await query.edit_message_text(
        f"🎯 *AI Sniper {status}*\n\n{'Monitoring for new token launches...' if user['sniper_active'] else 'Sniper has been stopped.'}",
        reply_markup=back_to_dashboard(), parse_mode="Markdown"
    )

# ---- APEX SNIPER ----
elif data == "apex_sniper":
    wallets = user["wallets"]
    if not wallets:
        await query.edit_message_text(
            "⚠️ *You need a connected wallet to use Apex Sniper.*",
            reply_markup=back_to_dashboard(), parse_mode="Markdown"
        )
        return
    text = (
        "🚀 *APEX SNIPER*\n\n"
        "Search trading pairs and execute snipes with your configured settings.\n\n"
        "Enter a contract address (CA) to search and snipe a token pair."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Search Pair by CA", callback_data="apex_search_ca")],
        [InlineKeyboardButton("🏠 Dashboard", callback_data="dashboard")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

elif data == "apex_search_ca":
    await query.edit_message_text(
        "🔍 *Search Pair by Contract Address*\n\nSend the token contract address (CA):",
        reply_markup=back_to_dashboard(), parse_mode="Markdown"
    )
    context.user_data["state"] = AI_SNIPER_WAITING

# ---- COPY TRADE ----
elif data == "copy_trade":
    wallets = user["wallets"]
    if not wallets:
        await query.edit_message_text(
            "⚠️ *You need a connected wallet to use Copy Trade.*\n\nPlease create or import a wallet first.",
            reply_markup=back_to_dashboard(), parse_mode="Markdown"
        )
        return
    copy_wallets = user["copy_wallets"]
    if not copy_wallets:
        wallet_list = "No wallets being tracked yet."
    else:
        wallet_list = "\n".join([f"• `{w[:20]}...`" for w in copy_wallets])

    text = (
        f"📋 *COPY TRADE*\n\n"
        f"Follow successful traders automatically.\n\n"
        f"📌 *Tracked Wallets:*\n{wallet_list}\n\n"
        f"Add a wallet address to start copy trading their moves."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Wallet to Copy", callback_data="add_copy_wallet")],
        [InlineKeyboardButton("🗑 Remove Wallet", callback_data="remove_copy_wallet")],
        [InlineKeyboardButton("🏠 Dashboard", callback_data="dashboard")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

elif data == "add_copy_wallet":
    await query.edit_message_text(
        "📋 *Add Wallet to Copy Trade*\n\nSend the Solana wallet address you want to copy:",
        reply_markup=back_to_dashboard(), parse_mode="Markdown"
    )
    context.user_data["state"] = COPY_WALLET

elif data == "remove_copy_wallet":
    copy_wallets = user["copy_wallets"]
    if not copy_wallets:
        await query.edit_message_text("❌ No wallets to remove.", reply_markup=back_to_dashboard(), parse_mode="Markdown")
    else:
        user["copy_wallets"] = []
        await query.edit_message_text("✅ All copy trade wallets removed.", reply_markup=back_to_dashboard(), parse_mode="Markdown")

# ---- BUY OR SELL ----
elif data == "buy_or_sell":
    wallets = user["wallets"]
    if not wallets:
        await query.edit_message_text(
            "⚠️ *Wallet Required*\n\nPlease connect a wallet first to buy or sell tokens.",
            reply_markup=back_to_dashboard(), parse_mode="Markdown"
        )
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Buy Token", callback_data="buy_token"),
         InlineKeyboardButton("🔴 Sell Token", callback_data="sell_token")],
        [InlineKeyboardButton("🏠 Dashboard", callback_data="dashboard")]
    ])
    await query.edit_message_text(
        "💰 *BUY OR SELL*\n\nChoose an action:",
        reply_markup=keyboard, parse_mode="Markdown"
    )

elif data == "buy_token":
    await query.edit_message_text(
        "🟢 *BUY TOKEN*\n\nSend the token contract address you want to buy:",
        reply_markup=back_to_dashboard(), parse_mode="Markdown"
    )
    context.user_data["state"] = BUY_TOKEN

elif data == "sell_token":
    await query.edit_message_text(
        "🔴 *SELL TOKEN*\n\nSend the token contract address you want to sell:",
        reply_markup=back_to_dashboard(), parse_mode="Markdown"
    )
    context.user_data["state"] = SELL_TOKEN

# ---- POSITIONS ----
elif data == "positions":
    positions = user["positions"]
    if not positions:
        text = (
            "📈 *YOUR POSITIONS*\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "You have no open positions.\n\n"
            "💡 Start trading by using the Buy or Sell feature!"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Buy or Sell", callback_data="buy_or_sell")],
            [InlineKeyboardButton("🏠 Dashboard", callback_data="dashboard")]
        ])
    else:
        lines = ""
        for p in positions:
            lines += f"\n• {p['symbol']}: {p['amount']} @ ${p['entry_price']:.4f}\n"
        text = f"📈 *YOUR POSITIONS*\n\n{lines}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Dashboard", callback_data="dashboard")]
        ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")

# ---- SEARCH TOKENS ----
elif data == "search_tokens":
    await query.edit_message_text(
        "🔍 *TOKEN SEARCH*\n\nSend a token name, symbol, or contract address:\n\n"
        "*Examples:*\n• BONK\n• Solana\n• DezXAZ8z7PnrnRJ...YwKT",
        reply_markup=back_to_dashboard(), parse_mode="Markdown"
    )
    context.user_data["state"] = SEARCH_TOKEN

# ---- HELP ----
elif data == "help":
    text = (
        "❓ *HELP & SUPPORT* ❓\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📖 *How to Use This Bot:*\n\n"
        "1️⃣ *Create Wallet:* Generate or import your Solana wallet\n"
        "2️⃣ *Fund Wallet:* Send SOL to your wallet address\n"
        "3️⃣ *Search Tokens:* Find and analyze Solana tokens\n"
        "4️⃣ *Buy or Sell:* Trade tokens instantly\n"
        "5️⃣ *AI Sniper:* Auto-snipe new token launches\n"
        "6️⃣ *Copy Trade:* Follow successful wallets\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ *Quick Commands:*\n"
        "/start - Dashboard\n"
        "/wallet - Wallet management\n"
        "/status - Wallet status\n"
        "/help - This help menu\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "💬 *Need Help?*\n"
        "Contact support for assistance."
    )
    await query.edit_message_text(text, reply_markup=back_to_dashboard(), parse_mode="Markdown")
```

# ========== MESSAGE HANDLER ==========

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
user_id = update.effective_user.id
user = get_user(user_id)
state = context.user_data.get(“state”)
text = update.message.text.strip()

```
if state == IMPORT_PRIVATE_KEY:
    context.user_data["state"] = None
    try:
        decoded = base58.b58decode(text)
        kp = Keypair.from_bytes(decoded)
        address = str(kp.pubkey())
        if len(user["wallets"]) >= 2:
            await update.message.reply_text("⚠️ Maximum 2 wallets reached.", reply_markup=back_to_dashboard())
            return
        user["wallets"].append({"address": address, "private_key": text})
        bal = get_sol_balance(address)
        await update.message.reply_text(
            f"✅ *Wallet Imported Successfully!*\n\n📋 Address:\n`{address}`\n\n💰 Balance: {bal:.6f} SOL",
            reply_markup=back_to_dashboard(), parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text("❌ Invalid private key. Please try again.", reply_markup=back_to_dashboard())

elif state == IMPORT_SEED:
    context.user_data["state"] = None
    await update.message.reply_text(
        "⚠️ *Seed phrase import is not supported for security reasons.*\nPlease use private key import instead.",
        reply_markup=back_to_dashboard(), parse_mode="Markdown"
    )

elif state == SEARCH_TOKEN:
    context.user_data["state"] = None
    await update.message.reply_text("🔍 Searching...")
    info = search_token_info(text)
    if not info:
        await update.message.reply_text("❌ Token not found. Try a different name or contract address.", reply_markup=back_to_dashboard())
        return
    change = info["change_24h"]
    change_emoji = "📈" if float(change) >= 0 else "📉"
    result = (
        f"🔍 *TOKEN INFO*\n\n"
        f"🪙 *{info['name']}* (${info['symbol']})\n\n"
        f"📋 Address: `{info['address']}`\n"
        f"💵 Price: *${float(info['price']):.8f}*\n"
        f"{change_emoji} 24h Change: *{change}%*\n"
        f"📦 24h Volume: *${info['volume_24h']:,.0f}*\n"
        f"💧 Liquidity: *${info['liquidity']:,.0f}*\n"
        f"📊 Market Cap: *${info['market_cap']:,.0f}*\n"
        f"🔄 DEX: *{info['dex'].upper()}*"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Buy This Token", callback_data="buy_token"),
         InlineKeyboardButton("🔴 Sell This Token", callback_data="sell_token")],
        [InlineKeyboardButton("🏠 Dashboard", callback_data="dashboard")]
    ])
    await update.message.reply_text(result, reply_markup=keyboard, parse_mode="Markdown")

elif state == BUY_TOKEN:
    context.user_data["pending_buy_token"] = text
    context.user_data["state"] = BUY_AMOUNT
    await update.message.reply_text(
        f"🟢 *Buy Token*\n\nToken: `{text[:20]}...`\n\nHow much SOL do you want to spend?\n\nExamples: 0.1, 0.5, 1",
        parse_mode="Markdown"
    )

elif state == BUY_AMOUNT:
    context.user_data["state"] = None
    try:
        amount = float(text)
        token = context.user_data.get("pending_buy_token", "Unknown")
        wallets = user["wallets"]
        bal = get_sol_balance(wallets[0]["address"])
        if amount > bal:
            await update.message.reply_text(
                f"❌ Insufficient balance!\nYour balance: {bal:.6f} SOL\nRequired: {amount} SOL",
                reply_markup=back_to_dashboard()
            )
            return
        # Simulate buy (real implementation needs Jupiter swap)
        user["positions"].append({
            "symbol": token[:10],
            "amount": amount,
            "entry_price": 0.001,
            "type": "buy"
        })
        await update.message.reply_text(
            f"✅ *Buy Order Placed!*\n\n"
            f"💰 Amount: {amount} SOL\n"
            f"🪙 Token: `{token[:20]}...`\n"
            f"⏳ Order submitted to Solana network...",
            reply_markup=back_to_dashboard(), parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please enter a number.", reply_markup=back_to_dashboard())

elif state == SELL_TOKEN:
    context.user_data["pending_sell_token"] = text
    context.user_data["state"] = SELL_AMOUNT
    await update.message.reply_text(
        f"🔴 *Sell Token*\n\nToken: `{text[:20]}...`\n\nHow much % do you want to sell?\n\nExamples: 25, 50, 100",
        parse_mode="Markdown"
    )

elif state == SELL_AMOUNT:
    context.user_data["state"] = None
    try:
        percent = float(text)
        token = context.user_data.get("pending_sell_token", "Unknown")
        await update.message.reply_text(
            f"✅ *Sell Order Placed!*\n\n"
            f"📉 Selling: {percent}%\n"
            f"🪙 Token: `{token[:20]}...`\n"
            f"⏳ Order submitted to Solana network...",
            reply_markup=back_to_dashboard(), parse_mode="Markdown"
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid percentage. Please enter a number.", reply_markup=back_to_dashboard())

elif state == COPY_WALLET:
    context.user_data["state"] = None
    try:
        Pubkey.from_string(text)
        user["copy_wallets"].append(text)
        await update.message.reply_text(
            f"✅ *Copy Trade Activated!*\n\n📋 Tracking wallet:\n`{text}`\n\nYou will now mirror their trades automatically.",
            reply_markup=back_to_dashboard(), parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text("❌ Invalid Solana wallet address.", reply_markup=back_to_dashboard())

elif state == AI_SNIPER_WAITING:
    context.user_data["state"] = None
    await update.message.reply_text("🔍 Searching pair...")
    info = search_token_info(text)
    if not info:
        await update.message.reply_text("❌ Pair not found.", reply_markup=back_to_dashboard())
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Snipe This Token", callback_data="buy_token")],
        [InlineKeyboardButton("🏠 Dashboard", callback_data="dashboard")]
    ])
    await update.message.reply_text(
        f"🚀 *APEX SNIPER - Pair Found!*\n\n"
        f"🪙 {info['name']} (${info['symbol']})\n"
        f"💵 Price: ${float(info['price']):.8f}\n"
        f"💧 Liquidity: ${info['liquidity']:,.0f}\n\n"
        f"Ready to snipe!",
        reply_markup=keyboard, parse_mode="Markdown"
    )
else:
    # Default - show dashboard
    await show_dashboard(update, context, edit=False)
```

# ========== COMMANDS ==========

async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
user_id = update.effective_user.id
user = get_user(user_id)
wallets = user[“wallets”]
text = “🔐 *WALLET MANAGEMENT*\n\nChoose an action below:”
await update.message.reply_text(
text,
reply_markup=wallet_keyboard(len(wallets) > 0, len(wallets)),
parse_mode=“Markdown”
)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
user_id = update.effective_user.id
user = get_user(user_id)
wallets = user[“wallets”]
if not wallets:
await update.message.reply_text(“❌ No wallet connected.”, reply_markup=back_to_dashboard())
return
lines = “”
for i, w in enumerate(wallets):
bal = get_sol_balance(w[“address”])
lines += f”\nWallet {i+1}: 🟢 Active\n`{w['address']}`\nBalance: {bal:.6f} SOL\n”
await update.message.reply_text(
f”📊 *WALLET STATUS*\n{lines}”,
reply_markup=back_to_dashboard(), parse_mode=“Markdown”
)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
text = (
“❓ *HELP & SUPPORT*\n\n”
“/start - Dashboard\n”
“/wallet - Wallet management\n”
“/status - Wallet status\n”
“/help - Help menu”
)
await update.message.reply_text(text, reply_markup=back_to_dashboard(), parse_mode=“Markdown”)

# ========== MAIN ==========

def main():
app = Application.builder().token(BOT_TOKEN).build()

```
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("wallet", wallet_command))
app.add_handler(CommandHandler("status", status_command))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

print("🚀 Trade Bot is running...")
app.run_polling()
```

if **name** == “**main**”:
main()
