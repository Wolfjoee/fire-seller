"""
Bot Handlers - All Commands and Callbacks
FIXED VERSION with proper category/coupon management
"""
import logging
from datetime import datetime
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup

from config import Config, Emoji, Messages
from database import db
from keyboards import Keyboards
from states import (
    CategoryStates, CouponStates, OrderStates, 
    QRStates, BroadcastStates
)
from utils import (
    is_admin, format_price, format_datetime, 
    validate_transaction_id, split_codes,
    safe_answer_callback, format_coupon_detail,
    format_admin_order_detail
)

logger = logging.getLogger(__name__)
router = Router()

# ==================== HELPER FUNCTIONS ====================

async def delete_message_safe(message: Message):
    """Safely delete message"""
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Could not delete message: {e}")

# ==================== START & HELP ====================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Start command - main entry point"""
    await state.clear()
    
    # Register user
    db.add_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    welcome_text = Messages.WELCOME.format(emoji=Emoji.FIRE)
    keyboard = Keyboards.main_menu(is_admin=is_admin(message.from_user.id))
    
    await message.answer(welcome_text, reply_markup=keyboard)

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Help command"""
    if is_admin(message.from_user.id):
        await message.answer(Messages.HELP_ADMIN)
        await message.answer(Messages.HELP_USER)
    else:
        await message.answer(Messages.HELP_USER)

@router.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """Help callback handler"""
    await safe_answer_callback(callback)
    
    if is_admin(callback.from_user.id):
        await callback.message.answer(Messages.HELP_ADMIN)
        await callback.message.answer(Messages.HELP_USER)
    else:
        await callback.message.answer(Messages.HELP_USER)

@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext):
    """Return to main menu"""
    await state.clear()
    await safe_answer_callback(callback)
    
    welcome_text = Messages.WELCOME.format(emoji=Emoji.FIRE)
    keyboard = Keyboards.main_menu(is_admin=is_admin(callback.from_user.id))
    
    await callback.message.edit_text(welcome_text, reply_markup=keyboard)

# ==================== BROWSE CATEGORIES (USER) ====================

@router.message(Command("browse"))
async def cmd_browse(message: Message, state: FSMContext):
    """Browse categories command"""
    await state.clear()
    categories = db.get_categories(active_only=True)
    
    if not categories:
        await message.answer(
            f"{Emoji.CROSS} No categories available yet.",
            reply_markup=Keyboards.back_button("main_menu", "Main Menu")
        )
        return
    
    text = f"{Emoji.CATEGORY} <b>Browse Categories</b>\n\nSelect a category to view coupons:"
    keyboard = Keyboards.categories_menu(categories)
    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "browse_categories")
async def callback_browse_categories(callback: CallbackQuery, state: FSMContext):
    """Browse categories callback"""
    await state.clear()
    await safe_answer_callback(callback)
    
    categories = db.get_categories(active_only=True)
    
    if not categories:
        await callback.message.edit_text(
            f"{Emoji.CROSS} No categories available yet.",
            reply_markup=Keyboards.back_button("main_menu", "Main Menu")
        )
        return
    
    text = f"{Emoji.CATEGORY} <b>Browse Categories</b>\n\nSelect a category to view coupons:"
    keyboard = Keyboards.categories_menu(categories)
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("category_"))
async def callback_view_category(callback: CallbackQuery, state: FSMContext):
    """View coupons in category"""
    await safe_answer_callback(callback)
    
    category_id = int(callback.data.split("_")[1])
    category = db.get_category(category_id)
    
    if not category:
        await callback.answer("Category not found!", show_alert=True)
        return
    
    coupons = db.get_coupons(category_id=category_id, active_only=True)
    
    if not coupons:
        text = f"{Emoji.CROSS} <b>No Coupons Available</b>\n\n"
        text += f"Category: {category['name']}\n\n"
        text += f"<i>No coupons available in this category yet. Check back later!</i>"
        
        await callback.message.edit_text(
            text,
            reply_markup=Keyboards.back_button("browse_categories", "Back to Categories")
        )
        return
    
    text = f"{category.get('icon', Emoji.CATEGORY)} <b>{category['name']}</b>\n\n"
    if category.get('description'):
        text += f"{category['description']}\n\n"
    text += f"<b>Available Coupons:</b> {len(coupons)}"
    
    keyboard = Keyboards.coupons_menu(coupons, category_id)
    await callback.message.edit_text(text, reply_markup=keyboard)

# ==================== COUPON DETAILS & PURCHASE ====================

@router.callback_query(F.data.startswith("coupon_"))
async def callback_view_coupon(callback: CallbackQuery, state: FSMContext):
    """View coupon details"""
    await safe_answer_callback(callback)
    
    coupon_id = int(callback.data.split("_")[1])
    coupon = db.get_coupon(coupon_id)
    
    if not coupon:
        await callback.answer("Coupon not found!", show_alert=True)
        return
    
    text = format_coupon_detail(coupon)
    keyboard = Keyboards.coupon_detail(coupon, callback.from_user.id)
    
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("purchase_"))
async def callback_start_purchase(callback: CallbackQuery, state: FSMContext):
    """Start purchase process - select quantity"""
    await safe_answer_callback(callback)
    
    coupon_id = int(callback.data.split("_")[1])
    coupon = db.get_coupon(coupon_id)
    
    if not coupon:
        await callback.answer("Coupon not found!", show_alert=True)
        return
    
    if coupon['available_stock'] <= 0:
        await callback.answer("Sorry, this coupon is out of stock!", show_alert=True)
        return
    
    text = f"{Emoji.CART} <b>Purchase {coupon['name']}</b>\n\n"
    text += f"{Emoji.MONEY} Price per coupon: {format_price(coupon['price'])}\n"
    text += f"📦 Available: {coupon['available_stock']}\n\n"
    text += f"<b>Select quantity (Max: {min(coupon['max_purchase'], coupon['available_stock'])}):</b>"
    
    max_qty = min(coupon['max_purchase'], coupon['available_stock'])
    keyboard = Keyboards.quantity_selector(coupon_id, max_qty)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.update_data(coupon_id=coupon_id)

@router.callback_query(F.data.startswith("qty_"))
async def callback_select_quantity(callback: CallbackQuery, state: FSMContext):
    """Handle quantity selection and show payment"""
    await safe_answer_callback(callback)
    
    parts = callback.data.split("_")
    coupon_id = int(parts[1])
    quantity = int(parts[2])
    
    coupon = db.get_coupon(coupon_id)
    
    if not coupon:
        await callback.answer("Coupon not found!", show_alert=True)
        return
    
    if quantity > coupon['available_stock']:
        await callback.answer("Not enough stock available!", show_alert=True)
        return
    
    total_price = coupon['price'] * quantity
    
    # Get QR code settings
    qr_settings = db.get_qr_settings()
    
    # Show payment details
    text = f"{Emoji.MONEY} <b>Payment Details</b>\n\n"
    text += f"{Emoji.COUPON} <b>Coupon:</b> {coupon['name']}\n"
    text += f"🔢 <b>Quantity:</b> {quantity}\n"
    text += f"💵 <b>Unit Price:</b> {format_price(coupon['price'])}\n"
    text += f"💰 <b>Total Amount:</b> {format_price(total_price)}\n\n"
    text += f"<b>Payment Instructions:</b>\n"
    text += f"1️⃣ Scan the QR code below\n"
    text += f"2️⃣ Pay {format_price(total_price)}\n"
    
    if qr_settings and qr_settings.get('upi_id'):
        text += f"   to <code>{qr_settings['upi_id']}</code>\n"
    
    text += f"3️⃣ Take screenshot of confirmation\n"
    text += f"4️⃣ Click 'I've Paid' below\n\n"
    text += f"⚠️ <i>Order processed after admin verification</i>"
    
    # Save order data temporarily
    await state.update_data(
        coupon_id=coupon_id,
        quantity=quantity,
        unit_price=coupon['price'],
        total_price=total_price
    )
    
    # Send QR code if available
    if qr_settings and qr_settings.get('file_id'):
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=qr_settings['file_id'],
                caption=text,
                reply_markup=Keyboards.payment_confirmation()
            )
        except:
            await callback.message.edit_text(
                text + f"\n\n{Emoji.CROSS} QR code unavailable. Contact admin.",
                reply_markup=Keyboards.payment_confirmation()
            )
    else:
        await callback.message.edit_text(
            text + f"\n\n⚠️ <b>QR code not set by admin. Please contact support.</b>",
            reply_markup=Keyboards.back_button("browse_categories", "Back")
        )

@router.callback_query(F.data == "submit_payment")
async def callback_submit_payment(callback: CallbackQuery, state: FSMContext):
    """Request transaction ID from user"""
    await safe_answer_callback(callback)
    
    text = f"{Emoji.UPLOAD} <b>Submit Payment Proof</b>\n\n"
    text += f"Please send your <b>Transaction ID</b> (UTR/Reference number)\n\n"
    text += f"Format: 12-digit alphanumeric code\n"
    text += f"Example: <code>123456789012</code>\n\n"
    text += f"<i>After sending Transaction ID, you'll be asked for a screenshot</i>"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.cancel_order())
    await state.set_state(OrderStates.entering_transaction_id)

@router.message(OrderStates.entering_transaction_id)
async def process_transaction_id(message: Message, state: FSMContext):
    """Process transaction ID input"""
    transaction_id = message.text.strip().upper()
    
    if not validate_transaction_id(transaction_id):
        await message.answer(
            f"{Emoji.CROSS} Invalid transaction ID format!\n\n"
            f"Please send a valid 10-20 character alphanumeric code.",
            reply_markup=Keyboards.cancel_order()
        )
        return
    
    # Check for duplicate transaction ID
    existing_orders = db.get_orders()
    if any(order.get('transaction_id') == transaction_id for order in existing_orders):
        await message.answer(
            f"{Emoji.CROSS} This transaction ID has already been used!\n\n"
            f"Please send a different transaction ID or contact admin.",
            reply_markup=Keyboards.cancel_order()
        )
        return
    
    await state.update_data(transaction_id=transaction_id)
    
    text = f"{Emoji.CHECK} Transaction ID saved: <code>{transaction_id}</code>\n\n"
    text += f"Now please upload your <b>payment screenshot</b>.\n\n"
    text += f"<i>Send the screenshot as a photo</i>"
    
    await message.answer(text, reply_markup=Keyboards.cancel_order())
    await state.set_state(OrderStates.uploading_screenshot)

@router.message(OrderStates.uploading_screenshot, F.photo)
async def process_payment_screenshot(message: Message, state: FSMContext):
    """Process payment screenshot and create order"""
    data = await state.get_data()
    
    # Get largest photo size
    screenshot_file_id = message.photo[-1].file_id
    
    # Create order
    order_id = db.create_order(
        user_id=message.from_user.id,
        coupon_id=data['coupon_id'],
        quantity=data['quantity'],
        total_price=data['total_price'],
        transaction_id=data['transaction_id'],
        screenshot_file_id=screenshot_file_id
    )
    
    if not order_id:
        await message.answer(
            f"{Emoji.CROSS} Failed to create order. Please try again or contact admin."
        )
        await state.clear()
        return
    
    # Get coupon info for notification
    coupon = db.get_coupon(data['coupon_id'])
    
    # Notify user
    user_text = Messages.ORDER_CREATED.format(
        order_id=order_id,
        coupon_name=coupon['name'],
        quantity=data['quantity'],
        currency=Config.CURRENCY,
        total=data['total_price']
    )
    
    await message.answer(
        user_text,
        reply_markup=Keyboards.back_button("main_menu", "Main Menu")
    )
    
    # Notify all admins
    admin_text = f"{Emoji.NEW} <b>New Order Received!</b>\n\n"
    admin_text += f"Order ID: #{order_id}\n"
    admin_text += f"User: {message.from_user.first_name}"
    if message.from_user.username:
        admin_text += f" (@{message.from_user.username})"
    admin_text += f"\nCoupon: {coupon['name']}\n"
    admin_text += f"Quantity: {data['quantity']}\n"
    admin_text += f"Total: {format_price(data['total_price'])}\n"
    admin_text += f"Transaction ID: <code>{data['transaction_id']}</code>\n\n"
    admin_text += f"<i>Click below to approve/reject</i>"
    
    for admin_id in Config.ADMIN_IDS:
        try:
            from bot import bot
            await bot.send_photo(
                chat_id=admin_id,
                photo=screenshot_file_id,
                caption=admin_text,
                reply_markup=Keyboards.order_verification(order_id)
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    await state.clear()

@router.message(OrderStates.uploading_screenshot)
async def handle_invalid_screenshot(message: Message):
    """Handle non-photo input during screenshot upload"""
    await message.answer(
        f"{Emoji.CROSS} Please send a <b>photo</b> of your payment screenshot.\n\n"
        f"<i>Use your phone's camera or gallery</i>",
        reply_markup=Keyboards.cancel_order()
    )

@router.callback_query(F.data == "cancel_order")
async def callback_cancel_order(callback: CallbackQuery, state: FSMContext):
    """Cancel order creation"""
    await state.clear()
    await safe_answer_callback(callback, "Order cancelled")
    
    await callback.message.edit_text(
        f"{Emoji.CROSS} Order cancelled.\n\n<i>You can start a new order anytime!</i>",
        reply_markup=Keyboards.back_button("browse_categories", "Browse Coupons")
    )

# ==================== MY ORDERS ====================

@router.message(Command("myorders"))
async def cmd_my_orders(message: Message):
    """View user's orders"""
    orders = db.get_user_orders(message.from_user.id)
    
    if not orders:
        await message.answer(
            f"{Emoji.CROSS} You haven't placed any orders yet.\n\n"
            f"<i>Browse coupons to get started!</i>",
            reply_markup=Keyboards.back_button("browse_categories", "Browse Coupons")
        )
        return
    
    text = f"{Emoji.ORDERS} <b>My Orders</b>\n\n"
    text += f"Total Orders: {len(orders)}\n"
    text += f"Pending: {sum(1 for o in orders if o['status'] == 'pending')}\n"
    text += f"Delivered: {sum(1 for o in orders if o['status'] in ['delivered', 'approved'])}\n\n"
    text += f"<i>Click an order to view details:</i>"
    
    keyboard = Keyboards.user_orders(orders)
    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "my_orders")
