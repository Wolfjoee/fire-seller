"""
Utility Functions
"""
import re
from typing import List, Optional
from datetime import datetime
from config import Config, Emoji, Messages

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in Config.ADMIN_IDS

def format_price(amount: float) -> str:
    """Format price with currency"""
    return f"{Config.CURRENCY}{amount:.2f}"

def format_datetime(dt: str) -> str:
    """Format datetime string"""
    try:
        dt_obj = datetime.fromisoformat(dt)
        return dt_obj.strftime("%d %b %Y, %I:%M %p")
    except:
        return dt

def validate_transaction_id(txn_id: str) -> bool:
    """Validate transaction ID format"""
    # Allow alphanumeric, 10-20 characters
    return bool(re.match(r'^[A-Z0-9]{10,20}$', txn_id.upper()))

def validate_upi_id(upi: str) -> bool:
    """Validate UPI ID format"""
    return bool(re.match(r'^[\w.-]+@[\w.-]+$', upi))

def format_coupon_detail(coupon: dict) -> str:
    """Format coupon details for display"""
    discount_info = ""
    if coupon.get('original_price') and coupon['original_price'] > coupon['price']:
        discount = int(((coupon['original_price'] - coupon['price']) / coupon['original_price']) * 100)
        discount_info = f"\n{Emoji.SALE} <b>Discount:</b> {discount}% OFF (Was {format_price(coupon['original_price'])})"
    
    stock_status = f"{Emoji.CHECK} In Stock" if coupon['available_stock'] > 0 else f"{Emoji.CROSS} Out of Stock"
    
    featured = f"\n{Emoji.STAR} <b>Featured Item!</b>" if coupon.get('is_featured') else ""
    
    return f"""
{Emoji.COUPON} <b>{coupon['name']}</b>

{Emoji.CATEGORY} <b>Category:</b> {coupon.get('category_name', 'N/A')}
{Emoji.MONEY} <b>Price:</b> {format_price(coupon['price'])}{discount_info}
📦 <b>Available Stock:</b> {coupon['available_stock']}
📊 <b>Stock Status:</b> {stock_status}

📝 <b>Description:</b>
{coupon.get('description', 'No description available')}{featured}

<i>Select quantity to purchase</i>
"""

def format_order_detail(order: dict) -> str:
    """Format order details for display"""
    status_emoji = {
        'pending': Emoji.PENDING,
        'approved': Emoji.APPROVED,
        'rejected': Emoji.REJECTED,
        'delivered': Emoji.CHECK
    }
    
    status_text = f"{status_emoji.get(order['status'], '')} <b>{order['status'].upper()}</b>"
    
    reject_info = ""
    if order['status'] == 'rejected' and order.get('reject_reason'):
        reject_info = f"\n{Emoji.CROSS} <b>Reject Reason:</b> {order['reject_reason']}"
    
    return f"""
{Emoji.ORDERS} <b>Order #{order['id']}</b>

{Emoji.COUPON} <b>Coupon:</b> {order['coupon_name']}
🔢 <b>Quantity:</b> {order['quantity']}
{Emoji.MONEY} <b>Unit Price:</b> {format_price(order['unit_price'])}
💵 <b>Total:</b> {format_price(order['total_price'])}

💳 <b>Transaction ID:</b> <code>{order['transaction_id']}</code>
📅 <b>Ordered On:</b> {format_datetime(order['created_at'])}

📊 <b>Status:</b> {status_text}{reject_info}
"""

def format_admin_order_detail(order: dict) -> str:
    """Format order details for admin view"""
    user_info = f"@{order['username']}" if order.get('username') else order.get('first_name', 'Unknown')
    
    return f"""
{Emoji.ADMIN} <b>Admin Order View</b>

{Emoji.ORDERS} <b>Order ID:</b> #{order['id']}
{Emoji.USER} <b>Customer:</b> {user_info} (ID: {order['user_id']})

{Emoji.COUPON} <b>Coupon:</b> {order['coupon_name']}
🔢 <b>Quantity:</b> {order['quantity']}
{Emoji.MONEY} <b>Unit Price:</b> {format_price(order['unit_price'])}
💵 <b>Total Amount:</b> {format_price(order['total_price'])}

💳 <b>Transaction ID:</b> <code>{order['transaction_id']}</code>
📅 <b>Ordered:</b> {format_datetime(order['created_at'])}

📊 <b>Status:</b> {order['status'].upper()}
"""

def format_statistics(stats: dict) -> str:
    """Format bot statistics"""
    return f"""
{Emoji.STATS} <b>Bot Statistics</b>

{Emoji.USER} <b>Total Users:</b> {stats.get('total_users', 0)}
{Emoji.CATEGORY} <b>Active Categories:</b> {stats.get('total_categories', 0)}
{Emoji.COUPON} <b>Active Coupons:</b> {stats.get('total_coupons', 0)}

{Emoji.ORDERS} <b>Total Orders:</b> {stats.get('total_orders', 0)}
{Emoji.PENDING} <b>Pending Orders:</b> {stats.get('pending_orders', 0)}
{Emoji.APPROVED} <b>Approved Orders:</b> {stats.get('approved_orders', 0)}

{Emoji.MONEY} <b>Total Revenue:</b> {format_price(stats.get('total_revenue', 0))}

📅 <b>Today's Performance:</b>
• Orders: {stats.get('today_orders', 0)}
• Revenue: {format_price(stats.get('today_revenue', 0))}
"""

def split_codes(codes_text: str) -> List[str]:
    """Split and clean coupon codes from text"""
    # Split by newlines and commas
    codes = re.split(r'[,\n]+', codes_text)
    # Clean and filter
    codes = [code.strip() for code in codes if code.strip()]
    return codes

def format_codes_list(codes: List[str]) -> str:
    """Format coupon codes for delivery"""
    formatted = []
    for i, code in enumerate(codes, 1):
        formatted.append(f"{i}. <code>{code}</code>")
    return "\n".join(formatted)

def escape_markdown(text: str) -> str:
    """Escape markdown special characters"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, '\\' + char)
    return text

async def safe_delete_message(message, delay: int = 0):
    """Safely delete message with optional delay"""
    try:
        if delay > 0:
            await asyncio.sleep(delay)
        await message.delete()
    except:
        pass

async def safe_answer_callback(callback_query, text: str = None, show_alert: bool = False):
    """Safely answer callback query"""
    try:
        await callback_query.answer(text=text, show_alert=show_alert)
    except:
        pass