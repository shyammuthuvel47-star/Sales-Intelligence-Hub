# 📊 Sales Intelligence Hub

A real-time, role-based **Sales Analytics Dashboard** built with **Streamlit** and **MySQL**, designed to track branch-wise sales, payment collection, and outstanding dues for a multi-branch business.

---

## 🚀 Overview

Sales Intelligence Hub gives Super Admins and Branch Admins a single dashboard to log sales, record payments, and monitor financial health across branches — with live KPIs, interactive charts, and a built-in SQL query reference panel.

---

## ✨ Features

- **🔐 Role-Based Login** — Super Admin (all branches) vs Branch Admin (their own branch only), authenticated against a MySQL `users` table.
- **📈 Financial Summary KPIs** — Total Sales, Received Amount, and Pending Amount, computed live from filtered data.
- **🔎 Advanced Filters** — Filter sales by status (Open/Close), branch, product, date range, and gross sales amount.
- **📋 Sales Data Table** — Color-coded status (green = Close, red = Open) with currency-formatted columns.
- **📊 Analytics Charts (Altair)**
  - Branch-wise gross sales bar chart
  - Received vs Pending payment donut chart
  - Payment method summary (Cash / UPI / Card) with icon cards, donut, and bar chart
- **➕ Add Sale** — Log a new customer sale with product, amount, and branch (auto-set to `Open` status).
- **💰 Add Payment** — Record a payment split against a sale ID; status auto-updates to `Close` when fully paid.
- **🗃️ Built-in SQL Reference Panel** — 20 categorized SQL questions (Basic, Aggregation, Join-Based, Financial Tracking) with query text and live results, useful as a learning/demo companion.
- **🔔 Toast Notifications** — Success, error, and warning feedback for every action.

---

## 🛠️ Tech Stack

| Layer          | Technology                  |
|----------------|------------------------------|
| Frontend / App | Streamlit                   |
| Database       | MySQL (`mysql-connector-python`) |
| Data Handling  | Pandas                      |
| Visualization  | Altair                      |

---

## 🗂️ Project Structure

```
Sales-Intelligence-Hub/
├── Saleshub.py           # Main Streamlit application
├── projecttesting.ipynb  # Notebook used for testing / exploration
└── README.md
```

---

## 🧩 Database Schema (expected)

The app expects a MySQL database (default name: `sales1`) with the following tables:

**`users`**
| Column     | Description                     |
|------------|----------------------------------|
| user_id    | Primary key                     |
| username   | Login username                  |
| password   | Login password                  |
| role       | `Super Admin` or `Admin`        |
| branch_id  | Linked branch                   |

**`branches`**
| Column       | Description        |
|--------------|---------------------|
| branch_id    | Primary key         |
| branch_name  | Branch display name |

**`customer_sales`**
| Column          | Description                          |
|-----------------|----------------------------------------|
| sale_id (PK)    | Primary key                          |
| branch_id       | Foreign key to `branches`            |
| date            | Sale date                            |
| name            | Customer name                        |
| mobile_number   | Customer mobile number               |
| product_name    | One of `DS`, `DA`, `BA`, `FSD`       |
| gross_sales     | Total sale value                     |
| received_amount | Amount received so far               |
| pending_amount  | Outstanding balance                  |
| status          | `Open` or `Close` (auto-calculated)  |

**`payment_splits`**
| Column         | Description                          |
|----------------|----------------------------------------|
| sale_id (FK)   | References `customer_sales`          |
| payment_date   | Date of payment                      |
| amount_paid    | Amount paid in this transaction      |
| payment_method | `Cash`, `UPI`, or `Card`             |

---

## ⚙️ Setup & Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/shyammuthuvel47-star/Sales-Intelligence-Hub.git
   cd Sales-Intelligence-Hub
   ```

2. **Install dependencies**
   ```bash
   pip install streamlit mysql-connector-python pandas altair
   ```

3. **Set up MySQL**
   - Create a database named `sales1` (or update the connection settings in `Saleshub.py`).
   - Create the tables described above (`users`, `branches`, `customer_sales`, `payment_splits`).
   - Update the `get_connection()` function in `Saleshub.py` with your MySQL host, user, and password.

4. **Run the app**
   ```bash
   streamlit run Saleshub.py
   ```

5. **Log in** using a username/password from your `users` table.

---

## 📌 Notes

- Sale status (`Open`/`Close`) is automatically recalculated on every dashboard load based on `pending_amount`.
- Super Admins can view and filter data across all branches; Branch Admins only see their own branch's data.
- The SQL Query Answers section is included for reference/learning and demonstrates common SQL patterns (aggregation, joins, filtering) against the live database.

---

## 👤 Author

**Shyam** — Data Analyst