async def callback_my_orders(callback: CallbackQuery):
    """View orders callback"""
    await safe_answer_callback(callback)
    
    orders = db.get_user_orders(callback.from_user.id)
    
    if not orders:
        await callback.message.edit_text(
            f"{Emoji.CROSS} You haven't placed any orders yet.\n\n"
            f"<i>Browse coupons to get started!</i>",
            reply_markup=Keyboards.back_button("main_menu", "Main Menu")
        )
        return
    
    text = f"{Emoji.ORDERS} <b>My Orders</b>\n\n"
    text += f"Total Orders: {len(orders)}\n"
    text += f"Pending: {sum(1 for o in orders if o['status'] == 'pending')}\n"
    text += f"Delivered: {sum(1 for o in orders if o['status'] in ['delivered', 'approved'])}\n\n"
    text += f"<i>Click an order to view details:</i>"
    
    keyboard = Keyboards.user_orders(orders)
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("user_order_"))
async def callback_view_user_order(callback: CallbackQuery):
    """View specific user order"""
    await safe_answer_callback(callback)
    
    order_id = int(callback.data.split("_")[2])
    order = db.get_order(order_id)
    
    if not order or order['user_id'] != callback.from_user.id:
        await callback.answer("Order not found!", show_alert=True)
        return
    
    text = f"{Emoji.ORDERS} <b>Order #{order_id}</b>\n\n"
    text += f"<b>Coupon:</b> {order.get('coupon_name', 'N/A')}\n"
    text += f"<b>Quantity:</b> {order['quantity']}\n"
    text += f"<b>Total:</b> {format_price(order['total_price'])}\n"
    text += f"<b>Transaction ID:</b> <code>{order.get('transaction_id', 'N/A')}</code>\n"
    text += f"<b>Date:</b> {format_datetime(order['created_at'])}\n\n"
    
    # Status
    status_emoji = {
        'pending': Emoji.PENDING,
        'approved': Emoji.APPROVED,
        'delivered': Emoji.APPROVED,
        'rejected': Emoji.REJECTED
    }
    
    text += f"<b>Status:</b> {status_emoji.get(order['status'], '')} {order['status'].title()}\n"
    
    if order['status'] == 'rejected' and order.get('reject_reason'):
        text += f"\n<b>Reject Reason:</b> {order['reject_reason']}\n"
    
    # Show coupon codes if delivered
    if order['status'] in ['delivered', 'approved']:
        codes = db.get_order_coupon_codes(order_id)
        if codes:
            text += f"\n<b>🎫 Your Coupon Codes:</b>\n"
            for i, code in enumerate(codes, 1):
                text += f"{i}. <code>{code['code']}</code>\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.back_button("my_orders", "Back to Orders")
    )

