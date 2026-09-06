#!/usr/bin/env python3
"""
Irani Café Management System — Three-Tier Application Server
Backend: Python 3 Standard Library only (http.server, sqlite3, json, hashlib, hmac, secrets, datetime, os)
Database: SQLite3 (cafe.db)
Frontend: Served statically at root /
"""

import os
import sys
import json
import sqlite3
import hashlib
import hmac
import secrets
from datetime import datetime, date, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import mimetypes

# Base directory for cross-platform compatibility
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "cafe.db")
STATIC_HTML_PATH = os.path.join(BASE_DIR, "irani-cafe-system.html")

# In-memory sessions: token -> {user_id, staff_id, role, name, username}
SESSIONS = {}

ALLOWED_DB_TABLES = {
    "irani_cafe", "customer", "menu_item", "inventory",
    "recipe", "staff", "attendance", "orders", "order_item", "app_user"
}

# ==============================================================================
# DATABASE SCHEMA & INITIALIZATION
# ==============================================================================

def get_db_connection():
    """Create a new database connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def init_db(force=False):
    """
    Creates cafe.db schema and seeds initial data if database does not exist.
    Matches the project ER diagram entity and attribute names exactly.
    """
    if os.path.exists(DB_PATH) and not force:
        return

    conn = get_db_connection()
    cur = conn.cursor()

    # DDL
    cur.executescript("""
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS irani_cafe (
        cafe_id TEXT PRIMARY KEY,
        cafe_name TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS customer (
        customer_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        contact_info TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS menu_item (
        menu_item_id TEXT PRIMARY KEY,
        item_name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS inventory (
        item_id TEXT PRIMARY KEY,
        item_name TEXT NOT NULL,
        unit TEXT NOT NULL,
        quantity REAL NOT NULL,
        reorder_level REAL NOT NULL,
        restock_step REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS recipe (
        menu_item_id TEXT NOT NULL,
        item_id TEXT NOT NULL,
        qty_per_unit REAL NOT NULL,
        PRIMARY KEY (menu_item_id, item_id),
        FOREIGN KEY (menu_item_id) REFERENCES menu_item(menu_item_id) ON DELETE CASCADE,
        FOREIGN KEY (item_id) REFERENCES inventory(item_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS staff (
        staff_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        contact TEXT NOT NULL,
        joining_date TEXT NOT NULL,
        shift TEXT NOT NULL,
        base_salary REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS attendance (
        attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id TEXT NOT NULL,
        att_date TEXT NOT NULL,
        status TEXT NOT NULL,
        FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id TEXT,
        order_time TEXT NOT NULL,
        total_amount REAL NOT NULL,
        payment_mode TEXT NOT NULL,
        billed_by TEXT NOT NULL,
        FOREIGN KEY (customer_id) REFERENCES customer(customer_id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS order_item (
        order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        menu_item_id TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        line_amount REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
        FOREIGN KEY (menu_item_id) REFERENCES menu_item(menu_item_id) ON DELETE RESTRICT
    );

    CREATE TABLE IF NOT EXISTS app_user (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id TEXT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL,
        FOREIGN KEY (staff_id) REFERENCES staff(staff_id) ON DELETE SET NULL
    );

    CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
    CREATE INDEX IF NOT EXISTS idx_order_item_order ON order_item(order_id);
    CREATE INDEX IF NOT EXISTS idx_attendance_staff ON attendance(staff_id, att_date);
    """)

    # Seed irani_cafe
    cur.execute("INSERT INTO irani_cafe (cafe_id, cafe_name) VALUES (?, ?)", ("IC-01", "Irani Café"))

    # Seed customers
    customers = [
        ("CUS-001", "Dara Unwala", "98220 55610"),
        ("CUS-002", "Zarin Commissariat", "90110 34782"),
        ("CUS-003", "Pervez Chinoy", "77200 91453"),
        ("CUS-004", "Anahita Mehta", "88990 67321")
    ]
    cur.executemany("INSERT INTO customer (customer_id, name, contact_info) VALUES (?, ?, ?)", customers)

    # Seed menu_items
    menu_items = [
        ("chai", "Irani Chai", "Chai & drinks", 20.0),
        ("spchai", "Special Chai", "Chai & drinks", 30.0),
        ("coffee", "Cold Coffee", "Chai & drinks", 80.0),
        ("lassi", "Sweet Lassi", "Chai & drinks", 60.0),
        ("bun", "Bun Maska", "Bakery", 35.0),
        ("brun", "Brun Maska", "Bakery", 40.0),
        ("osm", "Osmania Biscuit ×4", "Bakery", 30.0),
        ("mawa", "Mawa Cake", "Bakery", 45.0),
        ("puff", "Chicken Puff", "Bakery", 50.0),
        ("kheema", "Kheema Pav", "Kitchen", 110.0),
        ("bhurji", "Egg Bhurji Pav", "Kitchen", 90.0),
        ("akuri", "Akuri on Toast", "Kitchen", 120.0),
        ("samosa", "Mutton Samosa ×2", "Kitchen", 60.0),
        ("cust", "Caramel Custard", "Sweets", 70.0)
    ]
    cur.executemany("INSERT INTO menu_item (menu_item_id, item_name, category, price) VALUES (?, ?, ?, ?)", menu_items)

    # Seed inventory (exact values from STOCK)
    inventory = [
        ("milk", "Milk", "L", 38.0, 15.0, 20.0),
        ("tea", "Tea leaves", "kg", 2.4, 1.5, 2.0),
        ("sugar", "Sugar", "kg", 9.0, 5.0, 10.0),
        ("butter", "Amul butter", "kg", 1.8, 2.0, 2.0),
        ("bun", "Bun", "pcs", 62.0, 60.0, 100.0),
        ("brun", "Brun", "pcs", 34.0, 40.0, 60.0),
        ("pav", "Pav", "pcs", 96.0, 60.0, 120.0),
        ("egg", "Eggs", "pcs", 88.0, 60.0, 90.0),
        ("kheema", "Mutton kheema", "kg", 3.2, 2.0, 4.0)
    ]
    cur.executemany("INSERT INTO inventory (item_id, item_name, unit, quantity, reorder_level, restock_step) VALUES (?, ?, ?, ?, ?, ?)", inventory)

    # Seed recipe (maps dish uses -> inventory)
    recipes = [
        ("chai", "milk", 0.14),
        ("chai", "tea", 0.008),
        ("chai", "sugar", 0.018),
        ("spchai", "milk", 0.18),
        ("spchai", "tea", 0.010),
        ("spchai", "sugar", 0.020),
        ("coffee", "milk", 0.20),
        ("coffee", "sugar", 0.030),
        ("lassi", "milk", 0.25),
        ("lassi", "sugar", 0.030),
        ("bun", "bun", 1.0),
        ("bun", "butter", 0.020),
        ("brun", "brun", 1.0),
        ("brun", "butter", 0.022),
        ("kheema", "kheema", 0.12),
        ("kheema", "pav", 2.0),
        ("bhurji", "egg", 3.0),
        ("bhurji", "pav", 2.0),
        ("bhurji", "butter", 0.010),
        ("akuri", "egg", 3.0),
        ("akuri", "butter", 0.015),
        ("cust", "milk", 0.15),
        ("cust", "egg", 1.0),
        ("cust", "sugar", 0.030)
    ]
    cur.executemany("INSERT INTO recipe (menu_item_id, item_id, qty_per_unit) VALUES (?, ?, ?)", recipes)

    # Seed staff
    staff_members = [
        ("EMP-01", "Rustom Irani", "Manager", "98220 41953", "12 Mar 2011", "Morning", 32000.0),
        ("EMP-02", "Farhad Batliwala", "Head cook", "98600 22417", "04 Jul 2015", "Morning", 28000.0),
        ("EMP-03", "Meera Pawar", "Cashier", "90280 71134", "19 Jan 2021", "Afternoon", 19000.0),
        ("EMP-04", "Sanjay Kadam", "Waiter", "77098 33260", "02 Sep 2019", "Afternoon", 16000.0),
        ("EMP-05", "Imran Shaikh", "Waiter", "96570 88012", "15 Nov 2022", "Evening", 16000.0),
        ("EMP-06", "Babu Sonawane", "Cleaner", "88888 45120", "28 Feb 2018", "Evening", 12000.0)
    ]
    cur.executemany("INSERT INTO staff (staff_id, name, role, contact, joining_date, shift, base_salary) VALUES (?, ?, ?, ?, ?, ?, ?)", staff_members)

    # Seed attendance:
    # Target days present: EMP-01: 25, EMP-02: 24, EMP-03: 26, EMP-04: 23, EMP-05: 26, EMP-06: 22
    # Present today: EMP-01, EMP-02, EMP-03, EMP-05 (EMP-04 and EMP-06 are absent today)
    today_date = date.today()
    today_str = today_date.strftime("%Y-%m-%d")

    target_days = {
        "EMP-01": (25, True),
        "EMP-02": (24, True),
        "EMP-03": (26, True),
        "EMP-04": (23, False),
        "EMP-05": (26, True),
        "EMP-06": (22, False)
    }

    attendance_rows = []
    for sid, (days_count, is_today_present) in target_days.items():
        past_needed = days_count - (1 if is_today_present else 0)
        for d_offset in range(1, past_needed + 1):
            past_date_str = (today_date - timedelta(days=d_offset)).strftime("%Y-%m-%d")
            attendance_rows.append((sid, past_date_str, "Present"))
        if is_today_present:
            attendance_rows.append((sid, today_str, "Present"))

    cur.executemany("INSERT INTO attendance (staff_id, att_date, status) VALUES (?, ?, ?)", attendance_rows)

    # Seed app_user with PBKDF2-HMAC-SHA256 (100,000 iterations).
    # Pre-hashed salts and hashes for password "cafe123" — NO plaintext passwords anywhere!
    users = [
        ("EMP-01", "EMP-01", "936704462f70ced951ff714696a7418aadfc510073211d9259fbed08de74c760", "bf5734cdcc40d4a75978356777547a16", "Manager"),
        ("EMP-03", "EMP-03", "0423339635f6f4a763294a284fba3fe0d423a5452a62d3f3ee763fc66f241071", "9b7515264b85c6998a1b54fd01a635c4", "Cashier")
    ]
    cur.executemany("INSERT INTO app_user (staff_id, username, password_hash, salt, role) VALUES (?, ?, ?, ?, ?)", users)

    # Seed orders & order_item
    # Order sequence starts from 143 up to 154 (derived from billSeq = 142)
    seed_orders = [
        {"id": 143, "t": "07:48", "mode": "Cash", "cust": "CUS-001", "items": [("chai", 2), ("bun", 2)]},
        {"id": 144, "t": "08:05", "mode": "UPI",  "cust": None,      "items": [("chai", 1), ("brun", 1), ("osm", 1)]},
        {"id": 145, "t": "08:31", "mode": "Cash", "cust": None,      "items": [("spchai", 2), ("mawa", 2)]},
        {"id": 146, "t": "09:02", "mode": "UPI",  "cust": "CUS-003", "items": [("kheema", 1), ("chai", 2)]},
        {"id": 147, "t": "09:40", "mode": "Cash", "cust": None,      "items": [("chai", 4), ("bun", 4)]},
        {"id": 148, "t": "10:15", "mode": "UPI",  "cust": "CUS-002", "items": [("bhurji", 2), ("chai", 2), ("brun", 2)]},
        {"id": 149, "t": "10:52", "mode": "Cash", "cust": None,      "items": [("chai", 3), ("samosa", 1)]},
        {"id": 150, "t": "11:20", "mode": "UPI",  "cust": None,      "items": [("akuri", 1), ("coffee", 1)]},
        {"id": 151, "t": "11:47", "mode": "Cash", "cust": None,      "items": [("chai", 2), ("puff", 2), ("mawa", 1)]},
        {"id": 152, "t": "12:18", "mode": "UPI",  "cust": "CUS-001", "items": [("kheema", 2), ("lassi", 2), ("chai", 2)]},
        {"id": 153, "t": "12:55", "mode": "Cash", "cust": None,      "items": [("chai", 6), ("bun", 6)]},
        {"id": 154, "t": "13:26", "mode": "UPI",  "cust": None,      "items": [("cust", 2), ("spchai", 2)]}
    ]

    menu_price_dict = dict(cur.execute("SELECT menu_item_id, price FROM menu_item").fetchall())

    for o in seed_orders:
        subtotal = sum(menu_price_dict[item_id] * qty for item_id, qty in o["items"])
        total_amount = round(subtotal + (subtotal * 0.05), 2)
        cur.execute("""
            INSERT INTO orders (order_id, customer_id, order_time, total_amount, payment_mode, billed_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (o["id"], o["cust"], o["t"], total_amount, o["mode"], "Manager · EMP-01"))

        for item_id, qty in o["items"]:
            line_amount = menu_price_dict[item_id] * qty
            cur.execute("""
                INSERT INTO order_item (order_id, menu_item_id, quantity, line_amount)
                VALUES (?, ?, ?, ?)
            """, (o["id"], item_id, qty, line_amount))

    conn.commit()
    conn.close()
    print(f"[Irani Café] Database initialized and seeded successfully at {DB_PATH}")

# Overtime static configuration matching field study
STAFF_OVERTIME_HOURS = {
    "EMP-01": 0,
    "EMP-02": 9,
    "EMP-03": 4,
    "EMP-04": 6,
    "EMP-05": 12,
    "EMP-06": 0
}

# ==============================================================================
# AUTH & CRYPTO HELPERS
# ==============================================================================

def verify_password(stored_hash, stored_salt, password):
    calculated_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        stored_salt.encode("utf-8"),
        100000
    ).hex()
    return hmac.compare_digest(stored_hash, calculated_hash)

# ==============================================================================
# HTTP REQUEST HANDLER
# ==============================================================================

class CafeHandler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message, status=400):
        self.send_json({"error": message}, status=status)

    def serve_static(self, path):
        # Normalize and prevent directory traversal
        rel_path = path.lstrip("/")
        if not rel_path or rel_path == "index.html":
            file_path = STATIC_HTML_PATH
        else:
            file_path = os.path.join(BASE_DIR, rel_path)

        file_path = os.path.abspath(file_path)
        if not file_path.startswith(BASE_DIR) or not os.path.exists(file_path) or os.path.isdir(file_path):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"404 Not Found")
            return

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"
        if mime_type.startswith("text/"):
            mime_type += "; charset=utf-8"

        with open(file_path, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def read_json_body(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                return {}
            raw = self.rfile.read(content_length).decode("utf-8")
            return json.loads(raw)
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # GET & HEAD ROUTER
    # --------------------------------------------------------------------------
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # API routing
        if path.startswith("/api/"):
            try:
                self.handle_api_get(path, query)
            except Exception as e:
                self.send_error_json(f"Server error: {str(e)}", status=500)
            return

        # Static file serving
        self.serve_static(path)

    def handle_api_get(self, path, query):
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. GET /api/menu
        if path == "/api/menu":
            rows = cur.execute("SELECT menu_item_id, item_name, category, price FROM menu_item ORDER BY category, item_name").fetchall()
            items = []
            for r in rows:
                items.append({
                    "id": r["menu_item_id"],
                    "menu_item_id": r["menu_item_id"],
                    "name": r["item_name"],
                    "cat": r["category"],
                    "category": r["category"],
                    "price": r["price"]
                })
            conn.close()
            self.send_json(items)
            return

        # 2. GET /api/inventory
        if path == "/api/inventory":
            rows = cur.execute("SELECT item_id, item_name, unit, quantity, reorder_level, restock_step FROM inventory").fetchall()
            items = []
            for r in rows:
                items.append({
                    "id": r["item_id"],
                    "item_id": r["item_id"],
                    "name": r["item_name"],
                    "unit": r["unit"],
                    "qty": round(r["quantity"], 3),
                    "quantity": round(r["quantity"], 3),
                    "min": r["reorder_level"],
                    "reorder_level": r["reorder_level"],
                    "step": r["restock_step"],
                    "restock_step": r["restock_step"],
                    "is_low": r["quantity"] <= r["reorder_level"]
                })
            conn.close()
            self.send_json(items)
            return

        # 3. GET /api/customers
        if path == "/api/customers":
            rows = cur.execute("""
                SELECT 
                    c.customer_id, 
                    c.name, 
                    c.contact_info,
                    COUNT(o.order_id) AS visits,
                    COALESCE(SUM(o.total_amount), 0) AS total_spent,
                    COALESCE(MAX(o.order_time), '—') AS last_visit
                FROM customer c
                LEFT JOIN orders o ON c.customer_id = o.customer_id
                GROUP BY c.customer_id
                ORDER BY c.customer_id
            """).fetchall()
            customers = []
            for r in rows:
                customers.append({
                    "Customer_id": r["customer_id"],
                    "customer_id": r["customer_id"],
                    "Name": r["name"],
                    "name": r["name"],
                    "Contact_info": r["contact_info"],
                    "contact_info": r["contact_info"],
                    "visits": r["visits"],
                    "total_spent": round(r["total_spent"], 2),
                    "last_visit": r["last_visit"]
                })
            conn.close()
            self.send_json(customers)
            return

        # 4. GET /api/orders
        if path == "/api/orders":
            order_rows = cur.execute("""
                SELECT o.order_id, o.customer_id, c.name as customer_name, o.order_time, o.total_amount, o.payment_mode, o.billed_by
                FROM orders o
                LEFT JOIN customer c ON o.customer_id = c.customer_id
                ORDER BY o.order_id ASC
            """).fetchall()

            # Batch load order items
            items_rows = cur.execute("""
                SELECT oi.order_id, oi.menu_item_id, m.item_name, oi.quantity, oi.line_amount, m.price
                FROM order_item oi
                JOIN menu_item m ON oi.menu_item_id = m.menu_item_id
                ORDER BY oi.order_item_id ASC
            """).fetchall()

            items_by_order = {}
            for ir in items_rows:
                oid = ir["order_id"]
                if oid not in items_by_order:
                    items_by_order[oid] = []
                items_by_order[oid].append({
                    "id": ir["menu_item_id"],
                    "menu_item_id": ir["menu_item_id"],
                    "name": ir["item_name"],
                    "qty": ir["quantity"],
                    "price": ir["price"],
                    "line_amount": ir["line_amount"]
                })

            bills = []
            for o in order_rows:
                oid = o["order_id"]
                subtotal = sum(item["line_amount"] for item in items_by_order.get(oid, []))
                tax = round(subtotal * 0.05, 2)
                bills.append({
                    "order_id": oid,
                    "no": f"IC/26-27/{oid:04d}",
                    "Customer_id": o["customer_id"],
                    "customer_id": o["customer_id"],
                    "customer_name": o["customer_name"],
                    "time": o["order_time"],
                    "mode": o["payment_mode"],
                    "billed_by": o["billed_by"],
                    "subtotal": subtotal,
                    "tax": tax,
                    "total": o["total_amount"],
                    "items": items_by_order.get(oid, [])
                })
            conn.close()
            self.send_json(bills)
            return

        # 5. GET /api/staff
        if path == "/api/staff":
            staff_rows = cur.execute("SELECT staff_id, name, role, contact, joining_date, shift, base_salary FROM staff").fetchall()
            today_str = date.today().strftime("%Y-%m-%d")

            result = []
            for s in staff_rows:
                sid = s["staff_id"]
                days_row = cur.execute("SELECT COUNT(*) as cnt FROM attendance WHERE staff_id = ? AND status = 'Present'", (sid,)).fetchone()
                days_present = days_row["cnt"] if days_row else 0

                today_att = cur.execute("SELECT status FROM attendance WHERE staff_id = ? AND att_date = ?", (sid, today_str)).fetchone()
                present_today = bool(today_att and today_att["status"] == "Present")

                base = s["base_salary"]
                ot = STAFF_OVERTIME_HOURS.get(sid, 0)
                per_day = base / 26.0
                earned = per_day * days_present
                ot_pay = ot * (per_day / 8.0) * 1.5
                net_salary = round(earned + ot_pay)

                result.append({
                    "id": sid,
                    "staff_id": sid,
                    "name": s["name"],
                    "role": s["role"],
                    "shift": s["shift"],
                    "phone": s["contact"],
                    "contact": s["contact"],
                    "joined": s["joining_date"],
                    "joining_date": s["joining_date"],
                    "base": base,
                    "base_salary": base,
                    "days": days_present,
                    "days_present": days_present,
                    "ot": ot,
                    "overtime_hours": ot,
                    "present": present_today,
                    "present_today": present_today,
                    "net_salary": net_salary
                })
            conn.close()
            self.send_json(result)
            return

        # 6. GET /api/reports/today
        if path == "/api/reports/today":
            orders_rows = cur.execute("SELECT order_id, total_amount, payment_mode FROM orders").fetchall()
            bills_count = len(orders_rows)
            today_revenue = sum(o["total_amount"] for o in orders_rows)
            avg_bill = round(today_revenue / bills_count, 2) if bills_count else 0.0

            cash = sum(o["total_amount"] for o in orders_rows if o["payment_mode"] == "Cash")
            upi = sum(o["total_amount"] for o in orders_rows if o["payment_mode"] == "UPI")
            card = sum(o["total_amount"] for o in orders_rows if o["payment_mode"] == "Card")

            top_rows = cur.execute("""
                SELECT m.item_name, SUM(oi.quantity) as qty, SUM(oi.line_amount) as rev
                FROM order_item oi
                JOIN menu_item m ON oi.menu_item_id = m.menu_item_id
                GROUP BY oi.menu_item_id
                ORDER BY rev DESC
                LIMIT 5
            """).fetchall()

            top_sellers = [{"name": r["item_name"], "qty": r["qty"], "rev": r["rev"]} for r in top_rows]
            low_count = cur.execute("SELECT COUNT(*) as cnt FROM inventory WHERE quantity <= reorder_level").fetchone()["cnt"]

            conn.close()
            self.send_json({
                "bills_count": bills_count,
                "revenue": round(today_revenue, 2),
                "avg_bill": avg_bill,
                "payment_split": {
                    "Cash": round(cash, 2),
                    "UPI": round(upi, 2),
                    "Card": round(card, 2)
                },
                "top_sellers": top_sellers,
                "low_count": low_count
            })
            return

        # 7. GET /api/reports/week
        if path == "/api/reports/week":
            week_past = [14280, 15840, 12960, 17420, 21360, 26810]
            today_rev_row = cur.execute("SELECT COALESCE(SUM(total_amount), 0) as tot FROM orders").fetchone()
            today_revenue = round(today_rev_row["tot"], 2)
            week_values = week_past + [today_revenue]
            conn.close()
            self.send_json({
                "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                "values": week_values,
                "total": sum(week_values)
            })
            return

        # 8. GET /api/db/<table> (Strict Whitelist + Parameterized)
        if path.startswith("/api/db/"):
            table_name = path[len("/api/db/"):].strip()
            if table_name not in ALLOWED_DB_TABLES:
                conn.close()
                self.send_error_json(f"Access denied: table '{table_name}' is not in the whitelist.", status=404)
                return

            cols_info = cur.execute(f"PRAGMA table_info({table_name})").fetchall()
            columns = [c["name"] for c in cols_info]

            rows_data = cur.execute(f"SELECT * FROM {table_name}").fetchall()
            rows = [[row[c] for c in columns] for row in rows_data]

            conn.close()
            self.send_json({
                "table": table_name,
                "columns": columns,
                "rows": rows,
                "count": len(rows)
            })
            return

        conn.close()
        self.send_error_json("Unknown API endpoint", status=404)

    # --------------------------------------------------------------------------
    # POST ROUTER
    # --------------------------------------------------------------------------
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if not path.startswith("/api/"):
            self.send_error_json("Not found", status=404)
            return

        body = self.read_json_body()
        if body is None:
            self.send_error_json("Invalid JSON payload", status=400)
            return

        try:
            self.handle_api_post(path, body)
        except Exception as e:
            self.send_error_json(f"Server error: {str(e)}", status=500)

    def handle_api_post(self, path, body):
        conn = get_db_connection()
        cur = conn.cursor()

        # 1. POST /api/login
        if path == "/api/login":
            username = body.get("username", "").strip()
            password = body.get("password", "").strip()

            if not username or not password:
                conn.close()
                self.send_error_json("Username and password are required.", status=400)
                return

            user = cur.execute("""
                SELECT u.user_id, u.staff_id, u.username, u.password_hash, u.salt, u.role, s.name
                FROM app_user u
                LEFT JOIN staff s ON u.staff_id = s.staff_id
                WHERE u.username = ? OR u.staff_id = ?
            """, (username, username)).fetchone()

            if not user or not verify_password(user["password_hash"], user["salt"], password):
                conn.close()
                self.send_error_json("Invalid username or password.", status=401)
                return

            token = secrets.token_hex(24)
            SESSIONS[token] = {
                "user_id": user["user_id"],
                "staff_id": user["staff_id"],
                "role": user["role"],
                "username": user["username"],
                "name": user["name"] or user["role"]
            }

            conn.close()
            self.send_json({
                "token": token,
                "role": user["role"],
                "staff_id": user["staff_id"],
                "name": user["name"] or user["role"],
                "username": user["username"]
            })
            return

        # 2. POST /api/orders (SINGLE ATOMIC TRANSACTION)
        if path == "/api/orders":
            items = body.get("items", [])
            payment_mode = body.get("payment_mode", "Cash")
            customer_id = body.get("customer_id")
            billed_by = body.get("billed_by", "Manager · EMP-01")
            order_time = body.get("time") or datetime.now().strftime("%H:%M")

            if not items:
                conn.close()
                self.send_error_json("Order must contain at least one item.", status=400)
                return

            try:
                with conn:  # BEGIN TRANSACTION
                    # 1. Fetch menu prices and recipes
                    subtotal = 0.0
                    order_line_data = []

                    for line in items:
                        item_id = line.get("id") or line.get("menu_item_id")
                        qty = int(line.get("qty", 1))
                        if qty <= 0:
                            continue

                        menu_row = cur.execute("SELECT item_name, price FROM menu_item WHERE menu_item_id = ?", (item_id,)).fetchone()
                        if not menu_row:
                            raise ValueError(f"Menu item '{item_id}' not found.")

                        line_amount = round(menu_row["price"] * qty, 2)
                        subtotal += line_amount
                        order_line_data.append({
                            "menu_item_id": item_id,
                            "item_name": menu_row["item_name"],
                            "price": menu_row["price"],
                            "qty": qty,
                            "line_amount": line_amount
                        })

                    # Server-computed tax and total (5% GST split as CGST 2.5% + SGST 2.5%)
                    tax = round(subtotal * 0.05, 2)
                    cgst = round(tax / 2.0, 2)
                    sgst = round(tax / 2.0, 2)
                    total_amount = round(subtotal + tax, 2)

                    # Verify customer_id if provided
                    if customer_id:
                        cust_row = cur.execute("SELECT customer_id, name FROM customer WHERE customer_id = ?", (customer_id,)).fetchone()
                        if not cust_row:
                            customer_id = None

                    # 2. Insert into orders
                    cur.execute("""
                        INSERT INTO orders (customer_id, order_time, total_amount, payment_mode, billed_by)
                        VALUES (?, ?, ?, ?, ?)
                    """, (customer_id, order_time, total_amount, payment_mode, billed_by))
                    order_id = cur.lastrowid

                    # 3. Insert order_items
                    for line in order_line_data:
                        cur.execute("""
                            INSERT INTO order_item (order_id, menu_item_id, quantity, line_amount)
                            VALUES (?, ?, ?, ?)
                        """, (order_id, line["menu_item_id"], line["qty"], line["line_amount"]))

                    # 4. Decrement inventory rows via recipe table
                    for line in order_line_data:
                        recipe_rows = cur.execute("""
                            SELECT item_id, qty_per_unit FROM recipe WHERE menu_item_id = ?
                        """, (line["menu_item_id"],)).fetchall()

                        for r in recipe_rows:
                            stock_needed = r["qty_per_unit"] * line["qty"]
                            cur.execute("""
                                UPDATE inventory 
                                SET quantity = MAX(0.0, ROUND(quantity - ?, 3))
                                WHERE item_id = ?
                            """, (stock_needed, r["item_id"]))

                    # COMMIT TRANSACTION automatically on block exit
            except Exception as e:
                conn.close()
                self.send_error_json(f"Transaction failed, order rolled back: {str(e)}", status=500)
                return

            bill_no = f"IC/26-27/{order_id:04d}"
            conn.close()
            self.send_json({
                "success": True,
                "order_id": order_id,
                "no": bill_no,
                "time": order_time,
                "mode": payment_mode,
                "customer_id": customer_id,
                "subtotal": round(subtotal, 2),
                "cgst": cgst,
                "sgst": sgst,
                "tax": tax,
                "total": total_amount,
                "items": order_line_data
            }, status=201)
            return

        # 3. POST /api/inventory/restock
        if path == "/api/inventory/restock":
            item_id = body.get("item_id", "").strip()
            if not item_id:
                conn.close()
                self.send_error_json("item_id is required.", status=400)
                return

            row = cur.execute("SELECT item_name, quantity, restock_step, unit FROM inventory WHERE item_id = ?", (item_id,)).fetchone()
            if not row:
                conn.close()
                self.send_error_json(f"Inventory item '{item_id}' not found.", status=404)
                return

            new_qty = round(row["quantity"] + row["restock_step"], 3)
            cur.execute("UPDATE inventory SET quantity = ? WHERE item_id = ?", (new_qty, item_id))
            conn.commit()
            conn.close()
            self.send_json({
                "success": True,
                "item_id": item_id,
                "item_name": row["item_name"],
                "new_quantity": new_qty,
                "restocked_by": row["restock_step"],
                "unit": row["unit"]
            })
            return

        # 4. POST /api/customers
        if path == "/api/customers":
            name = body.get("name", "").strip()
            contact_info = body.get("contact_info", "").strip()

            if not name:
                conn.close()
                self.send_error_json("Customer name is required.", status=400)
                return

            max_id_row = cur.execute("SELECT customer_id FROM customer ORDER BY customer_id DESC LIMIT 1").fetchone()
            if max_id_row and max_id_row["customer_id"].startswith("CUS-"):
                seq = int(max_id_row["customer_id"][4:]) + 1
            else:
                seq = 1
            cust_id = f"CUS-{seq:03d}"

            cur.execute("INSERT INTO customer (customer_id, name, contact_info) VALUES (?, ?, ?)", (cust_id, name, contact_info))
            conn.commit()
            conn.close()
            self.send_json({
                "Customer_id": cust_id,
                "customer_id": cust_id,
                "Name": name,
                "name": name,
                "Contact_info": contact_info,
                "contact_info": contact_info,
                "visits": 0,
                "total_spent": 0,
                "last_visit": "—"
            }, status=201)
            return

        # 5. POST /api/attendance
        if path == "/api/attendance":
            staff_id = body.get("staff_id", "").strip()
            today_str = date.today().strftime("%Y-%m-%d")

            if not staff_id:
                conn.close()
                self.send_error_json("staff_id is required.", status=400)
                return

            staff_row = cur.execute("SELECT name, base_salary FROM staff WHERE staff_id = ?", (staff_id,)).fetchone()
            if not staff_row:
                conn.close()
                self.send_error_json(f"Staff member '{staff_id}' not found.", status=404)
                return

            existing = cur.execute("SELECT attendance_id, status FROM attendance WHERE staff_id = ? AND att_date = ?", (staff_id, today_str)).fetchone()

            if existing:
                if existing["status"] == "Present":
                    cur.execute("UPDATE attendance SET status = 'Absent' WHERE attendance_id = ?", (existing["attendance_id"],))
                    new_status = "Absent"
                else:
                    cur.execute("UPDATE attendance SET status = 'Present' WHERE attendance_id = ?", (existing["attendance_id"],))
                    new_status = "Present"
            else:
                cur.execute("INSERT INTO attendance (staff_id, att_date, status) VALUES (?, ?, 'Present')", (staff_id, today_str))
                new_status = "Present"

            conn.commit()

            days_count = cur.execute("SELECT COUNT(*) as cnt FROM attendance WHERE staff_id = ? AND status = 'Present'", (staff_id,)).fetchone()["cnt"]
            ot = STAFF_OVERTIME_HOURS.get(staff_id, 0)
            base = staff_row["base_salary"]
            per_day = base / 26.0
            earned = per_day * days_count
            ot_pay = ot * (per_day / 8.0) * 1.5
            net_salary = round(earned + ot_pay)

            conn.close()
            self.send_json({
                "success": True,
                "staff_id": staff_id,
                "status": new_status,
                "present": new_status == "Present",
                "days": days_count,
                "days_present": days_count,
                "net_salary": net_salary
            })
            return

        conn.close()
        self.send_error_json("Unknown API endpoint", status=404)

# ==============================================================================
# SERVER ENTRYPOINT
# ==============================================================================

def run_server(port=8000):
    init_db()
    server_address = ("", port)
    httpd = HTTPServer(server_address, CafeHandler)
    print(f"\n========================================================")
    print(f"  Irani Café Management System")
    print(f"  Server running on http://localhost:{port}/")
    print(f"  Database: {DB_PATH}")
    print(f"  Press Ctrl+C to stop.")
    print(f"========================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    run_server(port)
