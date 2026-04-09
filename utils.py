"""
Utility Functions
"""
import re
from datetime import datetime
from typing import List, Optional
from aiogram.types import CallbackQuery
from config import Config, Emoji

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in Config.ADMIN_IDS

def format_price(amount: float) -> str:
    """Format price with currency"""
    return f"{Config.CURRENCY}{amount:.2f}"

def format_datetime(dt_string: str) -> str:
    """Format datetime string"""
    try:
        dt = datetime.strptime(dt_string, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d %b %Y, %I:%M %p")
    except:
        return dt_string

def validate_transaction_id(transaction_id: str) -> bool:
    """Validate transaction ID format"""
    # Accept 10-20 character alphanumeric strings
    if not transaction_id:
        return False
    
    # Remove spaces and special characters
    cleaned = re.sub(r'[^A-Z0-9]', '', transaction_id.upper())
    
    return 10 <= len(cleaned) <= 20 and cleaned.isalnum()

def split_codes(text: str) -> List[str]:
    """Split text into individual coupon codes"""
    # Split by newline, comma, or space
    codes = re.split(r'[\n,\s]+', text.strip())
    
    # Clean and filter
    codes = [code.strip() for code in codes if code.strip()]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_codes = []
    for code in codes:
        if code not in seen:
            seen.add(code)
            unique_codes.append(code)
    
    return unique_codes

async def safe_answer_callback(callback: CallbackQuery, text: Optional[str] = None):
    """Safely answer callback query"""
    try:
        await callback.answer(text)
    except:
        pass

def format_coupon_detail(coupon: dict) -> str:
    """Format coupon detail text"""
    text = f"{Emoji.COUPON} <b>{coupon['name']}</b>\n\n"
    
    if coupon.get('description'):
        text += f"{coupon['description']}\n\n"
    
    # Price
    text += f"<b>{Emoji.MONEY} Price:</b> {format_price(coupon['price'])}\n"
    
    # Discount
    if coupon.get('original_price') and coupon['original_price'] > coupon['price']:
        discount = int(((coupon['original_price'] - coupon['price']) / coupon['original_price']) * 100)
        text += f"<b>{Emoji.SALE} Discount:</b> {discount}% OFF\n"
        text += f"<s>Original: {format_price(coupon['original_price'])}</s>\n"
    
    text += f"\n"
    
    # Stock
    if coupon['available_stock'] > 0:
        text += f"<b>📦 Stock:</b> {coupon['available_stock']} available\n"
        
        if coupon['available_stock'] < 10:
            text += f"⚠️ <i>Limited stock!</i>\n"
    else:
        text += f"<b>❌ Out of Stock</b>\n"
    
    # Purchase limits
    text += f"<b>Min Purchase:</b> {coupon.get('min_purchase', 1)}\n"
    text += f"<b>Max Purchase:</b> {coupon.get('max_purchase', 10)}\n"
    
    # Featured
    if coupon.get('is_featured'):
        text += f"\n{Emoji.FIRE} <b>Featured Product!</b>\n"
    
    return text

def format_admin_order_detail(order: dict) -> str:
    """Format order detail for admin"""
    text = f"{Emoji.ORDERS} <b>Order Details</b>\n\n"
    
    text += f"<b>Order ID:</b> #{order['id']}\n"
    text += f"<b>Coupon:</b> {order.get('coupon_name', 'N/A')}\n"
    text += f"<b>Quantity:</b> {order['quantity']}\n"
    text += f"<b>Total:</b> {format_price(order['total_price'])}\n\n"
    
    text += f"<b>Customer Information:</b>\n"
    text += f"User ID: <code>{order['user_id']}</code>\n"
    
    if order.get('username'):
        text += f"Username: @{order['username']}\n"
    
    text += f"\n<b>Payment Details:</b>\n"
    text += f"Transaction ID: <code>{order.get('transaction_id', 'N/A')}</code>\n"
    text += f"Screenshot: {'✅ Uploaded' if order.get('screenshot_file_id') else '❌ None'}\n\n"
    
    # Status
    status_emoji = {
        'pending': Emoji.PENDING,
        'approved': Emoji.APPROVED,
        'delivered': Emoji.APPROVED,
        'rejected': Emoji.REJECTED
    }
    
    text += f"<b>Status:</b> {status_emoji.get(order['status'], '')} {order['status'].title()}\n"
    
    if order['status'] == 'rejected' and order.get('reject_reason'):
        text += f"<b>Reject Reason:</b> {order['reject_reason']}\n"
    
    text += f"\n<b>Dates:</b>\n"
    text += f"Created: {format_datetime(order['created_at'])}\n"
    
    if order.get('updated_at') != order.get('created_at'):
        text += f"Updated: {format_datetime(order['updated_at'])}\n"
    
    return text