# ==================== ADMIN PANEL ====================

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Admin panel command"""
    if not is_admin(message.from_user.id):
        await message.answer(f"{Emoji.CROSS} Access denied. Admin only!")
        return
    
    await state.clear()
    stats = db.get_statistics()
    
    text = f"{Emoji.ADMIN} <b>Admin Panel</b>\n\n"
    text += f"👥 Total Users: {stats.get('total_users', 0)}\n"
    text += f"📁 Categories: {stats.get('total_categories', 0)}\n"
    text += f"🎫 Coupons: {stats.get('total_coupons', 0)}\n"
    text += f"📦 Total Orders: {stats.get('total_orders', 0)}\n"
    text += f"⏳ Pending: {stats.get('pending_orders', 0)}\n"
    text += f"💰 Revenue: {format_price(stats.get('total_revenue', 0))}\n\n"
    text += f"<i>Select an option below:</i>"
    
    keyboard = Keyboards.admin_panel()
    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "admin_panel")
async def callback_admin_panel(callback: CallbackQuery, state: FSMContext):
    """Admin panel callback"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await state.clear()
    await safe_answer_callback(callback)
    
    stats = db.get_statistics()
    
    text = f"{Emoji.ADMIN} <b>Admin Panel</b>\n\n"
    text += f"👥 Total Users: {stats.get('total_users', 0)}\n"
    text += f"📁 Categories: {stats.get('total_categories', 0)}\n"
    text += f"🎫 Coupons: {stats.get('total_coupons', 0)}\n"
    text += f"📦 Total Orders: {stats.get('total_orders', 0)}\n"
    text += f"⏳ Pending: {stats.get('pending_orders', 0)}\n"
    text += f"💰 Revenue: {format_price(stats.get('total_revenue', 0))}\n\n"
    text += f"<i>Select an option below:</i>"
    
    keyboard = Keyboards.admin_panel()
    await callback.message.edit_text(text, reply_markup=keyboard)

# ==================== ADMIN - CATEGORIES ====================

@router.callback_query(F.data == "admin_categories")
async def callback_admin_categories(callback: CallbackQuery):
    """Admin categories management"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    categories = db.get_categories(active_only=False)
    
    text = f"{Emoji.CATEGORY} <b>Manage Categories</b>\n\n"
    text += f"Total Categories: {len(categories)}\n"
    text += f"Active: {sum(1 for c in categories if c['is_active'])}\n\n"
    text += f"<i>Select a category or add new:</i>"
    
    keyboard = Keyboards.admin_categories(categories)
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "admin_add_category")
async def callback_admin_add_category(callback: CallbackQuery, state: FSMContext):
    """Start adding category"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    text = f"{Emoji.ADD} <b>Add New Category</b>\n\n"
    text += f"Please enter the category name:\n\n"
    text += f"<i>Example: Gaming Accounts, Gift Cards, etc.</i>"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(CategoryStates.entering_name)

