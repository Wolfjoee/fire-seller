"""
All Bot Handlers - Commands and Callbacks
"""
import asyncio
import logging
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from config import Config, Emoji, Messages
from database import db
from keyboards import Keyboards
from utils import *
from states import *

logger = logging.getLogger(__name__)

# Create router
router = Router()

# ==================== START & HELP ====================

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Start command handler"""
    await state.clear()
    
    # Add user to database
    db.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    welcome_text = Messages.WELCOME.format(emoji=Emoji.FIRE)
    keyboard = Keyboards.main_menu(is_admin=is_admin(message.from_user.id))
    
    await message.answer(welcome_text, reply_markup=keyboard)

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Help command handler"""
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

# ==================== BROWSE CATEGORIES ====================

@router.message(Command("browse"))
async def cmd_browse(message: Message, state: FSMContext):
    """Browse categories command"""
    await state.clear()
    categories = db.get_categories(active_only=True)
    
    if not categories:
        await message.answer(f"{Emoji.CROSS} No categories available yet.")
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
        await callback.message.edit_text(
            f"{Emoji.CROSS} No coupons available in this category yet.",
            reply_markup=Keyboards.back_button("browse_categories", "Back to Categories")
        )
        return
    
    text = f"{category['icon']} <b>{category['name']}</b>\n\n"
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
    text += f"2️⃣ Pay {format_price(total_price)} to {qr_settings.get('upi_id', Config.DEFAULT_UPI_ID)}\n"
    text += f"3️⃣ Take a screenshot of payment confirmation\n"
    text += f"4️⃣ Click 'I've Paid' and submit transaction ID\n\n"
    text += f"⚠️ <i>Note: Order will be processed after admin verification</i>"
    
    # Save order data temporarily
    await state.update_data(
        coupon_id=coupon_id,
        quantity=quantity,
        unit_price=coupon['price'],
        total_price=total_price
    )
    await state.set_state(OrderStates.entering_transaction_id)
    
    # Send QR code if available
    if qr_settings and qr_settings.get('file_id'):
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=qr_settings['file_id'],
                caption=text,
                reply_markup=Keyboards.payment_confirmation(0)
            )
        except:
            await callback.message.edit_text(
                text + f"\n\n{Emoji.CROSS} QR code unavailable. Contact admin.",
                reply_markup=Keyboards.payment_confirmation(0)
            )
    else:
        await callback.message.edit_text(
            text + f"\n\n{Emoji.CROSS} QR code not set. Contact admin.",
            reply_markup=Keyboards.payment_confirmation(0)
        )

@router.callback_query(F.data.startswith("submit_payment_"))
async def callback_submit_payment(callback: CallbackQuery, state: FSMContext):
    """Request transaction ID from user"""
    await safe_answer_callback(callback)
    
    text = f"{Emoji.UPLOAD} <b>Submit Payment Proof</b>\n\n"
    text += f"Please send your <b>Transaction ID</b> (UTR number)\n\n"
    text += f"Format: 12-digit alphanumeric code\n"
    text += f"Example: <code>123456789012</code>\n\n"
    text += f"<i>Then upload your payment screenshot</i>"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(OrderStates.entering_transaction_id)

