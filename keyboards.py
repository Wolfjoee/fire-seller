"""
Inline Keyboard Builders
"""
from typing import List, Dict, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import Config, Emoji

class Keyboards:
    """Inline keyboard builder utility"""
    
    @staticmethod
    def paginate_buttons(items: List[tuple], page: int, per_page: int, 
                        callback_prefix: str) -> List[List[InlineKeyboardButton]]:
        """Create paginated buttons"""
        total_pages = (len(items) + per_page - 1) // per_page
        start = page * per_page
        end = start + per_page
        
        buttons = []
        
        # Item buttons
        for text, callback_data in items[start:end]:
            buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
        
        # Navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(
                text=f"{Emoji.BACK} Previous",
                callback_data=f"{callback_prefix}_page_{page-1}"
            ))
        if page < total_pages - 1:
            nav_buttons.append(InlineKeyboardButton(
                text=f"Next {Emoji.BACK}",
                callback_data=f"{callback_prefix}_page_{page+1}"
            ))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        return buttons
    
    @staticmethod
    def main_menu(is_admin: bool = False) -> InlineKeyboardMarkup:
        """Main menu keyboard"""
        buttons = [
            [InlineKeyboardButton(text=f"{Emoji.CATEGORY} Browse Categories", callback_data="browse_categories")],
            [InlineKeyboardButton(text=f"{Emoji.ORDERS} My Orders", callback_data="my_orders")],
            [InlineKeyboardButton(text=f"{Emoji.HELP} Help", callback_data="help")]
        ]
        
        if is_admin:
            buttons.append([InlineKeyboardButton(text=f"{Emoji.ADMIN} Admin Panel", callback_data="admin_panel")])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def categories_menu(categories: List[Dict], page: int = 0) -> InlineKeyboardMarkup:
        """Categories browsing menu"""
        items = [
            (f"{cat['icon']} {cat['name']} ({cat['coupon_count']})", f"category_{cat['id']}")
            for cat in categories
        ]
        
        buttons = Keyboards.paginate_buttons(items, page, Config.ITEMS_PER_PAGE, "categories")
        buttons.append([InlineKeyboardButton(text=f"{Emoji.HOME} Main Menu", callback_data="main_menu")])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def coupons_menu(coupons: List[Dict], category_id: int, page: int = 0) -> InlineKeyboardMarkup:
        """Coupons in category menu"""
        items = []
        for coupon in coupons:
            discount_tag = ""
            if coupon.get('original_price') and coupon['original_price'] > coupon['price']:
                discount = int(((coupon['original_price'] - coupon['price']) / coupon['original_price']) * 100)
                discount_tag = f" {Emoji.SALE}{discount}% OFF"
            
            stock_status = f"({coupon['available_stock']} left)" if coupon['available_stock'] < 50 else ""
            featured = f"{Emoji.FIRE} " if coupon.get('is_featured') else ""
            
            items.append((
                f"{featured}{coupon['name']} - {Config.CURRENCY}{coupon['price']:.2f}{discount_tag} {stock_status}",
                f"coupon_{coupon['id']}"
            ))
        
        buttons = Keyboards.paginate_buttons(items, page, Config.ITEMS_PER_PAGE, f"coupons_{category_id}")
        buttons.append([InlineKeyboardButton(text=f"{Emoji.BACK} Back to Categories", callback_data="browse_categories")])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def coupon_detail(coupon: Dict, user_id: int = None) -> InlineKeyboardMarkup:
        """Coupon detail view"""
        buttons = []
        
        # Check stock
        if coupon['available_stock'] > 0:
            buttons.append([InlineKeyboardButton(
                text=f"{Emoji.CART} Purchase Now",
                callback_data=f"purchase_{coupon['id']}"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text=f"{Emoji.CROSS} Out of Stock",
                callback_data="out_of_stock"
            )])
        
        buttons.append([
            InlineKeyboardButton(text=f"{Emoji.BACK} Back", callback_data=f"category_{coupon['category_id']}")
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def quantity_selector(coupon_id: int, max_qty: int) -> InlineKeyboardMarkup:
        """Quantity selection keyboard"""
        buttons = []
        
        # Quantity buttons (1-10 or max available)
        max_display = min(max_qty, Config.MAX_COUPON_PURCHASE)
        
        row = []
        for i in range(1, max_display + 1):
            row.append(InlineKeyboardButton(
                text=str(i),
                callback_data=f"qty_{coupon_id}_{i}"
            ))
            if len(row) == 5:
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        buttons.append([InlineKeyboardButton(
            text=f"{Emoji.BACK} Cancel",
            callback_data=f"coupon_{coupon_id}"
        )])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def payment_confirmation(order_id: int) -> InlineKeyboardMarkup:
        """Payment confirmation keyboard"""
        buttons = [
            [InlineKeyboardButton(
                text=f"{Emoji.CHECK} I've Paid - Submit Transaction ID",
                callback_data=f"submit_payment_{order_id}"
            )],
            [InlineKeyboardButton(
                text=f"{Emoji.CROSS} Cancel Order",
                callback_data=f"cancel_order_{order_id}"
            )]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def order_verification(order_id: int) -> InlineKeyboardMarkup:
        """Admin order verification keyboard"""
        buttons = [
            [
                InlineKeyboardButton(
                    text=f"{Emoji.CHECK} Approve",
                    callback_data=f"approve_order_{order_id}"
                ),
                InlineKeyboardButton(
                    text=f"{Emoji.CROSS} Reject",
                    callback_data=f"reject_order_{order_id}"
                )
            ],
            [InlineKeyboardButton(
                text=f"{Emoji.SEARCH} View Screenshot",
                callback_data=f"view_screenshot_{order_id}"
            )]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def my_orders_menu(orders: List[Dict], page: int = 0) -> InlineKeyboardMarkup:
        """User's orders menu"""
        status_emoji = {
            'pending': Emoji.PENDING,
            'approved': Emoji.APPROVED,
            'rejected': Emoji.REJECTED,
            'delivered': Emoji.CHECK
        }
        
        items = [
            (
                f"#{order['id']} - {order['coupon_name']} ({status_emoji.get(order['status'], '')} {order['status'].title()})",
                f"order_detail_{order['id']}"
            )
            for order in orders
        ]
        
        buttons = Keyboards.paginate_buttons(items, page, Config.ITEMS_PER_PAGE, "my_orders")
        buttons.append([InlineKeyboardButton(text=f"{Emoji.HOME} Main Menu", callback_data="main_menu")])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def order_detail(order: Dict) -> InlineKeyboardMarkup:
        """Order detail view"""
        buttons = []
        
        if order['status'] == 'pending':
            buttons.append([InlineKeyboardButton(
                text=f"{Emoji.PENDING} Waiting for Approval...",
                callback_data="noop"
            )])
        
        buttons.append([InlineKeyboardButton(
            text=f"{Emoji.BACK} Back to Orders",
            callback_data="my_orders"
        )])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # ==================== ADMIN KEYBOARDS ====================
    
    @staticmethod
    def admin_panel() -> InlineKeyboardMarkup:
        """Admin main panel"""
        buttons = [
            [
                InlineKeyboardButton(text=f"{Emoji.CATEGORY} Categories", callback_data="admin_categories"),
                InlineKeyboardButton(text=f"{Emoji.COUPON} Coupons", callback_data="admin_coupons")
            ],
            [
                InlineKeyboardButton(text=f"{Emoji.PENDING} Pending Orders", callback_data="admin_pending_orders"),
                InlineKeyboardButton(text=f"{Emoji.ORDERS} All Orders", callback_data="admin_all_orders")
            ],
            [
                InlineKeyboardButton(text=f"{Emoji.USER} Users", callback_data="admin_users"),
                InlineKeyboardButton(text=f"{Emoji.STATS} Statistics", callback_data="admin_stats")
            ],
            [
                InlineKeyboardButton(text=f"{Emoji.QR} Update QR Code", callback_data="admin_update_qr"),
                InlineKeyboardButton(text=f"{Emoji.BROADCAST} Broadcast", callback_data="admin_broadcast")
            ],
            [InlineKeyboardButton(text=f"{Emoji.HOME} Main Menu", callback_data="main_menu")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def admin_categories(categories: List[Dict], page: int = 0) -> InlineKeyboardMarkup:
        """Admin categories management"""
        items = [
            (f"{cat['icon']} {cat['name']} ({cat['coupon_count']} coupons)", f"admin_cat_{cat['id']}")
            for cat in categories
        ]
        
        buttons = Keyboards.paginate_buttons(items, page, Config.ITEMS_PER_PAGE, "admin_categories")
        buttons.insert(0, [InlineKeyboardButton(
            text=f"{Emoji.ADD} Add New Category",
            callback_data="admin_add_category"
        )])
        buttons.append([InlineKeyboardButton(
            text=f"{Emoji.BACK} Admin Panel",
            callback_data="admin_panel"
        )])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def admin_category_detail(category_id: int) -> InlineKeyboardMarkup:
        """Admin category detail actions"""
        buttons = [
            [
                InlineKeyboardButton(text=f"{Emoji.EDIT} Edit Name", callback_data=f"admin_edit_cat_name_{category_id}"),
                InlineKeyboardButton(text=f"{Emoji.EDIT} Edit Description", callback_data=f"admin_edit_cat_desc_{category_id}")
            ],
            [
                InlineKeyboardButton(text=f"{Emoji.COUPON} View Coupons", callback_data=f"admin_cat_coupons_{category_id}"),
                InlineKeyboardButton(text=f"{Emoji.DELETE} Delete", callback_data=f"admin_delete_cat_{category_id}")
            ],
            [InlineKeyboardButton(text=f"{Emoji.BACK} Back", callback_data="admin_categories")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def admin_coupons(coupons: List[Dict], page: int = 0) -> InlineKeyboardMarkup:
        """Admin coupons management"""
        items = [
            (f"{c['name']} - {Config.CURRENCY}{c['price']} (Stock: {c['available_stock']})", f"admin_cpn_{c['id']}")
            for c in coupons
        ]
        
        buttons = Keyboards.paginate_buttons(items, page, Config.ITEMS_PER_PAGE, "admin_coupons")
        buttons.insert(0, [InlineKeyboardButton(
            text=f"{Emoji.ADD} Add New Coupon",
            callback_data="admin_add_coupon"
        )])
        buttons.append([InlineKeyboardButton(
            text=f"{Emoji.BACK} Admin Panel",
            callback_data="admin_panel"
        )])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def admin_coupon_detail(coupon_id: int) -> InlineKeyboardMarkup:
        """Admin coupon detail actions"""
        buttons = [
            [
                InlineKeyboardButton(text=f"{Emoji.EDIT} Edit Details", callback_data=f"admin_edit_cpn_{coupon_id}"),
                InlineKeyboardButton(text=f"{Emoji.UPLOAD} Upload Codes", callback_data=f"admin_upload_codes_{coupon_id}")
            ],
            [
                InlineKeyboardButton(text=f"{Emoji.SEARCH} View Codes", callback_data=f"admin_view_codes_{coupon_id}"),
                InlineKeyboardButton(text=f"{Emoji.DELETE} Delete", callback_data=f"admin_delete_cpn_{coupon_id}")
            ],
            [InlineKeyboardButton(text=f"{Emoji.BACK} Back", callback_data="admin_coupons")]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def admin_orders(orders: List[Dict], page: int = 0, filter_type: str = "all") -> InlineKeyboardMarkup:
        """Admin orders view"""
        status_emoji = {
            'pending': Emoji.PENDING,
            'approved': Emoji.APPROVED,
            'rejected': Emoji.REJECTED,
            'delivered': Emoji.CHECK
        }
        
        items = [
            (
                f"#{o['id']} - {o['first_name']} - {o['coupon_name']} ({status_emoji.get(o['status'], '')})",
                f"admin_order_{o['id']}"
            )
            for o in orders
        ]
        
        buttons = Keyboards.paginate_buttons(items, page, Config.ITEMS_PER_PAGE, f"admin_{filter_type}_orders")
        buttons.append([InlineKeyboardButton(
            text=f"{Emoji.BACK} Admin Panel",
            callback_data="admin_panel"
        )])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def confirm_action(action: str, data: str) -> InlineKeyboardMarkup:
        """Confirmation keyboard"""
        buttons = [
            [
                InlineKeyboardButton(text=f"{Emoji.CHECK} Confirm", callback_data=f"confirm_{action}_{data}"),
                InlineKeyboardButton(text=f"{Emoji.CROSS} Cancel", callback_data=f"cancel_{action}")
            ]
        ]
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def back_button(callback_data: str, text: str = "Back") -> InlineKeyboardMarkup:
        """Simple back button"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Emoji.BACK} {text}", callback_data=callback_data)]
        ])
    
    @staticmethod
    def cancel_button(text: str = "Cancel") -> InlineKeyboardMarkup:
        """Cancel action button"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"{Emoji.CROSS} {text}", callback_data="cancel_action")]
        ])