@router.message(CategoryStates.entering_name)
async def process_category_name(message: Message, state: FSMContext):
    """Process category name"""
    if not is_admin(message.from_user.id):
        return
    
    category_name = message.text.strip()
    
    if len(category_name) < 2 or len(category_name) > 100:
        await message.answer(
            f"{Emoji.CROSS} Category name must be between 2 and 100 characters!",
            reply_markup=Keyboards.cancel_button()
        )
        return
    
    await state.update_data(category_name=category_name)
    
    text = f"{Emoji.EDIT} <b>Add Category Description</b>\n\n"
    text += f"Category: <b>{category_name}</b>\n\n"
    text += f"Enter a description or send /skip to continue without description:"
    
    await message.answer(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(CategoryStates.entering_description)

@router.message(CategoryStates.entering_description)
async def process_category_description(message: Message, state: FSMContext):
    """Process category description and create"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    description = None if message.text == "/skip" else message.text.strip()
    
    # Create category
    category_id = db.add_category(
        name=data['category_name'],
        description=description
    )
    
    if category_id:
        text = f"{Emoji.CHECK} <b>Category Created Successfully!</b>\n\n"
        text += f"Name: <b>{data['category_name']}</b>\n"
        if description:
            text += f"Description: {description}\n"
        text += f"\n<i>Category ID: {category_id}</i>"
        
        await message.answer(
            text,
            reply_markup=Keyboards.back_button("admin_categories", "Back to Categories")
        )
    else:
        await message.answer(
            f"{Emoji.CROSS} Failed to create category. Name might already exist!",
            reply_markup=Keyboards.back_button("admin_categories", "Back to Categories")
        )
    
    await state.clear()

@router.callback_query(F.data.startswith("admin_cat_"))
async def callback_admin_category_detail(callback: CallbackQuery):
    """Admin category detail view"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    category_id = int(callback.data.split("_")[2])
    category = db.get_category(category_id)
    
    if not category:
        await callback.answer("Category not found!", show_alert=True)
        return
    
    coupons = db.get_coupons(category_id=category_id, active_only=False)
    
    text = f"{Emoji.CATEGORY} <b>Category Details</b>\n\n"
    text += f"<b>Name:</b> {category['name']}\n"
    text += f"<b>Description:</b> {category.get('description', 'No description')}\n"
    text += f"<b>Coupons:</b> {len(coupons)}\n"
    text += f"<b>Status:</b> {'✅ Active' if category['is_active'] else '❌ Inactive'}\n"
    text += f"<b>Created:</b> {format_datetime(category['created_at'])}\n\n"
    text += f"<i>Select an action:</i>"
    
    keyboard = Keyboards.admin_category_detail(category_id, category['is_active'])
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("admin_toggle_cat_"))
async def callback_admin_toggle_category(callback: CallbackQuery):
    """Toggle category active status"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    category_id = int(callback.data.split("_")[3])
    category = db.get_category(category_id)
    
    if not category:
        await callback.answer("Category not found!", show_alert=True)
        return
    
    new_status = 0 if category['is_active'] else 1
    
    if db.update_category(category_id, is_active=new_status):
        status_text = "activated" if new_status else "deactivated"
        await callback.answer(f"Category {status_text}!", show_alert=True)
        
        # Refresh the detail view
        category = db.get_category(category_id)
        coupons = db.get_coupons(category_id=category_id, active_only=False)
        
        text = f"{Emoji.CATEGORY} <b>Category Details</b>\n\n"
        text += f"<b>Name:</b> {category['name']}\n"
        text += f"<b>Description:</b> {category.get('description', 'No description')}\n"
        text += f"<b>Coupons:</b> {len(coupons)}\n"
        text += f"<b>Status:</b> {'✅ Active' if category['is_active'] else '❌ Inactive'}\n"
        text += f"<b>Created:</b> {format_datetime(category['created_at'])}\n\n"
        text += f"<i>Select an action:</i>"
        
        keyboard = Keyboards.admin_category_detail(category_id, category['is_active'])
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.answer("Failed to update category!", show_alert=True)

@router.callback_query(F.data.startswith("admin_delete_cat_"))
async def callback_admin_delete_category(callback: CallbackQuery):
    """Delete category"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    category_id = int(callback.data.split("_")[3])
    category = db.get_category(category_id)
    
    if not category:
        await callback.answer("Category not found!", show_alert=True)
        return
    
    # Check if category has coupons
    coupons = db.get_coupons(category_id=category_id, active_only=False)
    
    if coupons:
        await callback.answer(
            f"Cannot delete! Category has {len(coupons)} coupon(s).\nDelete coupons first.",
            show_alert=True
        )
        return
    
    if db.delete_category(category_id):
        await callback.answer("Category deleted successfully!", show_alert=True)
        
        # Redirect to categories list
        categories = db.get_categories(active_only=False)
        text = f"{Emoji.CATEGORY} <b>Manage Categories</b>\n\n"
        text += f"Total Categories: {len(categories)}\n"
        text += f"Active: {sum(1 for c in categories if c['is_active'])}\n\n"
        text += f"<i>Select a category or add new:</i>"
        
        keyboard = Keyboards.admin_categories(categories)
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.answer("Failed to delete category!", show_alert=True)

# ==================== ADMIN - COUPONS ====================

@router.callback_query(F.data == "admin_coupons")
async def callback_admin_coupons(callback: CallbackQuery):
    """Admin coupons management"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    coupons = db.get_coupons(active_only=False)
    
    text = f"{Emoji.COUPON} <b>Manage Coupons</b>\n\n"
    text += f"Total Coupons: {len(coupons)}\n"
    text += f"Active: {sum(1 for c in coupons if c['is_active'])}\n\n"
    text += f"<i>Select a coupon or add new:</i>"
    
    keyboard = Keyboards.admin_coupons(coupons)
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "admin_add_coupon")
async def callback_admin_add_coupon(callback: CallbackQuery, state: FSMContext):
    """Start adding coupon - select category first"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    categories = db.get_categories(active_only=True)
    
    if not categories:
        await callback.answer(
            "No active categories! Create a category first.",
            show_alert=True
        )
        return
    
    text = f"{Emoji.ADD} <b>Add New Coupon</b>\n\n"
    text += f"Step 1: Select a category for this coupon:"
    
    keyboard = Keyboards.select_category_for_coupon(categories)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(CouponStates.selecting_category)