@router.message(OrderStates.entering_transaction_id)
async def process_transaction_id(message: Message, state: FSMContext):
    """Process transaction ID input"""
    transaction_id = message.text.strip().upper()
    
    if not validate_transaction_id(transaction_id):
        await message.answer(
            f"{Emoji.CROSS} Invalid transaction ID format!\n\n"
            f"Please send a valid 10-20 character alphanumeric code.",
            reply_markup=Keyboards.cancel_button()
        )
        return
    
    # Check for duplicate transaction ID
    existing_orders = db.get_orders()
    if any(order['transaction_id'] == transaction_id for order in existing_orders):
        await message.answer(
            f"{Emoji.CROSS} This transaction ID has already been used!\n\n"
            f"Please send a different transaction ID or contact admin if this is an error.",
            reply_markup=Keyboards.cancel_button()
        )
        return
    
    await state.update_data(transaction_id=transaction_id)
    
    text = f"{Emoji.CHECK} Transaction ID saved!\n\n"
    text += f"Now please upload your <b>payment screenshot</b>.\n\n"
    text += f"<i>Send the screenshot as a photo</i>"
    
    await message.answer(text, reply_markup=Keyboards.cancel_button())
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
        unit_price=data['unit_price'],
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
    
    # Get order and coupon details
    order = db.get_order(order_id)
    coupon = db.get_coupon(data['coupon_id'])
    
    # Notify user
    user_text = Messages.ORDER_CREATED.format(
        order_id=order_id,
        coupon_name=coupon['name'],
        quantity=data['quantity'],
        currency=Config.CURRENCY,
        total=data['total_price']
    )
    
    await message.answer(user_text, reply_markup=Keyboards.back_button("main_menu", "Main Menu"))
    
    # Notify all admins
    admin_text = f"{Emoji.NEW} <b>New Order Received!</b>\n\n"
    admin_text += format_admin_order_detail(order)
    
    for admin_id in Config.ADMIN_IDS:
        try:
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=screenshot_file_id,
                caption=admin_text,
                reply_markup=Keyboards.order_verification(order_id)
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")
    
    await state.clear()

@router.message(OrderStates.uploading_screenshot)
async def invalid_screenshot(message: Message):
    """Handle invalid screenshot upload"""
    await message.answer(
        f"{Emoji.CROSS} Please send a valid photo (screenshot).\n\n"
        f"<i>Use the photo attachment button to send your screenshot</i>",
        reply_markup=Keyboards.cancel_button()
    )

# ==================== MY ORDERS ====================

@router.message(Command("myorders"))
async def cmd_my_orders(message: Message):
    """View user's orders"""
    orders = db.get_orders(user_id=message.from_user.id)
    
    if not orders:
        await message.answer(
            f"{Emoji.CROSS} You haven't placed any orders yet.\n\n"
            f"Browse coupons and make your first purchase!",
            reply_markup=Keyboards.back_button("browse_categories", "Browse Coupons")
        )
        return
    
    text = f"{Emoji.ORDERS} <b>My Orders</b>\n\n"
    text += f"Total Orders: {len(orders)}\n"
    text += f"Pending: {sum(1 for o in orders if o['status'] == 'pending')}\n"
    text += f"Approved: {sum(1 for o in orders if o['status'] in ['approved', 'delivered'])}\n\n"
    text += f"<i>Select an order to view details:</i>"
    
    keyboard = Keyboards.my_orders_menu(orders)
    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "my_orders")
async def callback_my_orders(callback: CallbackQuery):
    """View user's orders callback"""
    await safe_answer_callback(callback)
    
    orders = db.get_orders(user_id=callback.from_user.id)
    
    if not orders:
        await callback.message.edit_text(
            f"{Emoji.CROSS} You haven't placed any orders yet.\n\n"
            f"Browse coupons and make your first purchase!",
            reply_markup=Keyboards.back_button("browse_categories", "Browse Coupons")
        )
        return
    
    text = f"{Emoji.ORDERS} <b>My Orders</b>\n\n"
    text += f"Total Orders: {len(orders)}\n"
    text += f"Pending: {sum(1 for o in orders if o['status'] == 'pending')}\n"
    text += f"Approved: {sum(1 for o in orders if o['status'] in ['approved', 'delivered'])}\n\n"
    text += f"<i>Select an order to view details:</i>"
    
    keyboard = Keyboards.my_orders_menu(orders)
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("order_detail_"))
async def callback_order_detail(callback: CallbackQuery):
    """View order detail"""
    await safe_answer_callback(callback)
    
    order_id = int(callback.data.split("_")[2])
    order = db.get_order(order_id)
    
    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return
    
    # Verify ownership
    if order['user_id'] != callback.from_user.id and not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    text = format_order_detail(order)
    keyboard = Keyboards.order_detail(order)
    
    await callback.message.edit_text(text, reply_markup=keyboard)

