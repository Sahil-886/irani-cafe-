# Irani Café Management System (Three-Tier Full Stack)

A computer science field project implementation for a heritage Irani café in Camp, Pune (S.Y.B.Sc. Computer Science, Nowrosjee Wadia College).

This application turns the client-side prototype into a three-tier architecture:
**SQLite Schema (Source of Truth) → Python 3 API (Business Rules & Transactions) → JavaScript Client (Presentation & Fallback)**.

---

## 1. How to Run

### Requirements
- Python 3.8 or newer (standard library only).
- **Zero `pip install` required** at any point. No external dependencies, no build tools, no Node.js, no bundlers.
- Works offline on machines with no internet access and no administrator privileges.

### Windows
Double-click `run.bat` or open Command Prompt / PowerShell:
```cmd
run.bat
```
*(The batch script tries `py -3 app.py`, then `python app.py`, and prints a clear message if Python is not found).*

### macOS / Linux
Open Terminal in this directory:
```bash
./run.sh
```
or directly:
```bash
python3 app.py
```

### Accessing the System
Once started, open your web browser to:
```
http://localhost:8000/
```
*Note: On first run, `app.py` automatically initializes `cafe.db`, builds the full relational schema, and seeds all initial data. No separate migration or seed step is needed.*

---

## 2. Relational Schema & Entity-Relationship Model

The database schema matches the project's ER diagram entities and attributes:

```
+----------------------------------------------------------------------------------------------------+
|                                      RELATIONAL SCHEMA DIAGRAM                                      |
+----------------------------------------------------------------------------------------------------+

  [irani_cafe]
  ├── cafe_id (PK, TEXT)
  └── cafe_name (TEXT)

  [customer] <─────────────────────────────────┐
  ├── customer_id (PK, TEXT)                   │ (Places: 1 to Many)
  ├── name (TEXT)                              │
  └── contact_info (TEXT)                      │
                                               │
  [orders] ────────────────────────────────────┘
  ├── order_id (PK, INTEGER AUTOINCREMENT)
  ├── customer_id (FK -> customer.customer_id, nullable)
  ├── order_time (TEXT)
  ├── total_amount (REAL)
  ├── payment_mode (TEXT)
  └── billed_by (TEXT)
        │
        │ (Contains: 1 to Many)
        ▼
  [order_item]
  ├── order_item_id (PK, INTEGER AUTOINCREMENT)
  ├── order_id (FK -> orders.order_id, CASCADE)
  ├── menu_item_id (FK -> menu_item.menu_item_id, RESTRICT)
  ├── quantity (INTEGER)
  └── line_amount (REAL)
        │
        │ (Referenced)
        ▼
  [menu_item] <────────────────────────────────┐
  ├── menu_item_id (PK, TEXT)                  │
  ├── item_name (TEXT)                         │
  ├── category (TEXT)                          │
  └── price (REAL)                             │ (Uses: Many to Many)
                                               │
  [recipe] ────────────────────────────────────┤
  ├── menu_item_id (PK, FK -> menu_item)       │
  ├── item_id (PK, FK -> inventory) ───────────┼──────────┐
  └── qty_per_unit (REAL)                      │          │
                                                          ▼
  [inventory] <───────────────────────────────────────────┘
  ├── item_id (PK, TEXT)
  ├── item_name (TEXT)
  ├── unit (TEXT)
  ├── quantity (REAL)
  ├── reorder_level (REAL)
  └── restock_step (REAL)

  [staff] <────────────────────────────────────┐
  ├── staff_id (PK, TEXT)                      │ (Has Attendance: 1 to Many)
  ├── name (TEXT)                              │
  ├── role (TEXT)                              │
  ├── contact (TEXT)                           │
  ├── joining_date (TEXT)                      │
  ├── shift (TEXT)                             │
  └── base_salary (REAL)                       │
        ▲                                      │
        │ (Authenticates: 1 to 1)              │
        │                                      ▼
  [app_user]                             [attendance]
  ├── user_id (PK, INTEGER)              ├── attendance_id (PK, INTEGER)
  ├── staff_id (FK -> staff.staff_id)    ├── staff_id (FK -> staff.staff_id)
  ├── username (TEXT, UNIQUE)            ├── att_date (TEXT)
  ├── password_hash (TEXT, PBKDF2)       └── status (TEXT: 'Present'/'Absent')
  ├── salt (TEXT, HEX)
  └── role (TEXT)
```