@router.callback_query(CouponStates.selecting_category, F.data.startswith("select_cat_"))
async def callback_select_coupon_category(callback: CallbackQuery, state: FSMContext):
    """Category selected, ask for coupon name"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    category_id = int(callback.data.split("_")[2])
    category = db.get_category(category_id)
    
    if not category:
        await callback.answer("Category not found!", show_alert=True)
        return
    
    await state.update_data(category_id=category_id, category_name=category['name'])
    
    text = f"{Emoji.EDIT} <b>Add New Coupon</b>\n\n"
    text += f"Category: <b>{category['name']}</b>\n\n"
    text += f"Step 2: Enter coupon name:\n\n"
    text += f"<i>Example: Netflix Premium 1 Month, Steam $50 Gift Card</i>"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(CouponStates.entering_name)

@router.message(CouponStates.entering_name)
async def process_coupon_name(message: Message, state: FSMContext):
    """Process coupon name, ask for price"""
    if not is_admin(message.from_user.id):
        return
    
    coupon_name = message.text.strip()
    
    if len(coupon_name) < 3 or len(coupon_name) > 200:
        await message.answer(
            f"{Emoji.CROSS} Coupon name must be between 3 and 200 characters!",
            reply_markup=Keyboards.cancel_button()
        )
        return
    
    data = await state.get_data()
    await state.update_data(coupon_name=coupon_name)
    
    text = f"{Emoji.MONEY} <b>Add New Coupon</b>\n\n"
    text += f"Category: <b>{data['category_name']}</b>\n"
    text += f"Name: <b>{coupon_name}</b>\n\n"
    text += f"Step 3: Enter coupon price:\n\n"
    text += f"<i>Enter number only (e.g., 99 or 99.50)</i>"
    
    await message.answer(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(CouponStates.entering_price)

@router.message(CouponStates.entering_price)
async def process_coupon_price(message: Message, state: FSMContext):
    """Process coupon price, ask for description"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            f"{Emoji.CROSS} Invalid price! Please enter a valid number.\n\n"
            f"<i>Example: 99 or 99.50</i>",
            reply_markup=Keyboards.cancel_button()
        )
        return
    
    data = await state.get_data()
    await state.update_data(price=price)
    
    text = f"{Emoji.EDIT} <b>Add New Coupon</b>\n\n"
    text += f"Category: <b>{data['category_name']}</b>\n"
    text += f"Name: <b>{data['coupon_name']}</b>\n"
    text += f"Price: {format_price(price)}\n\n"
    text += f"Step 4: Enter coupon description:\n\n"
    text += f"<i>Or send /skip to continue without description</i>"
    
    await message.answer(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(CouponStates.entering_description)

@router.message(CouponStates.entering_description)
async def process_coupon_description(message: Message, state: FSMContext):
    """Process coupon description and create"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    description = None if message.text == "/skip" else message.text.strip()
    
    # Create coupon
    coupon_id = db.add_coupon(
        category_id=data['category_id'],
        name=data['coupon_name'],
        price=data['price'],
        description=description
    )
    
    if coupon_id:
        text = f"{Emoji.CHECK} <b>Coupon Created Successfully!</b>\n\n"
        text += f"Name: <b>{data['coupon_name']}</b>\n"
        text += f"Category: {data['category_name']}\n"
        text += f"Price: {format_price(data['price'])}\n"
        if description:
            text += f"Description: {description}\n"
        text += f"\nCoupon ID: <code>{coupon_id}</code>\n\n"
        text += f"⚠️ <b>Important:</b> Upload coupon codes using the 'Upload Codes' button!"
        
        await message.answer(
            text,
            reply_markup=Keyboards.back_button("admin_coupons", "Back to Coupons")
        )
    else:
        await message.answer(
            f"{Emoji.CROSS} Failed to create coupon. Please try again.",
            reply_markup=Keyboards.back_button("admin_coupons", "Back to Coupons")
        )
    
    await state.clear()

@router.callback_query(F.data.startswith("admin_cpn_"))
async def callback_admin_coupon_detail(callback: CallbackQuery):
    """Admin coupon detail view"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    coupon_id = int(callback.data.split("_")[2])
    coupon = db.get_coupon(coupon_id)
    
    if not coupon:
        await callback.answer("Coupon not found!", show_alert=True)
        return
    
    text = f"{Emoji.COUPON} <b>Coupon Details</b>\n\n"
    text += f"<b>Name:</b> {coupon['name']}\n"
    text += f"<b>Category:</b> {coupon.get('category_name', 'N/A')}\n"
    text += f"<b>Price:</b> {format_price(coupon['price'])}\n"
    text += f"<b>Description:</b> {coupon.get('description', 'No description')}\n\n"
    text += f"<b>Stock Information:</b>\n"
    text += f"Total Codes: {coupon['stock']}\n"
    text += f"Available: {coupon['available_stock']}\n"
    text += f"Sold: {coupon['sold_count']}\n\n"
    text += f"<b>Settings:</b>\n"
    text += f"Status: {'✅ Active' if coupon['is_active'] else '❌ Inactive'}\n"
    text += f"Featured: {'⭐ Yes' if coupon.get('is_featured') else 'No'}\n"
    text += f"Min Purchase: {coupon.get('min_purchase', 1)}\n"
    text += f"Max Purchase: {coupon.get('max_purchase', 10)}\n\n"
    text += f"<b>Created:</b> {format_datetime(coupon['created_at'])}\n\n"
    text += f"<i>Select an action:</i>"
    
    keyboard = Keyboards.admin_coupon_detail(coupon_id, coupon['is_active'])
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("admin_upload_codes_"))
async def callback_admin_upload_codes(callback: CallbackQuery, state: FSMContext):
    """Start uploading coupon codes"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    coupon_id = int(callback.data.split("_")[3])
    coupon = db.get_coupon(coupon_id)
    
    if not coupon:
        await callback.answer("Coupon not found!", show_alert=True)
        return
    
    text = f"{Emoji.UPLOAD} <b>Upload Coupon Codes</b>\n\n"
    text += f"Coupon: <b>{coupon['name']}</b>\n"
    text += f"Current Available Stock: {coupon['available_stock']}\n\n"
    text += f"<b>Instructions:</b>\n"
    text += f"Send coupon codes in any of these formats:\n\n"
    text += f"1️⃣ One code per line:\n"
    text += f"<code>CODE1\nCODE2\nCODE3</code>\n\n"
    text += f"2️⃣ Comma-separated:\n"
    text += f"<code>CODE1, CODE2, CODE3</code>\n\n"
    text += f"3️⃣ Space-separated:\n"
    text += f"<code>CODE1 CODE2 CODE3</code>\n\n"
    text += f"<i>You can send multiple messages to add more codes</i>"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.cancel_button())
    await state.update_data(coupon_id=coupon_id)
    await state.set_state(CouponStates.uploading_codes)

@router.message(CouponStates.uploading_codes)
async def process_coupon_codes(message: Message, state: FSMContext):
    """Process uploaded coupon codes"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    coupon_id = data['coupon_id']
    
    # Parse codes
    codes = split_codes(message.text)
    
    if not codes:
        await message.answer(
            f"{Emoji.CROSS} No valid codes found! Please try again.\n\n"
            f"<i>Make sure to send actual coupon codes</i>",
            reply_markup=Keyboards.cancel_button()
        )
        return
    
    # Add codes to database
    added, duplicates = db.add_coupon_codes(coupon_id, codes)
    
    text = f"{Emoji.CHECK} <b>Codes Upload Complete!</b>\n\n"
    text += f"✅ Successfully added: <b>{added}</b> new codes\n"
    
    if duplicates > 0:
        text += f"⚠️ Duplicates skipped: {duplicates}\n"
    
    # Get updated coupon info
    coupon = db.get_coupon(coupon_id)
    text += f"\n<b>Updated Stock:</b>\n"
    text += f"Total Available: {coupon['available_stock']}\n"
    text += f"Total Codes: {coupon['stock']}\n\n"
    text += f"<i>Send more codes or go back to coupon details</i>"
    
    # Keep state active for more uploads
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Emoji.CHECK} Done", callback_data=f"admin_cpn_{coupon_id}")],
            [InlineKeyboardButton(text=f"{Emoji.CROSS} Cancel", callback_data="admin_coupons")]
        ])
    )

