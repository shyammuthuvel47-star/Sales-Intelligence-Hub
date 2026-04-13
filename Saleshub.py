import streamlit as st
import mysql.connector
import pandas as pd
import altair as alt
import time

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Sales Intelligence Hub", layout="wide")

# ---------------- TOAST HELPER ----------------
def show_toast(message, type="success"):
    if type == "success":
        st.toast(f"✅ {message}", icon="✅")
    elif type == "error":
        st.toast(f"❌ {message}", icon="❌")
    elif type == "warning":
        st.toast(f"⚠️ {message}", icon="⚠️")

# ---------------- CUSTOM HEADER ----------------
st.markdown("""
<div style="background: linear-gradient(to right, #ff6b6b, #4ecdc4);
     padding: 20px; border-radius: 10px; text-align:center;">
  <h2 style="color:white;">📊 Sales Intelligence Hub</h2>
  <p style="color:white;">Real-Time Sales Analytics Dashboard</p>
</div>
""", unsafe_allow_html=True)

# ---------------- DB CONNECTION ----------------
def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="sales1"
    )

# ---------------- GET PRIMARY KEY COLUMN ----------------
def get_primary_key(cursor, table):
    cursor.execute(f"""
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = 'sales1' 
        AND TABLE_NAME = '{table}' 
        AND COLUMN_KEY = 'PRI'
        LIMIT 1
    """)
    result = cursor.fetchone()
    return result[0] if result else "id"

# ---------------- AUTO UPDATE STATUS ----------------
def update_status(cursor, conn):
    cursor.execute("""
        UPDATE customer_sales
        SET status = CASE
            WHEN pending_amount <= 0 THEN 'Close'
            ELSE 'Open'
        END
    """)
    conn.commit()

# ---------------- SESSION ----------------
if "user" not in st.session_state:
    st.session_state.user = None

