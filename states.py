"""
FSM States for Bot Workflows
"""
from aiogram.fsm.state import State, StatesGroup

class CategoryStates(StatesGroup):
    """States for category management"""
    entering_name = State()
    entering_description = State()
    editing_name = State()
    editing_description = State()

class CouponStates(StatesGroup):
    """States for coupon management"""
    selecting_category = State()
    entering_name = State()
    entering_description = State()
    entering_price = State()
    editing_field = State()
    uploading_codes = State()

class OrderStates(StatesGroup):
    """States for order processing"""
    selecting_quantity = State()
    entering_transaction_id = State()
    uploading_screenshot = State()
    entering_reject_reason = State()

class QRStates(StatesGroup):
    """States for QR code management"""
    uploading_qr = State()
    entering_upi = State()

class BroadcastStates(StatesGroup):
    """States for broadcasting"""
    entering_message = State()
    confirming = State()

class UserStates(StatesGroup):
    """States for user operations"""
    browsing_categories = State()
    viewing_coupon = State()