@router.callback_query(F.data.startswith("admin_toggle_cpn_"))
async def callback_admin_toggle_coupon(callback: CallbackQuery):
    """Toggle coupon active status"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    coupon_id = int(callback.data.split("_")[3])
    coupon = db.get_coupon(coupon_id)
    
    if not coupon:
        await callback.answer("Coupon not found!", show_alert=True)
        return
    
    new_status = 0 if coupon['is_active'] else 1
    
    if db.update_coupon(coupon_id, is_active=new_status):
        status_text = "activated" if new_status else "deactivated"
        await callback.answer(f"Coupon {status_text}!", show_alert=True)
        
        # Refresh the detail view
        coupon = db.get_coupon(coupon_id)
        
        text = f"{Emoji.COUPON} <b>Coupon Details</b>\n\n"
        text += f"<b>Name:</b> {coupon['name']}\n"
        text += f"<b>Category:</b> {coupon.get('category_name', 'N/A')}\n"
        text += f"<b>Price:</b> {format_price(coupon['price'])}\n"
        text += f"<b>Description:</b> {coupon.get('description', 'No description')}\n\n"
        text += f"<b>Stock Information:</b>\n"
        text += f"Total Codes: {coupon['stock']}\n"
        text += f"Available: {coupon['available_stock']}\n"
        text += f"Sold: {coupon['sold_count']}\n\n"
        text += f"<b>Settings:</b>\n"
        text += f"Status: {'✅ Active' if coupon['is_active'] else '❌ Inactive'}\n"
        text += f"Featured: {'⭐ Yes' if coupon.get('is_featured') else 'No'}\n"
        text += f"Min Purchase: {coupon.get('min_purchase', 1)}\n"
        text += f"Max Purchase: {coupon.get('max_purchase', 10)}\n\n"
        text += f"<b>Created:</b> {format_datetime(coupon['created_at'])}\n\n"
        text += f"<i>Select an action:</i>"
        
        keyboard = Keyboards.admin_coupon_detail(coupon_id, coupon['is_active'])
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.answer("Failed to update coupon!", show_alert=True)

@router.callback_query(F.data.startswith("admin_delete_cpn_"))
async def callback_admin_delete_coupon(callback: CallbackQuery):
    """Delete coupon"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    coupon_id = int(callback.data.split("_")[3])
    
    if db.delete_coupon(coupon_id):
        await callback.answer("Coupon deleted successfully!", show_alert=True)
        
        # Redirect to coupons list
        coupons = db.get_coupons(active_only=False)
        text = f"{Emoji.COUPON} <b>Manage Coupons</b>\n\n"
        text += f"Total Coupons: {len(coupons)}\n"
        text += f"Active: {sum(1 for c in coupons if c['is_active'])}\n\n"
        text += f"<i>Select a coupon or add new:</i>"
        
        keyboard = Keyboards.admin_coupons(coupons)
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.answer("Failed to delete coupon!", show_alert=True)

# ==================== ADMIN - ORDERS ====================

@router.callback_query(F.data == "admin_pending_orders")
async def callback_admin_pending_orders(callback: CallbackQuery):
    """View pending orders"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    orders = db.get_orders(status='pending')
    
    if not orders:
        await callback.message.edit_text(
            f"{Emoji.CHECK} No pending orders!",
            reply_markup=Keyboards.back_button("admin_panel", "Admin Panel")
        )
        return
    
    text = f"{Emoji.PENDING} <b>Pending Orders</b>\n\n"
    text += f"Total: {len(orders)}\n\n"
    text += f"<i>Select an order to approve/reject:</i>"
    
    keyboard = Keyboards.admin_orders(orders, filter_type="pending")
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "admin_all_orders")
async def callback_admin_all_orders(callback: CallbackQuery):
    """View all orders"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    orders = db.get_orders()
    
    if not orders:
        await callback.message.edit_text(
            f"{Emoji.CROSS} No orders yet!",
            reply_markup=Keyboards.back_button("admin_panel", "Admin Panel")
        )
        return
    
    text = f"{Emoji.ORDERS} <b>All Orders</b>\n\n"
    text += f"Total: {len(orders)}\n"
    text += f"Pending: {sum(1 for o in orders if o['status'] == 'pending')}\n"
    text += f"Approved: {sum(1 for o in orders if o['status'] in ['approved', 'delivered'])}\n"
    text += f"Rejected: {sum(1 for o in orders if o['status'] == 'rejected')}\n\n"
    text += f"<i>Select an order to view:</i>"
    
    keyboard = Keyboards.admin_orders(orders, filter_type="all")
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("admin_order_"))
async def callback_admin_order_detail(callback: CallbackQuery):
    """Admin order detail view"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    order_id = int(callback.data.split("_")[2])
    order = db.get_order(order_id)
    
    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return
    
    text = format_admin_order_detail(order)
    
    if order['status'] == 'pending':
        keyboard = Keyboards.order_verification(order_id)
    else:
        keyboard = Keyboards.back_button("admin_all_orders", "Back to Orders")
    
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("view_screenshot_"))
async def callback_view_screenshot(callback: CallbackQuery):
    """View payment screenshot"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    order_id = int(callback.data.split("_")[2])
    order = db.get_order(order_id)
    
    if not order or not order.get('screenshot_file_id'):
        await callback.answer("Screenshot not available!", show_alert=True)
        return
    
    try:
        await callback.message.answer_photo(
            photo=order['screenshot_file_id'],
            caption=f"💳 <b>Payment Screenshot - Order #{order_id}</b>\n\n"
                    f"Transaction ID: <code>{order.get('transaction_id', 'N/A')}</code>"
        )
    except Exception as e:
        logger.error(f"Error sending screenshot: {e}")
        await callback.answer("Failed to load screenshot!", show_alert=True)