# ==================== ADMIN PANEL ====================

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Admin panel command"""
    if not is_admin(message.from_user.id):
        await message.answer(f"{Emoji.CROSS} Access denied! Admin only.")
        return
    
    await state.clear()
    
    stats = db.get_statistics()
    
    text = f"{Emoji.ADMIN} <b>Admin Panel</b>\n\n"
    text += f"Welcome, Admin!\n\n"
    text += f"<b>Quick Stats:</b>\n"
    text += f"👥 Users: {stats.get('total_users', 0)}\n"
    text += f"📦 Pending Orders: {stats.get('pending_orders', 0)}\n"
    text += f"💰 Today's Revenue: {format_price(stats.get('today_revenue', 0))}\n\n"
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
    text += f"Welcome, Admin!\n\n"
    text += f"<b>Quick Stats:</b>\n"
    text += f"👥 Users: {stats.get('total_users', 0)}\n"
    text += f"📦 Pending Orders: {stats.get('pending_orders', 0)}\n"
    text += f"💰 Today's Revenue: {format_price(stats.get('today_revenue', 0))}\n\n"
    text += f"<i>Select an option below:</i>"
    
    keyboard = Keyboards.admin_panel()
    await callback.message.edit_text(text, reply_markup=keyboard)

# ==================== ADMIN - STATISTICS ====================

@router.callback_query(F.data == "admin_stats")
async def callback_admin_stats(callback: CallbackQuery):
    """Show bot statistics"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    stats = db.get_statistics()
    text = format_statistics(stats)
    
    keyboard = Keyboards.back_button("admin_panel", "Admin Panel")
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
    text += f"Total Categories: {len(categories)}\n\n"
    text += f"<i>Select a category or add new one:</i>"
    
    keyboard = Keyboards.admin_categories(categories)
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "admin_add_category")
async def callback_admin_add_category(callback: CallbackQuery, state: FSMContext):
    """Start adding new category"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    text = f"{Emoji.ADD} <b>Add New Category</b>\n\n"
    text += f"Please send the category name:"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(CategoryStates.entering_name)

@router.message(CategoryStates.entering_name)
async def process_category_name(message: Message, state: FSMContext):
    """Process new category name"""
    if not is_admin(message.from_user.id):
        return
    
    category_name = message.text.strip()
    
    if len(category_name) < 2:
        await message.answer(
            f"{Emoji.CROSS} Category name too short! Please send a valid name.",
            reply_markup=Keyboards.cancel_button()
        )
        return
    
    await state.update_data(category_name=category_name)
    
    text = f"{Emoji.EDIT} <b>Add Category Description</b>\n\n"
    text += f"Category: <b>{category_name}</b>\n\n"
    text += f"Please send a description (or /skip):"
    
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
    category_id = db.add_category(data['category_name'], description)
    
    if category_id:
        await message.answer(
            f"{Emoji.CHECK} Category <b>{data['category_name']}</b> created successfully!",
            reply_markup=Keyboards.back_button("admin_categories", "Back to Categories")
        )
    else:
        await message.answer(
            f"{Emoji.CROSS} Failed to create category. Name might already exist.",
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
    text += f"<b>Icon:</b> {category.get('icon', '📁')}\n"
    text += f"<b>Status:</b> {'✅ Active' if category['is_active'] else '❌ Inactive'}\n"
    text += f"<b>Total Coupons:</b> {len(coupons)}\n"
    text += f"<b>Created:</b> {format_datetime(category['created_at'])}\n\n"
    text += f"<i>Select an action:</i>"
    
    keyboard = Keyboards.admin_category_detail(category_id)
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("admin_delete_cat_"))
async def callback_admin_delete_category(callback: CallbackQuery):
    """Delete category"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    category_id = int(callback.data.split("_")[3])
    
    if db.delete_category(category_id):
        await callback.answer("Category deleted successfully!", show_alert=True)
        # Redirect to categories list
        categories = db.get_categories(active_only=False)
        text = f"{Emoji.CATEGORY} <b>Manage Categories</b>\n\nTotal Categories: {len(categories)}"
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
    text += f"Total Coupons: {len(coupons)}\n\n"
    text += f"<i>Select a coupon or add new one:</i>"
    
    keyboard = Keyboards.admin_coupons(coupons)
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "admin_add_coupon")
async def callback_admin_add_coupon(callback: CallbackQuery, state: FSMContext):
    """Start adding new coupon - select category"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    categories = db.get_categories(active_only=True)
    
    if not categories:
        await callback.answer("Please create a category first!", show_alert=True)
        return
    
    text = f"{Emoji.ADD} <b>Add New Coupon</b>\n\n"
    text += f"First, select a category:\n\n"
    
    # Create category selection buttons
    buttons = [
        [InlineKeyboardButton(text=f"{cat['icon']} {cat['name']}", callback_data=f"newcpn_cat_{cat['id']}")]
        for cat in categories
    ]
    buttons.append([InlineKeyboardButton(text=f"{Emoji.CROSS} Cancel", callback_data="admin_coupons")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(CouponStates.selecting_category)

@router.callback_query(CouponStates.selecting_category, F.data.startswith("newcpn_cat_"))
async def callback_new_coupon_category(callback: CallbackQuery, state: FSMContext):
    """Category selected for new coupon"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    category_id = int(callback.data.split("_")[2])
    await state.update_data(category_id=category_id)
    
    text = f"{Emoji.EDIT} <b>Add Coupon - Enter Name</b>\n\n"
    text += f"Please send the coupon name:"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(CouponStates.entering_name)

