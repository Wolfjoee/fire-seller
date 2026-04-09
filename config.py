"""
Configuration and Environment Settings
"""
import os
from typing import List

class Config:
    """Bot configuration"""
    
    # Bot Token from BotFather
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # Admin User IDs (comma-separated)
    ADMIN_IDS: List[int] = [
        int(id.strip()) 
        for id in os.getenv("ADMIN_IDS", "").split(",") 
        if id.strip().isdigit()
    ]
    
    # Database
    DB_FILE: str = os.getenv("DB_FILE", "coupon_bot.db")
    
    # Payment Settings
    DEFAULT_UPI_ID: str = os.getenv("UPI_ID", "merchant@upi")
    CURRENCY: str = "₹"
    
    # Bot Settings
    ITEMS_PER_PAGE: int = 8
    MAX_COUPON_PURCHASE: int = 10
    AUTO_DELETE_MESSAGES: bool = True
    MESSAGE_DELETE_DELAY: int = 300  # 5 minutes
    
    # Feature Flags
    ENABLE_REFERRAL: bool = True
    ENABLE_DISCOUNT: bool = True
    ENABLE_AUTO_EXPIRY: bool = True
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required!")
        if not cls.ADMIN_IDS:
            raise ValueError("At least one ADMIN_ID is required!")
        return True

# Emoji Constants
class Emoji:
    """Emoji constants for better UX"""
    CART = "🛒"
    MONEY = "💰"
    CHECK = "✅"
    CROSS = "❌"
    BACK = "⬅️"
    HOME = "🏠"
    CATEGORY = "📁"
    COUPON = "🎫"
    ADMIN = "👨‍💼"
    USER = "👤"
    ORDERS = "📦"
    PENDING = "⏳"
    APPROVED = "✅"
    REJECTED = "🚫"
    SETTINGS = "⚙️"
    BROADCAST = "📢"
    STATS = "📊"
    SEARCH = "🔍"
    ADD = "➕"
    EDIT = "✏️"
    DELETE = "🗑️"
    UPLOAD = "📤"
    DOWNLOAD = "📥"
    QR = "📱"
    HELP = "ℹ️"
    STAR = "⭐"
    FIRE = "🔥"
    NEW = "🆕"
    SALE = "🏷️"

# Messages
class Messages:
    """Message templates"""
    
    WELCOME = """
{emoji} <b>Welcome to Coupon Store!</b>

Browse premium coupons at the best prices.
Choose a category below to get started!

💡 <i>Tip: Use /help for all commands</i>
"""
    
    HELP_USER = """
<b>📚 User Commands</b>

/start - Start the bot
/browse - Browse coupons
/myorders - View your orders
/help - Show this help

<b>How to Purchase:</b>
1️⃣ Browse categories
2️⃣ Select a coupon
3️⃣ Choose quantity
4️⃣ Make payment via QR
5️⃣ Submit transaction ID
6️⃣ Wait for admin approval
7️⃣ Receive your coupons!

<i>Need help? Contact admin</i>
"""
    
    HELP_ADMIN = """
<b>👨‍💼 Admin Commands</b>

<b>Main Panel:</b>
/admin - Open admin panel

<b>Category Management:</b>
/addcategory - Add new category
/categories - Manage categories

<b>Coupon Management:</b>
/addcoupon - Add new coupon
/coupons - Manage all coupons
/bulkupload - Upload coupon codes

<b>Order Management:</b>
/orders - View all orders
/pending - Pending approvals

<b>User Management:</b>
/users - View all users
/broadcast - Send broadcast

<b>Settings:</b>
/qr - Update payment QR
/stats - View statistics

<i>All operations via inline buttons!</i>
"""
    
    ORDER_CREATED = """
<b>🎉 Order Created Successfully!</b>

Order ID: <code>#{order_id}</code>
Coupon: {coupon_name}
Quantity: {quantity}
Total: {currency}{total}

Status: ⏳ <b>Pending Approval</b>

Your order is under review. You'll be notified once approved!
"""
    
    ORDER_APPROVED = """
<b>✅ Order Approved!</b>

Order ID: <code>#{order_id}</code>
Coupon: {coupon_name}

<b>Your Coupon Codes:</b>
{codes}

Thank you for your purchase! 🎉
"""
    
    ORDER_REJECTED = """
<b>❌ Order Rejected</b>

Order ID: <code>#{order_id}</code>
Coupon: {coupon_name}

<b>Reason:</b> {reason}

Please contact admin if you have questions.
"""