@router.callback_query(F.data.startswith("approve_order_"))
async def callback_approve_order(callback: CallbackQuery):
    """Approve order and deliver coupons"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback, "Processing approval...")
    
    order_id = int(callback.data.split("_")[2])
    order = db.get_order(order_id)
    
    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return
    
    if order['status'] != 'pending':
        await callback.answer("Order already processed!", show_alert=True)
        return
    
    # Check if enough codes available
    coupon = db.get_coupon(order['coupon_id'])
    if coupon['available_stock'] < order['quantity']:
        await callback.answer(
            f"Not enough codes! Available: {coupon['available_stock']}, Needed: {order['quantity']}",
            show_alert=True
        )
        return
    
    # Approve and deliver
    success = db.approve_order(order_id, order['user_id'])
    
    if success:
        # Get delivered codes
        codes = db.get_order_coupon_codes(order_id)
        
        # Notify user
        user_text = Messages.ORDER_APPROVED.format(
            order_id=order_id,
            coupon_name=coupon['name'],
            codes="\n".join([f"{i}. <code>{c['code']}</code>" for i, c in enumerate(codes, 1)])
        )
        
        try:
            from bot import bot
            await bot.send_message(
                chat_id=order['user_id'],
                text=user_text
            )
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")
        
        await callback.answer("✅ Order approved and codes delivered!", show_alert=True)
        
        # Update admin view
        text = format_admin_order_detail(db.get_order(order_id))
        keyboard = Keyboards.back_button("admin_pending_orders", "Pending Orders")
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.answer("Failed to approve order!", show_alert=True)

@router.callback_query(F.data.startswith("reject_order_"))
async def callback_reject_order(callback: CallbackQuery, state: FSMContext):
    """Start order rejection - ask for reason"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    order_id = int(callback.data.split("_")[2])
    order = db.get_order(order_id)
    
    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return
    
    if order['status'] != 'pending':
        await callback.answer("Order already processed!", show_alert=True)
        return
    
    text = f"{Emoji.REJECTED} <b>Reject Order #{order_id}</b>\n\n"
    text += f"Please enter the rejection reason:\n\n"
    text += f"<i>This will be sent to the user</i>"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.cancel_button())
    await state.update_data(reject_order_id=order_id)
    await state.set_state(OrderStates.entering_reject_reason)

@router.message(OrderStates.entering_reject_reason)
async def process_reject_reason(message: Message, state: FSMContext):
    """Process rejection reason and reject order"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    order_id = data['reject_order_id']
    reason = message.text.strip()
    
    order = db.get_order(order_id)
    
    if not order:
        await message.answer("Order not found!")
        await state.clear()
        return
    
    # Reject order
    success = db.reject_order(order_id, reason)
    
    if success:
        coupon = db.get_coupon(order['coupon_id'])
        
        # Notify user
        user_text = Messages.ORDER_REJECTED.format(
            order_id=order_id,
            coupon_name=coupon['name'],
            reason=reason
        )
        
        try:
            from bot import bot
            await bot.send_message(
                chat_id=order['user_id'],
                text=user_text
            )
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")
        
        await message.answer(
            f"{Emoji.CHECK} Order #{order_id} rejected and user notified.",
            reply_markup=Keyboards.back_button("admin_pending_orders", "Pending Orders")
        )
    else:
        await message.answer(
            f"{Emoji.CROSS} Failed to reject order!",
            reply_markup=Keyboards.back_button("admin_panel", "Admin Panel")
        )
    
    await state.clear()

# ==================== ADMIN - QR CODE ====================

@router.callback_query(F.data == "admin_update_qr")
async def callback_admin_update_qr(callback: CallbackQuery, state: FSMContext):
    """Start QR code update process"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    qr_settings = db.get_qr_settings()
    
    text = f"{Emoji.QR} <b>Update Payment QR Code</b>\n\n"
    
    if qr_settings:
        text += f"<b>Current Settings:</b>\n"
        text += f"UPI ID: <code>{qr_settings.get('upi_id', 'Not set')}</code>\n"
        text += f"QR Code: {'✅ Uploaded' if qr_settings.get('file_id') else '❌ Not uploaded'}\n"
        text += f"Last Updated: {format_datetime(qr_settings.get('updated_at', qr_settings.get('created_at')))}\n\n"
    else:
        text += f"<b>No QR code configured yet</b>\n\n"
    
    text += f"Please send the new QR code image:\n\n"
    text += f"<i>Send as a photo (not file)</i>"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(QRStates.uploading_qr)

@router.message(QRStates.uploading_qr, F.photo)
async def process_qr_upload(message: Message, state: FSMContext):
    """Process QR code image upload"""
    if not is_admin(message.from_user.id):
        return
    
    # Get largest photo size
    file_id = message.photo[-1].file_id
    
    text = f"{Emoji.CHECK} QR code image received!\n\n"
    text += f"Now enter the UPI ID for this QR code:\n\n"
    text += f"<i>Example: merchant@paytm, business@upi</i>\n\n"
    text += f"Or send /skip to keep current UPI ID"
    
    await state.update_data(qr_file_id=file_id)
    await message.answer(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(QRStates.entering_upi)

@router.message(QRStates.uploading_qr)
async def handle_invalid_qr(message: Message):
    """Handle non-photo during QR upload"""
    if not is_admin(message.from_user.id):
        return
    
    await message.answer(
        f"{Emoji.CROSS} Please send a <b>photo</b> of the QR code!\n\n"
        f"<i>Do not send as a file or document</i>",
        reply_markup=Keyboards.cancel_button()
    )

@router.message(QRStates.entering_upi)
async def process_upi_id(message: Message, state: FSMContext):
    """Process UPI ID and save QR settings"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    
    if message.text == "/skip":
        upi_id = None
    else:
        upi_id = message.text.strip()
        if not upi_id or '@' not in upi_id:
            await message.answer(
                f"{Emoji.CROSS} Invalid UPI ID format!\n\n"
                f"Please enter a valid UPI ID (e.g., merchant@paytm)\n\n"
                f"Or send /skip to keep current",
                reply_markup=Keyboards.cancel_button()
            )
            return
    
    # Update QR settings
    success = db.update_qr_settings(
        file_id=data['qr_file_id'],
        upi_id=upi_id
    )
    
    if success:
        text = f"{Emoji.CHECK} <b>QR Code Updated Successfully!</b>\n\n"
        if upi_id:
            text += f"UPI ID: <code>{upi_id}</code>\n"
        text += f"\n<i>All new payment requests will use this QR code</i>"
        
        await message.answer(
            text,
            reply_markup=Keyboards.back_button("admin_panel", "Admin Panel")
        )
    else:
        await message.answer(
            f"{Emoji.CROSS} Failed to update QR settings!",
            reply_markup=Keyboards.back_button("admin_panel", "Admin Panel")
        )
    
    await state.clear()

# ==================== ADMIN - BROADCAST ====================

@router.callback_query(F.data == "admin_broadcast")
async def callback_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start broadcast message"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    users = db.get_all_users(active_only=True)
    
    text = f"{Emoji.BROADCAST} <b>Broadcast Message</b>\n\n"
    text += f"Total active users: {len(users)}\n\n"
    text += f"Enter the message to broadcast:\n\n"
    text += f"<i>HTML formatting supported</i>\n"
    text += f"<i>Use &lt;b&gt;bold&lt;/b&gt;, &lt;i&gt;italic&lt;/i&gt;, etc.</i>"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(BroadcastStates.entering_message)

@router.message(BroadcastStates.entering_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Process and confirm broadcast message"""
    if not is_admin(message.from_user.id):
        return
    
    broadcast_text = message.text or message.caption or ""
    
    if not broadcast_text.strip():
        await message.answer(
            f"{Emoji.CROSS} Please enter a valid message!",
            reply_markup=Keyboards.cancel_button()
        )
        return
    
    await state.update_data(broadcast_message=broadcast_text)
    
    users = db.get_all_users(active_only=True)
    
    preview_text = f"{Emoji.BROADCAST} <b>Broadcast Preview</b>\n\n"
    preview_text += f"Recipients: {len(users)} users\n\n"
    preview_text += f"<b>Message Preview:</b>\n"
    preview_text += "─" * 30 + "\n"
    preview_text += broadcast_text
    preview_text += "\n" + "─" * 30 + "\n\n"
    preview_text += f"<i>Confirm to send?</i>"
    
    await message.answer(
        preview_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Emoji.CHECK} Confirm & Send", callback_data="confirm_broadcast")],
            [InlineKeyboardButton(text=f"{Emoji.CROSS} Cancel", callback_data="admin_panel")]
        ])
    )
    await state.set_state(BroadcastStates.confirming)

