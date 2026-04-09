"""
Database Operations Layer
"""
import sqlite3
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager
from config import Config

logger = logging.getLogger(__name__)

class Database:
    """Database manager with connection pooling"""
    
    def __init__(self, db_file: str = Config.DB_FILE):
        self.db_file = db_file
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize all database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    referral_code TEXT UNIQUE,
                    referred_by INTEGER,
                    balance REAL DEFAULT 0,
                    total_spent REAL DEFAULT 0,
                    total_orders INTEGER DEFAULT 0,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_blocked INTEGER DEFAULT 0,
                    FOREIGN KEY (referred_by) REFERENCES users(user_id)
                )
            """)
            
            # Categories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    icon TEXT DEFAULT '📁',
                    position INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Coupons table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coupons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    price REAL NOT NULL,
                    original_price REAL,
                    stock INTEGER DEFAULT 0,
                    sold_count INTEGER DEFAULT 0,
                    min_purchase INTEGER DEFAULT 1,
                    max_purchase INTEGER DEFAULT 10,
                    is_active INTEGER DEFAULT 1,
                    is_featured INTEGER DEFAULT 0,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
                )
            """)
            
            # Coupon codes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coupon_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    coupon_id INTEGER NOT NULL,
                    code TEXT NOT NULL UNIQUE,
                    is_used INTEGER DEFAULT 0,
                    used_by INTEGER,
                    used_at TIMESTAMP,
                    order_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (coupon_id) REFERENCES coupons(id) ON DELETE CASCADE,
                    FOREIGN KEY (used_by) REFERENCES users(user_id),
                    FOREIGN KEY (order_id) REFERENCES orders(id)
                )
            """)
            
            # Orders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    coupon_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    total_price REAL NOT NULL,
                    discount REAL DEFAULT 0,
                    transaction_id TEXT UNIQUE NOT NULL,
                    screenshot_file_id TEXT,
                    payment_method TEXT DEFAULT 'UPI',
                    status TEXT DEFAULT 'pending',
                    reject_reason TEXT,
                    approved_by INTEGER,
                    approved_at TIMESTAMP,
                    delivered_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (coupon_id) REFERENCES coupons(id),
                    FOREIGN KEY (approved_by) REFERENCES users(user_id)
                )
            """)
            
            # QR Settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS qr_settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    file_id TEXT,
                    upi_id TEXT,
                    merchant_name TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert default QR settings
            cursor.execute("""
                INSERT OR IGNORE INTO qr_settings (id, upi_id, merchant_name) 
                VALUES (1, ?, 'Coupon Store')
            """, (Config.DEFAULT_UPI_ID,))
            
            # Broadcast history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sent_by INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    total_users INTEGER DEFAULT 0,
                    successful INTEGER DEFAULT 0,
                    failed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sent_by) REFERENCES users(user_id)
                )
            """)
            
            # Discount codes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS discount_codes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    discount_percent REAL,
                    discount_amount REAL,
                    min_purchase REAL DEFAULT 0,
                    max_uses INTEGER,
                    used_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_user 
                ON orders(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_orders_status 
                ON orders(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_coupon_codes_coupon 
                ON coupon_codes(coupon_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_coupon_codes_used 
                ON coupon_codes(is_used)
            """)
            
            logger.info("Database initialized successfully")
    
    # ==================== USER OPERATIONS ====================
    
    def add_user(self, user_id: int, username: str = None, 
                 first_name: str = None, last_name: str = None) -> bool:
        """Add or update user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (user_id, username, first_name, last_name)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        username = excluded.username,
                        first_name = excluded.first_name,
                        last_name = excluded.last_name,
                        last_active = CURRENT_TIMESTAMP
                """, (user_id, username, first_name, last_name))
                return True
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting user: {e}")
            return None
    
    def get_all_users(self, active_only: bool = False) -> List[Dict]:
        """Get all users"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM users WHERE is_blocked = 0" if active_only else "SELECT * FROM users"
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return []
    
    def block_user(self, user_id: int, block: bool = True) -> bool:
        """Block or unblock user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users SET is_blocked = ? WHERE user_id = ?
                """, (1 if block else 0, user_id))
                return True
        except Exception as e:
            logger.error(f"Error blocking user: {e}")
            return False
    
    # ==================== CATEGORY OPERATIONS ====================
    
    def add_category(self, name: str, description: str = None, 
                     icon: str = "📁") -> Optional[int]:
        """Add new category"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO categories (name, description, icon)
                    VALUES (?, ?, ?)
                """, (name, description, icon))
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Category '{name}' already exists")
            return None
        except Exception as e:
            logger.error(f"Error adding category: {e}")
            return None
    
    def get_categories(self, active_only: bool = True) -> List[Dict]:
        """Get all categories"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT c.*, COUNT(cp.id) as coupon_count
                    FROM categories c
                    LEFT JOIN coupons cp ON c.id = cp.category_id AND cp.is_active = 1
                    WHERE c.is_active = 1
                    GROUP BY c.id
                    ORDER BY c.position, c.name
                """ if active_only else """
                    SELECT c.*, COUNT(cp.id) as coupon_count
                    FROM categories c
                    LEFT JOIN coupons cp ON c.id = cp.category_id
                    GROUP BY c.id
                    ORDER BY c.position, c.name
                """
                cursor.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []
    
    def get_category(self, category_id: int) -> Optional[Dict]:
        """Get category by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting category: {e}")
            return None
    
    def update_category(self, category_id: int, **kwargs) -> bool:
        """Update category"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
                values = list(kwargs.values()) + [category_id]
                cursor.execute(f"""
                    UPDATE categories SET {fields}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, values)
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating category: {e}")
            return False
    
    def delete_category(self, category_id: int) -> bool:
        """Delete category (soft delete)"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE categories SET is_active = 0 WHERE id = ?
                """, (category_id,))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting category: {e}")
            return False
    
    # ==================== COUPON OPERATIONS ====================
    
    def add_coupon(self, category_id: int, name: str, price: float,
                   description: str = None, **kwargs) -> Optional[int]:
        """Add new coupon"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO coupons 
                    (category_id, name, description, price, original_price,
                     min_purchase, max_purchase, is_featured)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    category_id, name, description, price,
                    kwargs.get('original_price', price),
                    kwargs.get('min_purchase', 1),
                    kwargs.get('max_purchase', Config.MAX_COUPON_PURCHASE),
                    kwargs.get('is_featured', 0)
                ))
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error adding coupon: {e}")
            return None
    
    def get_coupons(self, category_id: int = None, 
                    active_only: bool = True) -> List[Dict]:
        """Get coupons"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT c.*, cat.name as category_name,
                           (SELECT COUNT(*) FROM coupon_codes cc 
                            WHERE cc.coupon_id = c.id AND cc.is_used = 0) as available_stock
                    FROM coupons c
                    LEFT JOIN categories cat ON c.category_id = cat.id
                    WHERE 1=1
                """
                params = []
                
                if category_id:
                    query += " AND c.category_id = ?"
                    params.append(category_id)
                
                if active_only:
                    query += " AND c.is_active = 1 AND cat.is_active = 1"
                
                query += " ORDER BY c.is_featured DESC, c.name"
                
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting coupons: {e}")
            return []
    
    def get_coupon(self, coupon_id: int) -> Optional[Dict]:
        """Get coupon by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT c.*, cat.name as category_name,
                           (SELECT COUNT(*) FROM coupon_codes cc 
                            WHERE cc.coupon_id = c.id AND cc.is_used = 0) as available_stock
                    FROM coupons c
                    LEFT JOIN categories cat ON c.category_id = cat.id
                    WHERE c.id = ?
                """, (coupon_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting coupon: {e}")
            return None
    
    def update_coupon(self, coupon_id: int, **kwargs) -> bool:
        """Update coupon"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                fields = ", ".join([f"{k} = ?" for k in kwargs.keys()])
                values = list(kwargs.values()) + [coupon_id]
                cursor.execute(f"""
                    UPDATE coupons SET {fields}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, values)
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating coupon: {e}")
            return False
    
    def delete_coupon(self, coupon_id: int) -> bool:
        """Delete coupon (soft delete)"""
        return self.update_coupon(coupon_id, is_active=0)
    
    # ==================== COUPON CODE OPERATIONS ====================
    
    def add_coupon_codes(self, coupon_id: int, codes: List[str]) -> Tuple[int, int]:
        """Bulk add coupon codes. Returns (added, duplicates)"""
        added = 0
        duplicates = 0
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for code in codes:
                    try:
                        cursor.execute("""
                            INSERT INTO coupon_codes (coupon_id, code)
                            VALUES (?, ?)
                        """, (coupon_id, code.strip()))
                        added += 1
                    except sqlite3.IntegrityError:
                        duplicates += 1
                
                # Update stock count
                cursor.execute("""
                    UPDATE coupons SET stock = (
                        SELECT COUNT(*) FROM coupon_codes 
                        WHERE coupon_id = ? AND is_used = 0
                    ) WHERE id = ?
                """, (coupon_id, coupon_id))
                
                return (added, duplicates)
        except Exception as e:
            logger.error(f"Error adding coupon codes: {e}")
            return (0, 0)
    
    def get_available_codes(self, coupon_id: int, quantity: int) -> List[str]:
        """Get available coupon codes"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT code FROM coupon_codes
                    WHERE coupon_id = ? AND is_used = 0
                    LIMIT ?
                """, (coupon_id, quantity))
                return [row['code'] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting available codes: {e}")
            return []
    
    def mark_codes_used(self, codes: List[str], user_id: int, order_id: int) -> bool:
        """Mark codes as used"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for code in codes:
                    cursor.execute("""
                        UPDATE coupon_codes 
                        SET is_used = 1, used_by = ?, used_at = CURRENT_TIMESTAMP, order_id = ?
                        WHERE code = ?
                    """, (user_id, order_id, code))
                return True
        except Exception as e:
            logger.error(f"Error marking codes as used: {e}")
            return False
    
    # ==================== ORDER OPERATIONS ====================
    
    def create_order(self, user_id: int, coupon_id: int, quantity: int,
                     unit_price: float, total_price: float, 
                     transaction_id: str, screenshot_file_id: str = None) -> Optional[int]:
        """Create new order"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO orders 
                    (user_id, coupon_id, quantity, unit_price, total_price, 
                     transaction_id, screenshot_file_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (user_id, coupon_id, quantity, unit_price, total_price,
                      transaction_id, screenshot_file_id))
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Duplicate transaction ID: {transaction_id}")
            return None
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return None
    
    def get_order(self, order_id: int) -> Optional[Dict]:
        """Get order by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT o.*, c.name as coupon_name, u.first_name, u.username
                    FROM orders o
                    LEFT JOIN coupons c ON o.coupon_id = c.id
                    LEFT JOIN users u ON o.user_id = u.user_id
                    WHERE o.id = ?
                """, (order_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting order: {e}")
            return None
    
    def get_orders(self, user_id: int = None, status: str = None) -> List[Dict]:
        """Get orders with filters"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT o.*, c.name as coupon_name, u.first_name, u.username
                    FROM orders o
                    LEFT JOIN coupons c ON o.coupon_id = c.id
                    LEFT JOIN users u ON o.user_id = u.user_id
                    WHERE 1=1
                """
                params = []
                
                if user_id:
                    query += " AND o.user_id = ?"
                    params.append(user_id)
                
                if status:
                    query += " AND o.status = ?"
                    params.append(status)
                
                query += " ORDER BY o.created_at DESC"
                
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []
    
    def update_order_status(self, order_id: int, status: str, 
                           approved_by: int = None, 
                           reject_reason: str = None) -> bool:
        """Update order status"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if status == 'approved':
                    cursor.execute("""
                        UPDATE orders 
                        SET status = ?, approved_by = ?, approved_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (status, approved_by, order_id))
                elif status == 'rejected':
                    cursor.execute("""
                        UPDATE orders 
                        SET status = ?, reject_reason = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (status, reject_reason, order_id))
                else:
                    cursor.execute("""
                        UPDATE orders 
                        SET status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (status, order_id))
                
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating order status: {e}")
            return False
    
    def deliver_order(self, order_id: int) -> bool:
        """Mark order as delivered"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE orders 
                    SET status = 'delivered', delivered_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (order_id,))
                
                # Update user stats
                cursor.execute("""
                    UPDATE users 
                    SET total_orders = total_orders + 1,
                        total_spent = total_spent + (SELECT total_price FROM orders WHERE id = ?)
                    WHERE user_id = (SELECT user_id FROM orders WHERE id = ?)
                """, (order_id, order_id))
                
                # Update coupon sold count
                cursor.execute("""
                    UPDATE coupons 
                    SET sold_count = sold_count + (SELECT quantity FROM orders WHERE id = ?)
                    WHERE id = (SELECT coupon_id FROM orders WHERE id = ?)
                """, (order_id, order_id))
                
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error delivering order: {e}")
            return False
    
    # ==================== QR SETTINGS ====================
    
    def get_qr_settings(self) -> Optional[Dict]:
        """Get QR code settings"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM qr_settings WHERE id = 1")
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting QR settings: {e}")
            return None
    
    def update_qr_settings(self, file_id: str = None, upi_id: str = None) -> bool:
        """Update QR settings"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if file_id and upi_id:
                    cursor.execute("""
                        UPDATE qr_settings 
                        SET file_id = ?, upi_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = 1
                    """, (file_id, upi_id))
                elif file_id:
                    cursor.execute("""
                        UPDATE qr_settings 
                        SET file_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = 1
                    """, (file_id,))
                elif upi_id:
                    cursor.execute("""
                        UPDATE qr_settings 
                        SET upi_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = 1
                    """, (upi_id,))
                return True
        except Exception as e:
            logger.error(f"Error updating QR settings: {e}")
            return False
    
    # ==================== STATISTICS ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get bot statistics"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Total users
                cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_blocked = 0")
                stats['total_users'] = cursor.fetchone()['count']
                
                # Total categories
                cursor.execute("SELECT COUNT(*) as count FROM categories WHERE is_active = 1")
                stats['total_categories'] = cursor.fetchone()['count']
                
                # Total coupons
                cursor.execute("SELECT COUNT(*) as count FROM coupons WHERE is_active = 1")
                stats['total_coupons'] = cursor.fetchone()['count']
                
                # Total orders
                cursor.execute("SELECT COUNT(*) as count FROM orders")
                stats['total_orders'] = cursor.fetchone()['count']
                
                # Pending orders
                cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'pending'")
                stats['pending_orders'] = cursor.fetchone()['count']
                
                # Approved orders
                cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'approved' OR status = 'delivered'")
                stats['approved_orders'] = cursor.fetchone()['count']
                
                # Total revenue
                cursor.execute("SELECT COALESCE(SUM(total_price), 0) as revenue FROM orders WHERE status IN ('approved', 'delivered')")
                stats['total_revenue'] = cursor.fetchone()['revenue']
                
                # Today's orders
                cursor.execute("SELECT COUNT(*) as count FROM orders WHERE DATE(created_at) = DATE('now')")
                stats['today_orders'] = cursor.fetchone()['count']
                
                # Today's revenue
                cursor.execute("SELECT COALESCE(SUM(total_price), 0) as revenue FROM orders WHERE DATE(created_at) = DATE('now') AND status IN ('approved', 'delivered')")
                stats['today_revenue'] = cursor.fetchone()['revenue']
                
                return stats
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    # ==================== BROADCAST ====================
    
    def add_broadcast(self, sent_by: int, message: str, 
                     total_users: int, successful: int, failed: int) -> Optional[int]:
        """Add broadcast record"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO broadcasts (sent_by, message, total_users, successful, failed)
                    VALUES (?, ?, ?, ?, ?)
                """, (sent_by, message, total_users, successful, failed))
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error adding broadcast: {e}")
            return None

# Global database instance
db = Database()