@router.message(CouponStates.entering_name)
async def process_coupon_name(message: Message, state: FSMContext):
    """Process new coupon name"""
    if not is_admin(message.from_user.id):
        return
    
    coupon_name = message.text.strip()
    
    if len(coupon_name) < 3:
        await message.answer(
            f"{Emoji.CROSS} Coupon name too short! Please send a valid name.",
            reply_markup=Keyboards.cancel_button()
        )
        return
    
    await state.update_data(coupon_name=coupon_name)
    
    text = f"{Emoji.MONEY} <b>Add Coupon - Enter Price</b>\n\n"
    text += f"Coupon: <b>{coupon_name}</b>\n\n"
    text += f"Please send the price (numbers only):\n"
    text += f"Example: 99.99"
    
    await message.answer(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(CouponStates.entering_price)

@router.message(CouponStates.entering_price)
async def process_coupon_price(message: Message, state: FSMContext):
    """Process coupon price"""
    if not is_admin(message.from_user.id):
        return
    
    try:
        price = float(message.text.strip())
        if price <= 0:
            raise ValueError()
    except:
        await message.answer(
            f"{Emoji.CROSS} Invalid price! Please send a valid number.",
            reply_markup=Keyboards.cancel_button()
        )
        return
    
    await state.update_data(price=price)
    
    text = f"{Emoji.EDIT} <b>Add Coupon - Enter Description</b>\n\n"
    text += f"Please send a description (or /skip):"
    
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
        text += f"Price: {format_price(data['price'])}\n"
        text += f"ID: <code>{coupon_id}</code>\n\n"
        text += f"⚠️ <i>Remember to upload coupon codes using /bulkupload or the admin panel!</i>"
        
        await message.answer(text, reply_markup=Keyboards.back_button("admin_coupons", "Back to Coupons"))
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
    text += f"<b>Description:</b> {coupon.get('description', 'No description')}\n"
    text += f"<b>Total Stock:</b> {coupon['stock']}\n"
    text += f"<b>Available:</b> {coupon['available_stock']}\n"
    text += f"<b>Sold:</b> {coupon['sold_count']}\n"
    text += f"<b>Status:</b> {'✅ Active' if coupon['is_active'] else '❌ Inactive'}\n"
    text += f"<b>Featured:</b> {'⭐ Yes' if coupon.get('is_featured') else 'No'}\n"
    text += f"<b>Created:</b> {format_datetime(coupon['created_at'])}\n\n"
    text += f"<i>Select an action:</i>"
    
    keyboard = Keyboards.admin_coupon_detail(coupon_id)
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
    text += f"Current Stock: {coupon['available_stock']}\n\n"
    text += f"<b>Instructions:</b>\n"
    text += f"Send coupon codes in the following format:\n\n"
    text += f"<code>CODE1\nCODE2\nCODE3</code>\n\n"
    text += f"Or comma-separated:\n"
    text += f"<code>CODE1, CODE2, CODE3</code>\n\n"
    text += f"<i>You can send multiple codes at once</i>"
    
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
            f"{Emoji.CROSS} No valid codes found! Please try again.",
            reply_markup=Keyboards.cancel_button()
        )
        return
    
    # Add codes to database
    added, duplicates = db.add_coupon_codes(coupon_id, codes)
    
    text = f"{Emoji.CHECK} <b>Codes Upload Complete!</b>\n\n"
    text += f"✅ Added: <b>{added}</b> codes\n"
    
    if duplicates > 0:
        text += f"⚠️ Duplicates skipped: {duplicates}\n"
    
    text += f"\n<b>Total Available Stock:</b> {added + duplicates - duplicates}\n\n"
    text += f"<i>Upload more codes or go back</i>"
    
    await message.answer(
        text,
        reply_markup=Keyboards.back_button(f"admin_cpn_{coupon_id}", "Coupon Details")
    )

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
        text = f"{Emoji.COUPON} <b>Manage Coupons</b>\n\nTotal Coupons: {len(coupons)}"
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
    text += f"Approved: {sum(1 for o in orders if o['status'] in ['approved', 'delivered'])}\n\n"
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
            caption=f"Payment Screenshot - Order #{order_id}"
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
    
    await safe_answer_callback(callback, "Processing order approval...")
    
    order_id = int(callback.data.split("_")[2])
    order = db.get_order(order_id)
    
    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return
    
    if order['status'] != 'pending':
        await callback.answer("Order already processed!", show_alert=True)
        return
    
    # Get available coupon codes
    codes = db.get_available_codes(order['coupon_id'], order['quantity'])
    
    if len(codes) < order['quantity']:
        await callback.answer(
            f"Not enough coupon codes available! Need {order['quantity']}, have {len(codes)}",
            show_alert=True
        )
        return
    
    # Update order status
    db.update_order_status(order_id, 'approved', approved_by=callback.from_user.id)
    
    # Mark codes as used
    db.mark_codes_used(codes, order['user_id'], order_id)
    
    # Deliver order
    db.deliver_order(order_id)
    
    # Notify user
    user_text = Messages.ORDER_APPROVED.format(
        order_id=order_id,
        coupon_name=order['coupon_name'],
        codes=format_codes_list(codes)
    )
    
    try:
        await callback.bot.send_message(
            chat_id=order['user_id'],
            text=user_text
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")
    
    # Update admin message
    await callback.message.edit_text(
        f"{Emoji.CHECK} <b>Order #{order_id} Approved & Delivered!</b>\n\n"
        f"Coupon codes sent to user.\n"
        f"Quantity: {order['quantity']}\n"
        f"Total: {format_price(order['total_price'])}",
        reply_markup=Keyboards.back_button("admin_pending_orders", "Pending Orders")
    )

@router.callback_query(F.data.startswith("reject_order_"))
async def callback_reject_order(callback: CallbackQuery, state: FSMContext):
    """Start order rejection - ask for reason"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    order_id = int(callback.data.split("_")[2])
    
    text = f"{Emoji.CROSS} <b>Reject Order #{order_id}</b>\n\n"
    text += f"Please send the rejection reason:"
    
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
    
    # Update order status
    db.update_order_status(order_id, 'rejected', reject_reason=reason)
    
    # Notify user
    user_text = Messages.ORDER_REJECTED.format(
        order_id=order_id,
        coupon_name=order['coupon_name'],
        reason=reason
    )
    
    try:
        await message.bot.send_message(
            chat_id=order['user_id'],
            text=user_text
        )
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")
    
    await message.answer(
        f"{Emoji.CHECK} Order #{order_id} rejected.\nUser has been notified.",
        reply_markup=Keyboards.back_button("admin_pending_orders", "Pending Orders")
    )
    
    await state.clear()

# ==================== ADMIN - QR CODE ====================

@router.callback_query(F.data == "admin_update_qr")
async def callback_admin_update_qr(callback: CallbackQuery, state: FSMContext):
    """Update QR code"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    qr_settings = db.get_qr_settings()
    
    text = f"{Emoji.QR} <b>Update Payment QR Code</b>\n\n"
    text += f"<b>Current UPI ID:</b> <code>{qr_settings.get('upi_id', 'Not set')}</code>\n\n"
    text += f"Please send the new QR code image:"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(QRStates.uploading_qr)

@router.message(QRStates.uploading_qr, F.photo)
async def process_qr_upload(message: Message, state: FSMContext):
    """Process QR code upload"""
    if not is_admin(message.from_user.id):
        return
    
    # Get largest photo
    file_id = message.photo[-1].file_id
    
    await state.update_data(qr_file_id=file_id)
    
    text = f"{Emoji.CHECK} QR code uploaded!\n\n"
    text += f"Now send the UPI ID (or /skip to keep current):"
    
    await message.answer(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(QRStates.entering_upi)

@router.message(QRStates.entering_upi)
async def process_qr_upi(message: Message, state: FSMContext):
    """Process UPI ID and save QR settings"""
    if not is_admin(message.from_user.id):
        return
    
    data = await state.get_data()
    upi_id = None
    
    if message.text != "/skip":
        upi_id = message.text.strip()
        if not validate_upi_id(upi_id):
            await message.answer(
                f"{Emoji.CROSS} Invalid UPI ID format!\n\n"
                f"Example: merchant@upi\n\n"
                f"Please try again:",
                reply_markup=Keyboards.cancel_button()
            )
            return
    
    # Update QR settings
    if db.update_qr_settings(file_id=data['qr_file_id'], upi_id=upi_id):
        text = f"{Emoji.CHECK} <b>QR Code Updated Successfully!</b>\n\n"
        if upi_id:
            text += f"UPI ID: <code>{upi_id}</code>\n\n"
        text += f"New QR code is now active for all payments."
        
        await message.answer(text, reply_markup=Keyboards.back_button("admin_panel", "Admin Panel"))
    else:
        await message.answer(
            f"{Emoji.CROSS} Failed to update QR code!",
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
    text += f"Total Active Users: <b>{len(users)}</b>\n\n"
    text += f"Send the message you want to broadcast:\n\n"
    text += f"<i>You can use HTML formatting</i>"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.cancel_button())
    await state.set_state(BroadcastStates.entering_message)

@router.message(BroadcastStates.entering_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Process broadcast message"""
    if not is_admin(message.from_user.id):
        return
    
    broadcast_text = message.text or message.caption
    
    if not broadcast_text:
        await message.answer(
            f"{Emoji.CROSS} Please send a text message!",
            reply_markup=Keyboards.cancel_button()
        )
        return
    
    await state.update_data(broadcast_message=broadcast_text)
    
    users = db.get_all_users(active_only=True)
    
    text = f"{Emoji.BROADCAST} <b>Confirm Broadcast</b>\n\n"
    text += f"<b>Recipients:</b> {len(users)} users\n\n"
    text += f"<b>Message Preview:</b>\n{broadcast_text}\n\n"
    text += f"⚠️ Are you sure you want to send this to all users?"
    
    keyboard = Keyboards.confirm_action("broadcast", "send")
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(BroadcastStates.confirming)

@router.callback_query(BroadcastStates.confirming, F.data == "confirm_broadcast_send")
async def callback_confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    """Execute broadcast"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback, "Sending broadcast...")
    
    data = await state.get_data()
    broadcast_text = data['broadcast_message']
    
    users = db.get_all_users(active_only=True)
    
    await callback.message.edit_text(
        f"{Emoji.BROADCAST} <b>Broadcasting...</b>\n\n"
        f"Sending to {len(users)} users...\n\n"
        f"<i>Please wait...</i>"
    )
    
    successful = 0
    failed = 0
    
    for user in users:
        try:
            await callback.bot.send_message(
                chat_id=user['user_id'],
                text=f"{Emoji.BROADCAST} <b>Announcement</b>\n\n{broadcast_text}"
            )
            successful += 1
            await asyncio.sleep(0.05)  # Rate limiting
        except Exception as e:
            logger.error(f"Failed to send to {user['user_id']}: {e}")
            failed += 1
    
    # Save broadcast record
    db.add_broadcast(
        sent_by=callback.from_user.id,
        message=broadcast_text,
        total_users=len(users),
        successful=successful,
        failed=failed
    )
    
    result_text = f"{Emoji.CHECK} <b>Broadcast Complete!</b>\n\n"
    result_text += f"✅ Sent: <b>{successful}</b>\n"
    result_text += f"❌ Failed: <b>{failed}</b>\n"
    result_text += f"📊 Total: <b>{len(users)}</b>"
    
    await callback.message.edit_text(
        result_text,
        reply_markup=Keyboards.back_button("admin_panel", "Admin Panel")
    )
    
    await state.clear()

# ==================== ADMIN - USERS ====================

@router.callback_query(F.data == "admin_users")
async def callback_admin_users(callback: CallbackQuery):
    """View all users"""
    if not is_admin(callback.from_user.id):
        await callback.answer("Access denied!", show_alert=True)
        return
    
    await safe_answer_callback(callback)
    
    users = db.get_all_users()
    active_users = [u for u in users if not u['is_blocked']]
    
    text = f"{Emoji.USER} <b>User Management</b>\n\n"
    text += f"Total Users: <b>{len(users)}</b>\n"
    text += f"Active: <b>{len(active_users)}</b>\n"
    text += f"Blocked: <b>{len(users) - len(active_users)}</b>\n\n"
    
    # Show recent users
    recent = sorted(users, key=lambda x: x['joined_at'], reverse=True)[:10]
    text += f"<b>Recent Users:</b>\n"
    for user in recent:
        username = f"@{user['username']}" if user.get('username') else user.get('first_name', 'Unknown')
        text += f"• {username} - {format_datetime(user['joined_at'])}\n"
    
    keyboard = Keyboards.back_button("admin_panel", "Admin Panel")
    await callback.message.edit_text(text, reply_markup=keyboard)

# ==================== COMMON CALLBACKS ====================

@router.callback_query(F.data == "cancel_action")
async def callback_cancel_action(callback: CallbackQuery, state: FSMContext):
    """Cancel current action"""
    await state.clear()
    await safe_answer_callback(callback, "Action cancelled")
    
    if is_admin(callback.from_user.id):
        keyboard = Keyboards.admin_panel()
        text = f"{Emoji.ADMIN} <b>Admin Panel</b>\n\nAction cancelled. Select an option:"
    else:
        keyboard = Keyboards.main_menu()
        text = f"{Emoji.HOME} <b>Main Menu</b>\n\nAction cancelled. What would you like to do?"
    
    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "noop")
async def callback_noop(callback: CallbackQuery):
    """No operation callback"""
    await safe_answer_callback(callback)

@router.callback_query(F.data == "out_of_stock")
async def callback_out_of_stock(callback: CallbackQuery):
    """Out of stock notification"""
    await callback.answer(
        "This coupon is currently out of stock. Please check back later!",
        show_alert=True
    )

# ==================== COMMAND SHORTCUTS ====================

@router.message(Command("categories"))
async def cmd_categories(message: Message):
    """Quick access to categories"""
    await cmd_browse(message, state=None)

@router.message(Command("pending"))
async def cmd_pending_orders(message: Message):
    """Quick access to pending orders (admin)"""
    if not is_admin(message.from_user.id):
        await message.answer(f"{Emoji.CROSS} Access denied!")
        return
    
    orders = db.get_orders(status='pending')
    
    text = f"{Emoji.PENDING} <b>Pending Orders: {len(orders)}</b>\n\n"
    if orders:
        for order in orders[:5]:
            text += f"#{order['id']} - {order['first_name']} - {format_price(order['total_price'])}\n"
    else:
        text += f"No pending orders!"
    
    keyboard = Keyboards.back_button("admin_panel", "View All")
    await message.answer(text, reply_markup=keyboard)

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Quick access to statistics (admin)"""
    if not is_admin(message.from_user.id):
        await message.answer(f"{Emoji.CROSS} Access denied!")
        return
    
    stats = db.get_statistics()
    text = format_statistics(stats)
    await message.answer(text)