@router.callback_query(BroadcastStates.confirming, F.data == "confirm_broadcast")
async def callback_confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    """Execute broadcast"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback, "Sending broadcast...")
    
    data = await state.get_data()
    broadcast_message = data['broadcast_message']
    
    users = db.get_all_users(active_only=True)
    total = len(users)
    successful = 0
    failed = 0
    
    progress_text = f"{Emoji.BROADCAST} <b>Broadcasting...</b>\n\n"
    progress_text += f"Total: {total}\n"
    progress_text += f"Progress: 0/{total}"
    
    progress_msg = await callback.message.edit_text(progress_text)
    
    from bot import bot
    
    for i, user in enumerate(users, 1):
        try:
            await bot.send_message(
                chat_id=user['user_id'],
                text=broadcast_message,
                disable_web_page_preview=True
            )
            successful += 1
        except Exception as e:
            logger.error(f"Failed to send to {user['user_id']}: {e}")
            failed += 1
        
        # Update progress every 10 users
        if i % 10 == 0 or i == total:
            try:
                await progress_msg.edit_text(
                    f"{Emoji.BROADCAST} <b>Broadcasting...</b>\n\n"
                    f"Total: {total}\n"
                    f"Progress: {i}/{total}\n"
                    f"✅ Successful: {successful}\n"
                    f"❌ Failed: {failed}"
                )
            except:
                pass
        
        # Small delay to avoid rate limits
        await asyncio.sleep(0.05)
    
    # Save broadcast record
    db.add_broadcast(
        sent_by=callback.from_user.id,
        message=broadcast_message,
        total_users=total,
        successful=successful,
        failed=failed
    )
    
    final_text = f"{Emoji.CHECK} <b>Broadcast Complete!</b>\n\n"
    final_text += f"Total Recipients: {total}\n"
    final_text += f"✅ Successfully sent: {successful}\n"
    final_text += f"❌ Failed: {failed}\n"
    final_text += f"Success Rate: {(successful/total*100):.1f}%"
    
    await progress_msg.edit_text(
        final_text,
        reply_markup=Keyboards.back_button("admin_panel", "Admin Panel")
    )
    
    await state.clear()

# ==================== ADMIN - STATISTICS ====================

@router.callback_query(F.data == "admin_stats")
async def callback_admin_stats(callback: CallbackQuery):
    """View detailed statistics"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    stats = db.get_statistics()
    
    text = f"{Emoji.STATS} <b>Bot Statistics</b>\n\n"
    
    text += f"<b>👥 Users</b>\n"
    text += f"Total: {stats.get('total_users', 0)}\n"
    text += f"Active: {stats.get('total_users', 0)}\n\n"
    
    text += f"<b>📁 Categories</b>\n"
    text += f"Total: {stats.get('total_categories', 0)}\n\n"
    
    text += f"<b>🎫 Coupons</b>\n"
    text += f"Total: {stats.get('total_coupons', 0)}\n\n"
    
    text += f"<b>📦 Orders</b>\n"
    text += f"Total: {stats.get('total_orders', 0)}\n"
    text += f"⏳ Pending: {stats.get('pending_orders', 0)}\n"
    text += f"✅ Approved: {stats.get('approved_orders', 0)}\n\n"
    
    text += f"<b>💰 Revenue</b>\n"
    text += f"Total: {format_price(stats.get('total_revenue', 0))}\n"
    text += f"Today: {format_price(stats.get('today_revenue', 0))}\n\n"
    
    text += f"<b>📊 Today's Activity</b>\n"
    text += f"Orders: {stats.get('today_orders', 0)}\n"
    text += f"Revenue: {format_price(stats.get('today_revenue', 0))}"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.back_button("admin_panel", "Admin Panel")
    )

# ==================== ADMIN - USERS ====================

@router.callback_query(F.data == "admin_users")
async def callback_admin_users(callback: CallbackQuery):
    """View all users"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    users = db.get_all_users(active_only=False)
    
    text = f"{Emoji.USER} <b>User Management</b>\n\n"
    text += f"Total Users: {len(users)}\n"
    text += f"Active: {sum(1 for u in users if not u['is_blocked'])}\n"
    text += f"Blocked: {sum(1 for u in users if u['is_blocked'])}\n\n"
    
    # Show recent users (last 10)
    recent_users = sorted(users, key=lambda x: x['joined_at'], reverse=True)[:10]
    
    text += f"<b>Recent Users:</b>\n"
    for user in recent_users:
        username = f"@{user['username']}" if user['username'] else "No username"
        text += f"• {user['first_name']} ({username})\n"
        text += f"  ID: <code>{user['user_id']}</code>\n"
        text += f"  Joined: {format_datetime(user['joined_at'])}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.back_button("admin_panel", "Admin Panel")
    )

# ==================== CANCEL OPERATIONS ====================

@router.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel any ongoing operation"""
    await state.clear()
    await safe_answer_callback(callback, "Operation cancelled")
    
    if is_admin(callback.from_user.id):
        await callback.message.edit_text(
            f"{Emoji.CROSS} Operation cancelled",
            reply_markup=Keyboards.back_button("admin_panel", "Admin Panel")
        )
    else:
        await callback.message.edit_text(
            f"{Emoji.CROSS} Operation cancelled",
            reply_markup=Keyboards.back_button("main_menu", "Main Menu")
        )

# ==================== ERROR HANDLER ====================

@router.errors()
async def error_handler(event, exception):
    """Global error handler"""
    logger.error(f"Error: {exception}", exc_info=True)
    
    try:
        if hasattr(event, 'update') and event.update.callback_query:
            await event.update.callback_query.answer(
                "An error occurred. Please try again.",
                show_alert=True
            )
        elif hasattr(event, 'update') and event.update.message:
            await event.update.message.answer(
                f"{Emoji.CROSS} An error occurred. Please try again or contact admin."
            )
    except:
        pass