# ---------------- LOGIN PAGE ----------------
if st.session_state.user is None:
    st.subheader("🔐 Login")
    username = st.text_input("User ID")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, role, branch_id 
            FROM users 
            WHERE username=%s AND password=%s
        """, (username, password))
        user = cursor.fetchone()
        conn.close()
        if user:
            st.session_state.user = {"id": user[0], "role": user[1], "branch_id": user[2]}
            st.rerun()
        else:
            st.error("Invalid Credentials ❌")

# ---------------- DASHBOARD ----------------
else:
    conn   = get_connection()
    cursor = conn.cursor()

    role      = st.session_state.user["role"]
    branch_id = st.session_state.user["branch_id"]

    cs_pk = get_primary_key(cursor, "customer_sales")
    ps_fk = "sale_id"

    update_status(cursor, conn)

    # ---------------- LOAD BRANCH MAP ----------------
    cursor.execute("SELECT branch_id, branch_name FROM branches")
    branch_rows = cursor.fetchall()
    branch_map       = {row[0]: row[1] for row in branch_rows}   # id → name
    branch_map_rev   = {row[1]: row[0] for row in branch_rows}   # name → id
    branch_name_list = [row[1] for row in branch_rows]           # ordered list of names

    st.subheader(f"Welcome, {role} 👋")

    if st.button("Logout"):
        st.session_state.user = None
        st.rerun()

    # ---------------- FETCH DATA ----------------
    if role == "Super Admin":
        cursor.execute("SELECT * FROM customer_sales")
    else:
        cursor.execute("SELECT * FROM customer_sales WHERE branch_id=%s", (branch_id,))

    data    = cursor.fetchall()
    columns = [i[0] for i in cursor.description]
    df      = pd.DataFrame(data, columns=columns)

    # Add branch_name column for display/filtering
    df["branch_name"] = df["branch_id"].map(branch_map)

    if df.empty:
        st.warning("No sales data available.")
    else:
        # ================================================================
        # ---------------- ADVANCED FILTERS (moved BEFORE KPIs) ----------
        # ================================================================
        st.subheader("🔎 Advanced Filters")
        col1, col2, col3 = st.columns(3)
        with col1:
            status_filter = st.selectbox("Status", ["All", "Open", "Close"])
        with col2:
            # Branch filter uses branch names
            available_branch_names = sorted(df["branch_name"].dropna().unique().tolist())
            branch_filter = st.selectbox("Branch", ["All"] + available_branch_names)
        with col3:
            product_list   = df["product_name"].unique().tolist()
            product_filter = st.selectbox("Product", ["All"] + product_list)

        col4, col5 = st.columns(2)
        with col4:
            start_date = st.date_input("Start Date", value=pd.to_datetime(df["date"]).min())
        with col5:
            end_date = st.date_input("End Date", value=pd.to_datetime(df["date"]).max())

        min_amount, max_amount = st.slider(
            "Gross Sales Range (₹)",
            int(df["gross_sales"].min()), int(df["gross_sales"].max()),
            (int(df["gross_sales"].min()), int(df["gross_sales"].max()))
        )

        # ---------------- APPLY FILTERS ----------------
        filtered_df = df.copy()
        if status_filter != "All":
            filtered_df = filtered_df[filtered_df["status"] == status_filter]
        if branch_filter != "All":
            filtered_df = filtered_df[filtered_df["branch_name"] == branch_filter]
        if product_filter != "All":
            filtered_df = filtered_df[filtered_df["product_name"] == product_filter]
        filtered_df = filtered_df[
            (pd.to_datetime(filtered_df["date"]) >= pd.to_datetime(start_date)) &
            (pd.to_datetime(filtered_df["date"]) <= pd.to_datetime(end_date))
        ]
        filtered_df = filtered_df[
            (filtered_df["gross_sales"] >= min_amount) &
            (filtered_df["gross_sales"] <= max_amount)
        ]

        # ================================================================
        # ---------------- KPI (based on filtered_df) --------------------
        # ================================================================
        st.subheader("📈 Financial Summary")
        total_sales    = filtered_df["gross_sales"].sum()
        total_received = filtered_df["received_amount"].sum()
        total_pending  = filtered_df["pending_amount"].sum()

        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Total Sales", f"₹{total_sales:,.2f}")
        col2.metric("✅ Received",    f"₹{total_received:,.2f}")
        col3.metric("⏳ Pending",     f"₹{total_pending:,.2f}")

        # ================================================================
        # ---------------- SALES DATA TABLE ------------------------------
        # ================================================================
        display_df = filtered_df.copy()

        # Show branch_name instead of branch_id in the table
        display_df = display_df.drop(columns=["branch_id"])
        # Reorder so branch_name appears early
        cols_order = [c for c in display_df.columns if c != "branch_name"]
        insert_pos = cols_order.index("date") if "date" in cols_order else 0
        cols_order.insert(insert_pos, "branch_name")
        display_df = display_df[cols_order]

        for col in ["gross_sales", "received_amount", "pending_amount"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: f"₹{x:,.2f}")

        def color_status(val):
            if val == "Close":
                return "background-color: #1e8449; color: white;"
            elif val == "Open":
                return "background-color: #c0392b; color: white;"
            return ""

        st.subheader("📋 Sales Data")
        if "status" in display_df.columns:
            try:
                styled = display_df.style.map(color_status, subset=["status"])
            except AttributeError:
                styled = display_df.style.applymap(color_status, subset=["status"])
            st.dataframe(styled, use_container_width=True)
        else:
            st.dataframe(display_df, use_container_width=True)
        st.divider()

        # ================================================================
        # ---------------- BRANCH-WISE SALES CHART (with branch names) ---
        # ================================================================
        st.subheader("📊 Analytics")
        st.write("### Branch-wise Sales")

        # Use the FULL df (unfiltered) for the analytics chart — or filtered_df if you prefer filtered
        chart_df = df.copy()
        branch_sales = chart_df.groupby("branch_name")["gross_sales"].sum().reset_index()
        branch_sales.columns = ["Branch", "gross_sales"]
        branch_sales["Label"] = branch_sales["gross_sales"].apply(lambda x: f"₹{x:,.0f}")

        bar_chart = alt.Chart(branch_sales).mark_bar(
            cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color="#00b7ff"
        ).encode(
            x=alt.X("Branch:N", title="Branch", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("gross_sales:Q", title="Gross Sales (₹)",
                    axis=alt.Axis(format="~s", labelExpr="'₹' + datum.label")),
            tooltip=[
                alt.Tooltip("Branch:N", title="Branch"),
                alt.Tooltip("gross_sales:Q", title="Sales (₹)", format=",.2f")
            ]
        ).properties(height=400)

        bar_labels = alt.Chart(branch_sales).mark_text(
            dy=-10, size=12, fontWeight="bold", color="#ffffff"
        ).encode(
            x=alt.X("Branch:N"),
            y=alt.Y("gross_sales:Q"),
            text=alt.Text("Label:N")
        )
        st.altair_chart(bar_chart + bar_labels, use_container_width=True)
        st.divider()

        # ================================================================
        # ---------------- PAYMENT DISTRIBUTION PIE ----------------------
        # ================================================================
        st.write("### Payment Details")

        if role == "Super Admin":
            branch_options_names = ["All"] + sorted(df["branch_name"].dropna().unique().tolist())
            selected_branch_pie  = st.selectbox("Filter by Branch", branch_options_names, key="pie_branch")
            if selected_branch_pie == "All":
                pie_source = df
            else:
                pie_source = df[df["branch_name"] == selected_branch_pie]
        else:
            pie_source = df

        pie_received = pie_source["received_amount"].sum()
        pie_pending  = pie_source["pending_amount"].sum()

        st.markdown(f"""
        <div style="display:flex; justify-content:center; gap:60px; margin-bottom:10px;">
            <div style="text-align:center;">
                <div style="font-size:22px; font-weight:bold; color:#2ecc71;">
                    ₹{pie_received:,.0f}
                </div>
                <div style="font-size:16px; font-weight:bold; color:#2ecc71; 
                     background:#2ecc7122; border:1px solid #2ecc71;
                     border-radius:8px; padding:4px 16px; margin-top:4px;">
                    ✅ Received
                </div>
            </div>
            <div style="text-align:center;">
                <div style="font-size:22px; font-weight:bold; color:#e74c3c;">
                    ₹{pie_pending:,.0f}
                </div>
                <div style="font-size:16px; font-weight:bold; color:#e74c3c;
                     background:#e74c3c22; border:1px solid #e74c3c;
                     border-radius:8px; padding:4px 16px; margin-top:4px;">
                    ⏳ Pending
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        pie_df = pd.DataFrame({
            "Category":  ["Received", "Pending"],
            "Amount":    [pie_received, pie_pending],
            "LineLabel": ["Received", "Pending"],
            "AmtLabel":  [f"₹{pie_received:,.0f}", f"₹{pie_pending:,.0f}"]
        })

        pie_chart = alt.Chart(pie_df).mark_arc(
            outerRadius=180, stroke="white", strokeWidth=3
        ).encode(
            theta=alt.Theta("Amount:Q"),
            color=alt.Color(
                "Category:N",
                scale=alt.Scale(domain=["Received", "Pending"], range=["#2ecc71", "#e74c3c"]),
                legend=None
            ),
            tooltip=[
                alt.Tooltip("Category:N", title="Category"),
                alt.Tooltip("Amount:Q",   title="Amount (₹)", format=",.2f")
            ]
        ).properties(height=420)

        pie_cat_label = alt.Chart(pie_df).mark_text(
            radius=110, dy=-10, size=16, fontWeight="bold", color="black"
        ).encode(
            theta=alt.Theta("Amount:Q", stack=True),
            text=alt.Text("LineLabel:N")
        )

        pie_amt_label = alt.Chart(pie_df).mark_text(
            radius=110, dy=12, size=14, fontWeight="normal", color="black"
        ).encode(
            theta=alt.Theta("Amount:Q", stack=True),
            text=alt.Text("AmtLabel:N")
        )

        st.altair_chart(pie_chart + pie_cat_label + pie_amt_label, use_container_width=True)
        st.divider()

        # ================================================================
        # ---------------- PAYMENT METHOD SUMMARY ------------------------
        # ================================================================
        st.subheader("💳 Payment Method Summary")

        try:
            cursor.execute(f"""
                SELECT cs.branch_id, ps.payment_method, SUM(ps.amount_paid) AS total
                FROM payment_splits ps
                JOIN customer_sales cs ON ps.{ps_fk} = cs.{cs_pk}
                GROUP BY cs.branch_id, ps.payment_method
            """)
            pay_data = cursor.fetchall()
        except Exception as e:
            st.error(f"❌ Could not load payment summary: {e}")
            st.info(f"💡 Detected primary key: `{cs_pk}`, foreign key used: `{ps_fk}`")
            pay_data = []

        if pay_data:
            df_pay = pd.DataFrame(pay_data, columns=["branch_id", "Method", "Amount"])
            # Map branch_id to branch_name
            df_pay["Branch"] = df_pay["branch_id"].map(branch_map)

            if role == "Super Admin":
                branch_options_pay_names = ["All"] + sorted(df_pay["Branch"].dropna().unique().tolist())
                selected_branch_pay      = st.selectbox("Filter by Branch", branch_options_pay_names, key="pay_branch")
                if selected_branch_pay != "All":
                    df_pay = df_pay[df_pay["Branch"] == selected_branch_pay]

            df_pay_grouped          = df_pay.groupby("Method")["Amount"].sum().reset_index()
            df_pay_grouped["Label"] = df_pay_grouped["Amount"].apply(lambda x: f"₹{x:,.0f}")

            icons_html = {
                "Cash": ("💵", "#f39c12"),
                "UPI":  ("📱", "#8e44ad"),
                "Card": ("💳", "#2980b9")
            }

            st.markdown("#### Payment Methods")
            icon_cols = st.columns(len(df_pay_grouped))
            for i, row in df_pay_grouped.iterrows():
                method = row["Method"]
                emoji  = icons_html.get(method, ("💰", "#555"))[0]
                color  = icons_html.get(method, ("💰", "#555"))[1]
                amount = f"₹{row['Amount']:,.0f}"
                with icon_cols[i]:
                    st.markdown(f"""
                    <div style="background:{color}22; border:2px solid {color};
                         border-radius:12px; padding:20px; text-align:center;">
                        <div style="font-size:40px;">{emoji}</div>
                        <div style="font-size:18px; font-weight:bold; color:{color};">{method}</div>
                        <div style="font-size:22px; font-weight:bold; color:white; margin-top:6px;">{amount}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            col_donut, col_bar = st.columns(2)

            with col_donut:
                st.write("#### By Share")

                donut = alt.Chart(df_pay_grouped).mark_arc(
                    innerRadius=80, outerRadius=160, stroke="white", strokeWidth=2
                ).encode(
                    theta=alt.Theta("Amount:Q"),
                    color=alt.Color(
                        "Method:N",
                        scale=alt.Scale(
                            domain=["Cash", "UPI", "Card"],
                            range=["#f39c12", "#8e44ad", "#2980b9"]
                        ),
                        legend=alt.Legend(title="Payment Method")
                    ),
                    tooltip=[
                        alt.Tooltip("Method:N", title="Method"),
                        alt.Tooltip("Amount:Q", title="Amount (₹)", format=",.2f")
                    ]
                ).properties(height=380)

                donut_method = alt.Chart(df_pay_grouped).mark_text(
                    radius=125, dy=-10, size=15, fontWeight="bold", color="black"
                ).encode(
                    theta=alt.Theta("Amount:Q", stack=True),
                    text=alt.Text("Method:N")
                )

                donut_amount = alt.Chart(df_pay_grouped).mark_text(
                    radius=125, dy=10, size=13, fontWeight="normal", color="black"
                ).encode(
                    theta=alt.Theta("Amount:Q", stack=True),
                    text=alt.Text("Label:N")
                )

                st.altair_chart(donut + donut_method + donut_amount, use_container_width=True)

            with col_bar:
                st.write("#### By Amount")
                icon_map = {"Cash": "💵 Cash", "UPI": "📱 UPI", "Card": "💳 Card"}
                df_pay_grouped["MethodLabel"] = df_pay_grouped["Method"].map(icon_map)

                pay_bar = alt.Chart(df_pay_grouped).mark_bar(
                    cornerRadiusTopLeft=6, cornerRadiusTopRight=6
                ).encode(
                    x=alt.X("MethodLabel:N", title="Payment Method",
                            axis=alt.Axis(labelAngle=0),
                            sort=["💵 Cash", "📱 UPI", "💳 Card"]),
                    y=alt.Y("Amount:Q", title="Amount (₹)",
                            axis=alt.Axis(labelExpr="'₹' + datum.label", format="~s")),
                    color=alt.Color(
                        "Method:N",
                        scale=alt.Scale(
                            domain=["Cash", "UPI", "Card"],
                            range=["#f39c12", "#8e44ad", "#2980b9"]
                        ),
                        legend=None
                    ),
                    tooltip=[
                        alt.Tooltip("Method:N", title="Method"),
                        alt.Tooltip("Amount:Q", title="Amount (₹)", format=",.2f")
                    ]
                ).properties(height=380)

                pay_bar_text = alt.Chart(df_pay_grouped).mark_text(
                    dy=-10, size=13, fontWeight="bold"
                ).encode(
                    x=alt.X("MethodLabel:N", sort=["💵 Cash", "📱 UPI", "💳 Card"]),
                    y=alt.Y("Amount:Q"),
                    text=alt.Text("Label:N"),
                    color=alt.Color(
                        "Method:N",
                        scale=alt.Scale(
                            domain=["Cash", "UPI", "Card"],
                            range=["#f39c12", "#8e44ad", "#2980b9"]
                        ),
                        legend=None
                    )
                )

                st.altair_chart(pay_bar + pay_bar_text, use_container_width=True)

        else:
            st.info("No payment data available.")

    # ================================================================
    # ---------------- ADD SALE --------------------------------------
    # ================================================================
    st.markdown("---")
    st.subheader("➕ Add Sale")

    with st.container():
        st.markdown("""
        <div style="background:#1a1a2e; border:1px solid #4ecdc4; border-radius:12px; padding:20px; margin-bottom:10px;">
        """, unsafe_allow_html=True)

        sale_col1, sale_col2 = st.columns(2)
        with sale_col1:
            name    = st.text_input("👤 Customer Name", placeholder="Enter customer name")
            product = st.selectbox("📦 Product", ["DS", "DA", "BA", "FSD"])
        with sale_col2:
            mobile  = st.text_input("📱 Mobile Number", placeholder="10-digit mobile number")
            amount  = st.number_input("💰 Gross Sales (₹)", min_value=0)

        if role == "Super Admin":
            # Let Super Admin pick branch by name
            branch_name_select = st.selectbox("🏢 Branch", branch_name_list)
            branch_input       = branch_map_rev[branch_name_select]
        else:
            branch_input = branch_id
            st.info(f"🏢 Branch: {branch_map.get(branch_id, branch_id)}")

        st.markdown("</div>", unsafe_allow_html=True)

        add_sale_btn = st.button("➕ Add Sale", type="primary", use_container_width=True)

    if add_sale_btn:
        if not name.strip():
            st.toast("⚠️ Please enter Customer Name!", icon="⚠️")
            st.warning("⚠️ Please enter Customer Name.")
        elif not mobile.strip():
            st.toast("⚠️ Please enter Mobile Number!", icon="⚠️")
            st.warning("⚠️ Please enter Mobile Number.")
        elif len(mobile.strip()) != 10 or not mobile.strip().isdigit():
            st.toast("⚠️ Enter a valid 10-digit Mobile Number!", icon="⚠️")
            st.warning("⚠️ Enter a valid 10-digit Mobile Number.")
        elif amount <= 0:
            st.toast("⚠️ Gross Sales must be greater than 0!", icon="⚠️")
            st.warning("⚠️ Gross Sales must be greater than 0.")
        else:
            try:
                cursor.execute("""
                    INSERT INTO customer_sales 
                    (branch_id, date, name, mobile_number, product_name, gross_sales, status)
                    VALUES (%s, CURDATE(), %s, %s, %s, %s, 'Open')
                """, (branch_input, name.strip(), mobile.strip(), product, amount))
                conn.commit()
                update_status(cursor, conn)

                st.toast(f"🎉 Sale of ₹{amount:,.2f} added for {name.strip()}!", icon="✅")
                st.markdown(f"""
                <div style="background:linear-gradient(90deg,#1e8449,#27ae60);
                     border-radius:10px; padding:16px; text-align:center; margin:10px 0;">
                    <span style="font-size:28px;">🎉</span>
                    <div style="color:white; font-size:18px; font-weight:bold; margin-top:6px;">
                        Sale Entry Added Successfully!
                    </div>
                    <div style="color:#d5f5e3; font-size:14px; margin-top:4px;">
                        Customer: <b>{name.strip()}</b> &nbsp;|&nbsp;
                        Product: <b>{product}</b> &nbsp;|&nbsp;
                        Amount: <b>₹{amount:,.2f}</b>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                conn.rollback()
                st.toast(f"❌ Error: {e}", icon="❌")
                st.error(f"❌ Error adding sale: {e}")

    # ================================================================
    # ---------------- ADD PAYMENT -----------------------------------
    # ================================================================
    st.markdown("---")
    st.subheader("💰 Add Payment")

    with st.container():
        st.markdown("""
        <div style="background:#1a1a2e; border:1px solid #f39c12; border-radius:12px; padding:20px; margin-bottom:10px;">
        """, unsafe_allow_html=True)

        pay_col1, pay_col2, pay_col3 = st.columns(3)
        with pay_col1:
            sale_id     = st.number_input("🔖 Sale ID", min_value=1)
        with pay_col2:
            amount_paid = st.number_input("💵 Amount Paid (₹)", min_value=0)
        with pay_col3:
            method      = st.selectbox("💳 Payment Method", ["Cash", "UPI", "Card"])

        st.markdown("</div>", unsafe_allow_html=True)

        add_pay_btn = st.button("💰 Add Payment", type="primary", use_container_width=True)

    if add_pay_btn:
        if amount_paid <= 0:
            st.toast("⚠️ Amount must be greater than 0!", icon="⚠️")
            st.warning("⚠️ Amount Paid must be greater than 0.")
        else:
            try:
                cursor.execute(f"SELECT name FROM customer_sales WHERE {cs_pk}=%s", (sale_id,))
                sale_rec = cursor.fetchone()
                if not sale_rec:
                    st.toast(f"❌ Sale ID {sale_id} not found!", icon="❌")
                    st.error(f"❌ Sale ID {sale_id} not found.")
                else:
                    cursor.execute("""
                        INSERT INTO payment_splits 
                        (sale_id, payment_date, amount_paid, payment_method)
                        VALUES (%s, CURDATE(), %s, %s)
                    """, (sale_id, amount_paid, method))
                    conn.commit()
                    update_status(cursor, conn)

                    method_icons = {"Cash": "💵", "UPI": "📱", "Card": "💳"}
                    icon = method_icons.get(method, "💰")

                    st.toast(f"Payment of ₹{amount_paid:,.2f} via {method} added!", icon="✅")
                    st.markdown(f"""
                    <div style="background:linear-gradient(90deg,#1a5276,#2980b9);
                         border-radius:10px; padding:16px; text-align:center; margin:10px 0;">
                        <span style="font-size:28px;">{icon}</span>
                        <div style="color:white; font-size:18px; font-weight:bold; margin-top:6px;">
                            Payment Recorded Successfully!
                        </div>
                        <div style="color:#d6eaf8; font-size:14px; margin-top:4px;">
                            Customer: <b>{sale_rec[0]}</b> &nbsp;|&nbsp;
                            Method: <b>{icon} {method}</b> &nbsp;|&nbsp;
                            Amount: <b>₹{amount_paid:,.2f}</b>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    time.sleep(1.5)
                    st.rerun()
            except Exception as e:
                conn.rollback()
                st.toast(f"❌ Error: {e}", icon="❌")
                st.error(f"❌ Error adding payment: {e}")
                st.divider()

    # ================================================================
    # ---------------- SQL QUESTIONS SECTION -------------------------
    # ================================================================
    st.markdown("---")
    st.markdown("""
    <div style="background: linear-gradient(to right, #1a1a2e, #16213e);
         padding: 18px; border-radius: 10px; border-left: 5px solid #4ecdc4; margin-bottom:10px;">
      <h3 style="color:#4ecdc4; margin:0;">🗃️ SQL Query Answers</h3>
      <p style="color:#aaa; margin:4px 0 0 0;">Questions — Basic | Aggregation | Join-Based | Financial Tracking</p>
    </div>
    """, unsafe_allow_html=True)

    # ── BASIC QUERIES ──
    with st.expander("🔹 Basic Queries ", expanded=False):

        st.markdown("**Q1. Retrieve all records from the customer_sales table.**")
        st.code("""SELECT * FROM customer_sales;""", language="sql")
        try:
            cursor.execute("SELECT * FROM customer_sales")
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q2. Retrieve all records from the branches table.**")
        st.code("""SELECT * FROM branches;""", language="sql")
        try:
            cursor.execute("SELECT * FROM branches")
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q3. Retrieve all records from the payment_splits table.**")
        st.code("""SELECT * FROM payment_splits;""", language="sql")
        try:
            cursor.execute("SELECT * FROM payment_splits")
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q4. Display all sales with status = 'Open'.**")
        st.code("""SELECT * FROM customer_sales WHERE status = 'Open';""", language="sql")
        try:
            cursor.execute("SELECT * FROM customer_sales WHERE status = 'Open'")
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q5. Retrieve all sales belonging to the Chennai branch.**")
        st.code("""
SELECT cs.*
FROM customer_sales cs
JOIN branches b ON cs.branch_id = b.branch_id
WHERE b.branch_name = 'Chennai';
""", language="sql")
        try:
            cursor.execute("""
                SELECT cs.*
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
                WHERE b.branch_name = 'Chennai'
            """)
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

    # ── AGGREGATION QUERIES ──
    with st.expander("🔹 Aggregation Queries ", expanded=False):

        st.markdown("**Q1. Calculate the total gross sales across all branches.**")
        st.code("""SELECT SUM(gross_sales) AS total_gross_sales FROM customer_sales;""", language="sql")
        try:
            cursor.execute("SELECT SUM(gross_sales) AS total_gross_sales FROM customer_sales")
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q2. Calculate the total received amount across all sales.**")
        st.code("""SELECT SUM(received_amount) AS total_received FROM customer_sales;""", language="sql")
        try:
            cursor.execute("SELECT SUM(received_amount) AS total_received FROM customer_sales")
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q3. Calculate the total pending amount across all sales.**")
        st.code("""SELECT SUM(pending_amount) AS total_pending FROM customer_sales;""", language="sql")
        try:
            cursor.execute("SELECT SUM(pending_amount) AS total_pending FROM customer_sales")
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q4. Count the total number of sales per branch.**")
        st.code("""
SELECT branch_id, COUNT(*) AS total_sales
FROM customer_sales
GROUP BY branch_id
ORDER BY branch_id;
""", language="sql")
        try:
            cursor.execute("""
                SELECT branch_id, COUNT(*) AS total_sales
                FROM customer_sales
                GROUP BY branch_id
                ORDER BY branch_id
            """)
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q5. Find the average gross sales amount.**")
        st.code("""SELECT ROUND(AVG(gross_sales), 2) AS avg_gross_sales FROM customer_sales;""", language="sql")
        try:
            cursor.execute("SELECT ROUND(AVG(gross_sales), 2) AS avg_gross_sales FROM customer_sales")
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

    # ── JOIN-BASED QUERIES ──
    with st.expander("🔹 Join-Based Queries ", expanded=False):

        st.markdown("**Q1. Retrieve sales details along with the branch name.**")
        st.code("""
SELECT cs.*, b.branch_name
FROM customer_sales cs
JOIN branches b ON cs.branch_id = b.branch_id;
""", language="sql")
        try:
            cursor.execute("""
                SELECT cs.*, b.branch_name
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
            """)
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q2. Retrieve sales details along with total payment received (using payment_splits).**")
        st.code(f"""
SELECT cs.*, COALESCE(SUM(ps.amount_paid), 0) AS total_paid
FROM customer_sales cs
LEFT JOIN payment_splits ps ON ps.sale_id = cs.{cs_pk}
GROUP BY cs.{cs_pk};
""", language="sql")
        try:
            cursor.execute(f"""
                SELECT cs.*, COALESCE(SUM(ps.amount_paid), 0) AS total_paid
                FROM customer_sales cs
                LEFT JOIN payment_splits ps ON ps.sale_id = cs.{cs_pk}
                GROUP BY cs.{cs_pk}
            """)
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q3. Show branch-wise total gross sales (using JOIN & GROUP BY).**")
        st.code("""
SELECT b.branch_name, SUM(cs.gross_sales) AS total_gross_sales
FROM customer_sales cs
JOIN branches b ON cs.branch_id = b.branch_id
GROUP BY b.branch_name
ORDER BY total_gross_sales DESC;
""", language="sql")
        try:
            cursor.execute("""
                SELECT b.branch_name, SUM(cs.gross_sales) AS total_gross_sales
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
                GROUP BY b.branch_name
                ORDER BY total_gross_sales DESC
            """)
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q4. Display sales along with payment method used.**")
        st.code(f"""
SELECT cs.name, cs.product_name, cs.gross_sales,
       ps.payment_method, ps.amount_paid, ps.payment_date
FROM customer_sales cs
JOIN payment_splits ps ON ps.sale_id = cs.{cs_pk}
ORDER BY ps.payment_date DESC;
""", language="sql")
        try:
            cursor.execute(f"""
                SELECT cs.name, cs.product_name, cs.gross_sales,
                       ps.payment_method, ps.amount_paid, ps.payment_date
                FROM customer_sales cs
                JOIN payment_splits ps ON ps.sale_id = cs.{cs_pk}
                ORDER BY ps.payment_date DESC
            """)
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q5. Retrieve sales along with branch admin name.**")
        st.code("""
SELECT cs.name AS customer_name, cs.product_name, cs.gross_sales,
       b.branch_name, u.username AS branch_admin
FROM customer_sales cs
JOIN branches b ON cs.branch_id = b.branch_id
JOIN users u ON u.branch_id = b.branch_id AND u.role = 'Admin'
ORDER BY cs.branch_id;
""", language="sql")
        try:
            cursor.execute("""
                SELECT cs.name AS customer_name, cs.product_name, cs.gross_sales,
                       b.branch_name, u.username AS branch_admin
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
                JOIN users u ON u.branch_id = b.branch_id AND u.role = 'Admin'
                ORDER BY cs.branch_id
            """)
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

    # ── FINANCIAL TRACKING QUERIES ──
    with st.expander("🔹 Financial Tracking Queries ", expanded=False):

        st.markdown("**Q1. Find sales where the pending amount is greater than 5000.**")
        st.code("""
SELECT * FROM customer_sales
WHERE pending_amount > 5000
ORDER BY pending_amount DESC;
""", language="sql")
        try:
            cursor.execute("""
                SELECT * FROM customer_sales
                WHERE pending_amount > 5000
                ORDER BY pending_amount DESC
            """)
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q2. Retrieve top 3 highest gross sales.**")
        st.code("""
SELECT * FROM customer_sales
ORDER BY gross_sales DESC
LIMIT 3;
""", language="sql")
        try:
            cursor.execute("""
                SELECT * FROM customer_sales
                ORDER BY gross_sales DESC
                LIMIT 3
            """)
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q3. Find the branch with highest total gross sales.**")
        st.code("""
SELECT b.branch_name, SUM(cs.gross_sales) AS total_sales
FROM customer_sales cs
JOIN branches b ON cs.branch_id = b.branch_id
GROUP BY b.branch_name
ORDER BY total_sales DESC
LIMIT 1;
""", language="sql")
        try:
            cursor.execute("""
                SELECT b.branch_name, SUM(cs.gross_sales) AS total_sales
                FROM customer_sales cs
                JOIN branches b ON cs.branch_id = b.branch_id
                GROUP BY b.branch_name
                ORDER BY total_sales DESC
                LIMIT 1
            """)
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q4. Retrieve monthly sales summary (group by month & year).**")
        st.code("""
SELECT 
    YEAR(date) AS year,
    MONTH(date) AS month,
    MONTHNAME(date) AS month_name,
    COUNT(*) AS total_sales,
    SUM(gross_sales) AS total_gross,
    SUM(received_amount) AS total_received,
    SUM(pending_amount) AS total_pending
FROM customer_sales
GROUP BY YEAR(date), MONTH(date)
ORDER BY year DESC, month DESC;
""", language="sql")
        try:
            cursor.execute("""
                SELECT 
                    YEAR(date) AS year,
                    MONTH(date) AS month,
                    MONTHNAME(date) AS month_name,
                    COUNT(*) AS total_sales,
                    SUM(gross_sales) AS total_gross,
                    SUM(received_amount) AS total_received,
                    SUM(pending_amount) AS total_pending
                FROM customer_sales
                GROUP BY YEAR(date), MONTH(date)
                ORDER BY year DESC, month DESC
            """)
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

        st.markdown("---")
        st.markdown("**Q5. Calculate payment method-wise total collection (Cash / UPI / Card).**")
        st.code("""
SELECT payment_method, 
       COUNT(*) AS transaction_count,
       SUM(amount_paid) AS total_collected
FROM payment_splits
GROUP BY payment_method
ORDER BY total_collected DESC;
""", language="sql")
        try:
            cursor.execute("""
                SELECT payment_method,
                       COUNT(*) AS transaction_count,
                       SUM(amount_paid) AS total_collected
                FROM payment_splits
                GROUP BY payment_method
                ORDER BY total_collected DESC
            """)
            r = cursor.fetchall()
            c = [i[0] for i in cursor.description]
            st.dataframe(pd.DataFrame(r, columns=c), use_container_width=True)
        except Exception as e:
            st.error(str(e))

    conn.close()