---

## 3. Architecture Rationale: Python vs. SQL vs. JavaScript

Examiners standard viva question: *"Which parts are Python, which are SQL, which are JavaScript, and why?"*

| Layer | Technology | Responsibilities | Why This Choice? |
|---|---|---|---|
| **Data** | **SQL (SQLite3)** | Source of truth, schema enforcement, relational joins, table indices, transactional atomicity. | **Integrity & Persistence:** File-based or in-memory arrays lose data on restart or browser refresh. SQLite guarantees ACID properties. Every connection executes `PRAGMA foreign_keys = ON` ensuring referential integrity. When an order is settled, the insertion into `orders`, `order_item`, and the inventory decrement via `recipe` happen inside a **single atomic transaction** (`with conn:`). If any ingredient update fails, the entire bill is rolled back. |
| **Server** | **Python 3 (stdlib)** | HTTP API, static asset server, single-transaction order settlement, password hashing, parameterized querying. | **No Drift in Business Logic:** Currency, GST (5% split as CGST 2.5% + SGST 2.5%), and payroll arithmetic are calculated exclusively on the server. If calculations are duplicated in client JavaScript, formulas drift. Python's standard library (`http.server`, `sqlite3`, `hashlib`, `hmac`, `secrets`) requires **no internet and no `pip install`**, guaranteeing the demo runs anywhere. All SQL queries use `?` parameterized placeholders to eliminate SQL injection risks. |
| **Client** | **JavaScript, HTML5, CSS3** | Presentation layer, 6 views (Counter, Bills, Stock, Staff register, Reports, Database ledger), printable thermal receipts, offline fallback. | **User Experience & Resilience:** JavaScript renders data fetched from the API into an enamel and plaster heritage aesthetic. It never recomputes money. Through a unified `api()` client, if the server is unreachable (or opened via `file://`), the app gracefully displays a calm offline banner (*"Running without the server. Data will not be saved."*) and falls back to in-memory datasets, ensuring the examiner is never presented with a blank screen. |

---

## 4. Security & Business Rules Implementation

1. **Password Security**:
   - App passwords use `hashlib.pbkdf2_hmac('sha256', password, salt, 100000)`.
   - Each user receives a unique cryptographically random 16-byte hex salt (`secrets.token_hex(16)`).
   - Verification uses constant-time string comparison `hmac.compare_digest` to prevent timing attacks.
   - No plaintext passwords exist anywhere in the code or database seed scripts.

2. **SQL Injection Protection**:
   - Every database read and write is parameterized with `?` placeholders.
   - The `/api/db/<table>` endpoint accepts only table names from a strict hardcoded whitelist:
     `ALLOWED_DB_TABLES = {"irani_cafe", "customer", "menu_item", "inventory", "recipe", "staff", "attendance", "orders", "order_item", "app_user"}`.
     Any table outside this set returns `404 Access Denied`.

3. **Single Transaction Order Pipeline**:
   - `POST /api/orders` begins a SQLite transaction.
   - Calculates subtotal from `menu_item` prices.
   - Computes CGST 2.5%, SGST 2.5%, and total.
   - Inserts row into `orders`.
   - Inserts each line into `order_item`.
   - Queries `recipe` join table for each dish and decrements `inventory.quantity`.
   - Commits transaction atomically.

4. **Staff Payroll Computation**:
   - Net salary is calculated dynamically using:
     $$\text{Net Salary} = \left(\frac{\text{base\_salary}}{26} \times \text{days\_present}\right) + \left(\text{overtime\_hours} \times \frac{\text{base\_salary}}{26 \times 8} \times 1.5\right)$$
   - `days_present` is counted live from the `attendance` table rather than stored as a static number on the staff record. Marking attendance immediately updates the month's net payable figure.

---

## 5. Credentials for Demonstration

| Role | Staff ID / Username | Password | Notes |
|---|---|---|---|
| **Manager** | `EMP-01` | `cafe123` | Rustom Irani (Full access to all screens) |
| **Cashier** | `EMP-03` | `cafe123` | Meera Pawar (Counter & billing) |
