import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


PRODUCTS = [
    ("field-notes", "Field Notes Backpack", "Travel", 68.00, "A daypack built for slow mornings, city walks, and everything in between.", "🎒", "#d9e7d5", "Bestseller"),
    ("ceramic-set", "Sunday Ceramic Set", "Home", 42.00, "Hand-finished stoneware for your everyday coffee ritual.", "☕", "#f0dfc8", "Small batch"),
    ("cloud-knit", "Cloud Knit Throw", "Home", 84.00, "A soft, breathable layer for the little moments at home.", "🧶", "#e7dfe9", "Made to last"),
    ("weekender", "The Weekend Edit", "Travel", 96.00, "An easy-carry weekender with room for one more thing.", "🧳", "#e8d8c6", "Customer favorite"),
    ("studio-bottle", "Studio Water Bottle", "Everyday", 28.00, "Double-wall stainless steel, made to go wherever you do.", "🫙", "#d8e6e9", "New color"),
    ("linen-tote", "Market Day Tote", "Everyday", 34.00, "Roomy washed linen for errands, books, and market flowers.", "🛍️", "#eee1ce", "Easy everyday"),
]


class Database:
    def __init__(self, path: str | None = None):
        configured_path = path or os.getenv("SUPPORTGPT_DATABASE_PATH", "supportgpt.sqlite3")
        self.path = Path(configured_path)

    def connect(self) -> sqlite3.Connection:
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def connection(self):
        connection = self.connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    email TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS products (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    price REAL NOT NULL,
                    description TEXT NOT NULL,
                    icon TEXT NOT NULL,
                    color TEXT NOT NULL,
                    badge TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    customer_email TEXT NOT NULL REFERENCES customers(email),
                    status TEXT NOT NULL,
                    placed_at TEXT NOT NULL,
                    estimated_delivery TEXT NOT NULL,
                    latest_update TEXT NOT NULL,
                    invoice_id TEXT NOT NULL UNIQUE,
                    total REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS order_items (
                    order_id TEXT NOT NULL REFERENCES orders(id),
                    product_id TEXT NOT NULL REFERENCES products(id),
                    quantity INTEGER NOT NULL,
                    unit_price REAL NOT NULL,
                    PRIMARY KEY (order_id, product_id)
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    customer_email TEXT REFERENCES customers(email),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id),
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tickets (
                    id TEXT PRIMARY KEY,
                    customer_email TEXT NOT NULL REFERENCES customers(email),
                    order_id TEXT REFERENCES orders(id),
                    subject TEXT NOT NULL,
                    message TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            for product in PRODUCTS:
                connection.execute(
                    """INSERT OR IGNORE INTO products
                    (id, name, category, price, description, icon, color, badge)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    product,
                )
            demo_email = "alex.morgan@example.com"
            connection.execute(
                "INSERT OR IGNORE INTO customers (email, name, created_at) VALUES (?, ?, ?)",
                (demo_email, "Alex Morgan", self._now()),
            )
            demo_order = "NM-20481"
            connection.execute(
                """INSERT OR IGNORE INTO orders
                (id, customer_email, status, placed_at, estimated_delivery,
                 latest_update, invoice_id, total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    demo_order, demo_email, "In transit",
                    (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                    (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat(),
                    "Your parcel left the regional sorting center this morning.",
                    "INV-20481", 68.00,
                ),
            )
            connection.execute(
                """INSERT OR IGNORE INTO order_items (order_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)""",
                (demo_order, "field-notes", 1, 68.00),
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def list_products(self, search: str = "", category: str = "") -> list[dict]:
        query = "SELECT * FROM products WHERE 1 = 1"
        params: list[str] = []
        if search:
            query += " AND (name LIKE ? OR description LIKE ?)"
            params.extend((f"%{search}%", f"%{search}%"))
        if category and category.lower() != "all":
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY name"
        with self.connection() as connection:
            return [dict(row) for row in connection.execute(query, params)]

    def get_product(self, product_id: str) -> dict | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM products WHERE id = ?", (product_id,)
            ).fetchone()
            return dict(row) if row else None

    def create_customer(self, email: str, name: str) -> dict:
        email = email.strip().lower()
        with self.connection() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO customers (email, name, created_at) VALUES (?, ?, ?)",
                (email, name.strip(), self._now()),
            )
            row = connection.execute(
                "SELECT * FROM customers WHERE email = ?", (email,)
            ).fetchone()
            return dict(row)

    def get_customer(self, email: str) -> dict | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM customers WHERE email = ?", (email.strip().lower(),)
            ).fetchone()
            return dict(row) if row else None

    def list_orders(self, email: str) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM orders WHERE customer_email = ? ORDER BY placed_at DESC",
                (email.strip().lower(),),
            ).fetchall()
            return [self._order_dict(connection, row) for row in rows]

    def get_order(self, order_id: str, email: str | None = None) -> dict | None:
        with self.connection() as connection:
            sql = "SELECT * FROM orders WHERE id = ?"
            params: tuple[str, ...] = (order_id,)
            if email is not None:
                sql += " AND customer_email = ?"
                params = (order_id, email.strip().lower())
            row = connection.execute(sql, params).fetchone()
            return self._order_dict(connection, row) if row else None

    @staticmethod
    def _order_dict(connection: sqlite3.Connection, row: sqlite3.Row) -> dict:
        order = dict(row)
        items = connection.execute(
            """SELECT oi.quantity, oi.unit_price, p.id AS product_id,
                      p.name, p.icon, p.color
               FROM order_items oi JOIN products p ON p.id = oi.product_id
               WHERE oi.order_id = ?""",
            (order["id"],),
        ).fetchall()
        order["items"] = [dict(item) for item in items]
        return order

    def create_order(self, email: str, product_id: str, quantity: int) -> dict | None:
        product = self.get_product(product_id)
        if not product or not self.get_customer(email):
            return None
        order_id = f"NM-{uuid4().hex[:8].upper()}"
        invoice_id = f"INV-{order_id[3:]}"
        now = datetime.now(timezone.utc)
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO orders
                (id, customer_email, status, placed_at, estimated_delivery,
                 latest_update, invoice_id, total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    order_id, email.strip().lower(), "Processing", now.isoformat(),
                    (now + timedelta(days=4)).date().isoformat(),
                    "Your demo order has been received and is being prepared.",
                    invoice_id, round(product["price"] * quantity, 2),
                ),
            )
            connection.execute(
                "INSERT INTO order_items VALUES (?, ?, ?, ?)",
                (order_id, product_id, quantity, product["price"]),
            )
        return self.get_order(order_id, email)

    def save_message(self, session_id: str, email: str | None, role: str, content: str) -> None:
        now = self._now()
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT customer_email FROM conversations WHERE id = ?", (session_id,)
            ).fetchone()
            normalized_email = email.strip().lower() if email else None
            if existing and existing["customer_email"] != normalized_email:
                raise PermissionError("Conversation does not belong to this customer.")
            connection.execute(
                "INSERT OR IGNORE INTO conversations (id, customer_email, created_at) VALUES (?, ?, ?)",
                (session_id, normalized_email, now),
            )
            connection.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now),
            )

    def conversation_messages(self, session_id: str, email: str) -> list[dict] | None:
        with self.connection() as connection:
            owner = connection.execute(
                "SELECT customer_email FROM conversations WHERE id = ?", (session_id,)
            ).fetchone()
            if not owner or owner["customer_email"] != email.strip().lower():
                return None
            rows = connection.execute(
                "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def list_conversations(self, email: str) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT c.id, c.created_at, MAX(m.created_at) AS updated_at,
                          (SELECT content FROM messages
                           WHERE conversation_id = c.id AND role = 'user'
                           ORDER BY id LIMIT 1) AS preview
                   FROM conversations c
                   LEFT JOIN messages m ON m.conversation_id = c.id
                   WHERE c.customer_email = ?
                   GROUP BY c.id ORDER BY updated_at DESC""",
                (email.strip().lower(),),
            ).fetchall()
            return [dict(row) for row in rows]

    def save_exchange(
        self, session_id: str, email: str, user_message: str, response: str
    ) -> None:
        normalized_email = email.strip().lower()
        now = self._now()
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT customer_email FROM conversations WHERE id = ?", (session_id,)
            ).fetchone()
            if existing and existing["customer_email"] != normalized_email:
                raise PermissionError("Conversation does not belong to this customer.")
            connection.execute(
                "INSERT OR IGNORE INTO conversations (id, customer_email, created_at) VALUES (?, ?, ?)",
                (session_id, normalized_email, now),
            )
            connection.executemany(
                """INSERT INTO messages (conversation_id, role, content, created_at)
                VALUES (?, ?, ?, ?)""",
                [
                    (session_id, "user", user_message, now),
                    (session_id, "assistant", response, now),
                ],
            )

    def conversation_belongs_to(self, session_id: str, email: str) -> bool:
        with self.connection() as connection:
            owner = connection.execute(
                "SELECT customer_email FROM conversations WHERE id = ?", (session_id,)
            ).fetchone()
            return owner is None or owner["customer_email"] == email.strip().lower()

    def create_ticket(self, email: str, subject: str, message: str, order_id: str | None) -> dict | None:
        ticket_id = f"NM-{uuid4().hex[:8].upper()}"
        with self.connection() as connection:
            if order_id:
                owner = connection.execute(
                    "SELECT 1 FROM orders WHERE id = ? AND customer_email = ?",
                    (order_id, email.strip().lower()),
                ).fetchone()
                if not owner:
                    return None
            connection.execute(
                """INSERT INTO tickets
                (id, customer_email, order_id, subject, message, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (ticket_id, email.strip().lower(), order_id, subject, message, "Open", self._now()),
            )
            row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
            return dict(row)


database = Database()
