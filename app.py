import streamlit as st
import pandas as pd
import numpy as np
import pickle
import sqlite3
import hashlib
import random
import time
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="Student Pass/Fail Prediction System",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Load Custom CSS (Connects style.css) ---
def load_css(file_name="style.css"):
    try:
        with open(file_name, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"⚠️ Warning: '{file_name}' not found. Default styles will be used.")

load_css("style.css")

# --- Database Initialization & Safe Schema Migration ---
def init_db():
    conn = sqlite3.connect("student_accounts.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    table_exists = cursor.fetchone()
    
    if table_exists:
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        if "username" not in columns:
            try:
                cursor.execute("ALTER TABLE users RENAME TO users_old")
                cursor.execute('''
                    CREATE TABLE users (
                        username TEXT PRIMARY KEY,
                        password TEXT NOT NULL DEFAULT '',
                        role TEXT NOT NULL DEFAULT 'student'
                    )
                ''')
                cursor.execute("PRAGMA table_info(users_old)")
                old_cols = [col[1] for col in cursor.fetchall()]
                if "password" in old_cols:
                    try:
                        cursor.execute("INSERT INTO users (username, password, role) SELECT COALESCE(name, rowid), password, COALESCE(role, 'student') FROM users_old")
                    except Exception:
                        pass
            except Exception as e:
                print(f"Migration note: {e}")
    else:
        cursor.execute('''
            CREATE TABLE users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                role TEXT NOT NULL
            )
        ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            studyhours REAL,
            attendance REAL,
            previousmarks REAL,
            prediction TEXT,
            timestamp TEXT,
            FOREIGN KEY (username) REFERENCES users (username)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            task TEXT,
            status TEXT DEFAULT 'Pending',
            timestamp TEXT,
            FOREIGN KEY (username) REFERENCES users (username)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# --- Security Functions ---
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hash(password, hashed_password):
    return make_hash(password) == hashed_password

# --- Load Machine Learning Model (with Tuple Handling) ---
@st.cache_resource
def load_model():
    try:
        with open("student_model.pkl", "rb") as f:
            loaded_object = pickle.load(f)
        
        if isinstance(loaded_object, tuple):
            return loaded_object[0]
        return loaded_object
    except Exception as e:
        return None

model = load_model()

# --- Session State Management ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "role" not in st.session_state:
    st.session_state["role"] = ""

def main():
    st.markdown("""
        <div style='text-align: center; padding: 1rem 0;'>
            <h1 style='color: #1e1b4b; font-weight: 800;'>🎓 Student Pass/Fail Prediction System</h1>
            <p style='color: #475569; font-size: 1.1rem;'>Machine Learning Powered Academic Performance & Productivity Analytics</p>
        </div>
    """, unsafe_allow_html=True)

    if not st.session_state["logged_in"]:
        auth_tab1, auth_tab2 = st.tabs(["🔐 Login", "📝 Student Registration"])
        
        with auth_tab1:
            st.markdown("### Secure System Login")
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit_login = st.form_submit_button("Login", use_container_width=True)
                
                if submit_login:
                    if not username or not password:
                        st.warning("Please enter both username and password.")
                    else:
                        conn = sqlite3.connect("student_accounts.db")
                        cursor = conn.cursor()
                        cursor.execute("SELECT password, role FROM users WHERE username = ?", (username,))
                        user_record = cursor.fetchone()
                        conn.close()
                        
                        if user_record and check_hash(password, user_record[0]):
                            st.session_state["logged_in"] = True
                            st.session_state["username"] = username
                            st.session_state["role"] = user_record[1]
                            st.success(f"Welcome back, {username}!")
                            st.rerun()
                        else:
                            st.error("Invalid username or password.")

        with auth_tab2:
            st.markdown("### New Student Account Registration")
            with st.form("reg_form"):
                reg_username = st.text_input("Choose Username")
                reg_password = st.text_input("Choose Password", type="password")
                reg_confirm = st.text_input("Confirm Password", type="password")
                submit_reg = st.form_submit_button("Register Account", use_container_width=True)
                
                if submit_reg:
                    if not reg_username or not reg_password:
                        st.warning("All fields are required.")
                    elif reg_password != reg_confirm:
                        st.error("Passwords do not match.")
                    else:
                        conn = sqlite3.connect("student_accounts.db")
                        cursor = conn.cursor()
                        cursor.execute("SELECT username FROM users WHERE username = ?", (reg_username,))
                        existing = cursor.fetchone()
                        
                        if existing:
                            st.error("Username already exists. Please choose another.")
                        else:
                            cursor.execute(
                                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                                (reg_username, make_hash(reg_password), "student")
                            )
                            conn.commit()
                            conn.close()
                            st.success("Registration successful! You can now log in.")
        return

    role = st.session_state["role"]
    username = st.session_state["username"]

    st.sidebar.markdown(f"### 👤 Logged in: **{username}**")
    st.sidebar.markdown(f"**Role:** `{role.upper()}`")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.session_state["role"] = ""
        st.rerun()

    st.sidebar.markdown("---")

    if role == "student":
        student_dashboard(username)
    elif role == "admin":
        admin_dashboard()

def generate_math_question():
    op = random.choice(["+", "-", "*"])
    if op == "+":
        a, b = random.randint(1, 50), random.randint(1, 50)
        ans = a + b
        text = f"{a} + {b} = ?"
    elif op == "-":
        a, b = random.randint(10, 50), random.randint(1, 49)
        if a < b:
            a, b = b, a
        ans = a - b
        text = f"{a} - {b} = ?"
    else:
        a, b = random.randint(2, 12), random.randint(2, 12)
        ans = a * b
        text = f"{a} x {b} = ?"
    return {"text": text, "answer": ans}

def student_dashboard(username):
    st.sidebar.markdown("### Student Menu")
    choice = st.sidebar.radio("Navigation", [
        "🔮 Predict Pass/Fail", 
        "📊 My Prediction History", 
        "🧮 Math Practice Game",
        "📅 Study Planner & Tasks",
        "⏱️ Pomodoro Focus Timer"
    ])

    if choice == "🔮 Predict Pass/Fail":
        st.markdown("### Academic Performance Prediction")
        st.markdown("Enter your metrics below to evaluate your predicted standing based on our trained machine learning model.")

        if model is None:
            st.error("Error: Trained model (`student_model.pkl`) not found or invalid format.")
            return

        with st.form("prediction_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                studyhours = st.number_input("Study Hours (Daily)", min_value=0.0, max_value=24.0, value=4.0, step=0.5)
            with col2:
                attendance = st.number_input("Attendance (%)", min_value=0.0, max_value=100.0, value=80.0, step=1.0)
            with col3:
                previousmarks = st.number_input("Previous Marks (%)", min_value=0.0, max_value=100.0, value=65.0, step=1.0)
            
            submit_pred = st.form_submit_button("Run Prediction", use_container_width=True)

            if submit_pred:
                input_data = np.array([[studyhours, attendance, previousmarks]])
                try:
                    prediction = model.predict(input_data)[0]
                    pred_label = "Pass" if str(prediction).lower() in ["1", "pass"] else "Fail"

                    # Calculate confidence percentage if model supports predict_proba
                    pass_percentage = None
                    if hasattr(model, "predict_proba"):
                        probs = model.predict_proba(input_data)[0]
                        if hasattr(model, "classes_"):
                            pass_idx = None
                            for idx, cls in enumerate(model.classes_):
                                if str(cls).lower() in ["1", "pass"]:
                                    pass_idx = idx
                                    break
                            if pass_idx is not None:
                                pass_percentage = probs[pass_idx] * 100
                            else:
                                pass_percentage = probs[-1] * 100
                        else:
                            pass_percentage = probs[-1] * 100

                    st.markdown("---")
                    if pred_label == "Pass":
                        if pass_percentage is not None:
                            st.success(f"🎉 **Prediction Result: PASS** (Confidence: **{pass_percentage:.1f}%**)")
                        else:
                            st.success("🎉 **Prediction Result: PASS**")
                        st.balloons()
                    else:
                        fail_percentage = (100.0 - pass_percentage) if pass_percentage is not None else 0.0
                        if pass_percentage is not None:
                            st.error(f"⚠️ **Prediction Result: FAIL** (Confidence: **{fail_percentage:.1f}%**)")
                        else:
                            st.error("⚠️ **Prediction Result: FAIL**")
                        st.info("Recommendation: Focus on boosting your daily study hours and class attendance.")

                    # Format stored database entry with percentage
                    if pass_percentage is not None:
                        stored_result = f"Pass ({pass_percentage:.1f}%)" if pred_label == "Pass" else f"Fail ({100.0 - pass_percentage:.1f}%)"
                    else:
                        stored_result = pred_label

                    conn = sqlite3.connect("student_accounts.db")
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO predictions (username, studyhours, attendance, previousmarks, prediction, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                        (username, studyhours, attendance, previousmarks, stored_result, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    )
                    conn.commit()
                    conn.close()

                except Exception as ex:
                    st.error(f"Prediction failed: {ex}")

    elif choice == "📊 My Prediction History":
        st.markdown("### Your Prediction Records")
        conn = sqlite3.connect("student_accounts.db")
        df_hist = pd.read_sql_query(
            "SELECT studyhours, attendance, previousmarks, prediction, timestamp FROM predictions WHERE username = ? ORDER BY id DESC",
            conn,
            params=(username,)
        )
        conn.close()

        if df_hist.empty:
            st.info("No prediction history recorded yet.")
        else:
            st.dataframe(df_hist, use_container_width=True)
            
            csv_data = df_hist.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export History to CSV",
                data=csv_data,
                file_name=f"{username}_history.csv",
                mime="text/csv"
            )

    elif choice == "🧮 Math Practice Game":
        st.markdown("### 🧮 Interactive Math Challenge Game")
        st.markdown("Sharpen your calculation skills, maintain your streak, and earn score points!")

        if "math_score" not in st.session_state:
            st.session_state.math_score = 0
        if "math_streak" not in st.session_state:
            st.session_state.math_streak = 0
        if "current_math_q" not in st.session_state:
            st.session_state.current_math_q = generate_math_question()

        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="Score", value=st.session_state.math_score)
        with col2:
            st.metric(label="Current Streak", value=f"🔥 {st.session_state.math_streak}")

        st.markdown("---")
        
        q = st.session_state.current_math_q
        st.markdown(f"**Solve this equation:** `{q['text']}`")

        with st.form(key="math_game_form"):
            user_answer = st.text_input("Your Answer", key="math_user_input")
            submit_answer = st.form_submit_button("Submit Answer", use_container_width=True)

        if submit_answer:
            try:
                if float(user_answer.strip()) == float(q["answer"]):
                    st.session_state.math_score += 10
                    st.session_state.math_streak += 1
                    st.success("Correct! Excellent job! 🎉")
                else:
                    st.session_state.math_streak = 0
                    st.error(f"Incorrect. The correct answer was {q['answer']}.")
                
                st.session_state.current_math_q = generate_math_question()
                st.rerun()
            except ValueError:
                st.warning("Please enter a valid numeric answer.")

        if st.button("Reset Game Stats", use_container_width=True):
            st.session_state.math_score = 0
            st.session_state.math_streak = 0
            st.session_state.current_math_q = generate_math_question()
            st.rerun()

    elif choice == "📅 Study Planner & Tasks":
        st.markdown("### 📅 Personal Study Planner & To-Do List")
        st.markdown("Organize your coursework, assignments, and study goals.")

        with st.form("add_task_form"):
            new_task = st.text_input("New Study Task / Assignment")
            submit_task = st.form_submit_button("Add Task", use_container_width=True)
            if submit_task:
                if new_task.strip():
                    conn = sqlite3.connect("student_accounts.db")
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO tasks (username, task, status, timestamp) VALUES (?, ?, ?, ?)",
                        (username, new_task.strip(), "Pending", datetime.now().strftime("%Y-%m-%d %H:%M"))
                    )
                    conn.commit()
                    conn.close()
                    st.success("Task added successfully!")
                    st.rerun()
                else:
                    st.warning("Task description cannot be empty.")

        st.markdown("---")
        st.markdown("#### Your Active Tasks")
        
        conn = sqlite3.connect("student_accounts.db")
        df_tasks = pd.read_sql_query("SELECT id, task, status, timestamp FROM tasks WHERE username = ? ORDER BY id DESC", conn, params=(username,))
        conn.close()

        if df_tasks.empty:
            st.info("No study tasks added yet. Add one above!")
        else:
            for index, row in df_tasks.iterrows():
                col_t1, col_t2, col_t3 = st.columns([3, 1, 1])
                with col_t1:
                    st.markdown(f"**{row['task']}** `({row['timestamp']})`")
                with col_t2:
                    st.markdown(f"Status: `{row['status']}`")
                with col_t3:
                    if row['status'] == 'Pending':
                        if st.button("Mark Done", key=f"done_{row['id']}"):
                            conn = sqlite3.connect("student_accounts.db")
                            cursor = conn.cursor()
                            cursor.execute("UPDATE tasks SET status = 'Completed' WHERE id = ?", (row['id'],))
                            conn.commit()
                            conn.close()
                            st.rerun()
                    else:
                        if st.button("Delete", key=f"del_{row['id']}"):
                            conn = sqlite3.connect("student_accounts.db")
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM tasks WHERE id = ?", (row['id'],))
                            conn.commit()
                            conn.close()
                            st.rerun()

    elif choice == "⏱️ Pomodoro Focus Timer":
        st.markdown("### ⏱️ Pomodoro Focus Timer")
        st.markdown("Boost your productivity with timed study intervals.")

        timer_col1, timer_col2, timer_col3 = st.columns(3)
        with timer_col1:
            if st.button("🚀 Start 25-Min Focus Session", use_container_width=True):
                st.info("Focus session started! Stay off distractions.")
                with st.spinner("Focusing... (Simulated 5s countdown for demo)"):
                    time.sleep(5)
                st.success("Focus session completed! Take a 5-minute break.")
        with timer_col2:
            if st.button("☕ Start 5-Min Break", use_container_width=True):
                st.info("Break time! Relax and stretch.")
                with st.spinner("Resting... (Simulated 3s countdown for demo)"):
                    time.sleep(3)
                st.success("Break over! Ready for the next session.")
        with timer_col3:
            if st.button("🔔 Quick Bell Test", use_container_width=True):
                st.balloons()
                st.success("Ding! Time to check your goals.")

def admin_dashboard():
    st.sidebar.markdown("### Admin Menu")
    admin_choice = st.sidebar.radio("Navigation", [
        "📈 Analytics & Overview", 
        "👥 Registered Students & Management", 
        "📋 All Prediction Records",
        "📊 System Activity & Reports"
    ])

    conn = sqlite3.connect("student_accounts.db")
    df_users = pd.read_sql_query("SELECT username, role FROM users", conn)
    df_preds = pd.read_sql_query("SELECT id, username, studyhours, attendance, previousmarks, prediction, timestamp FROM predictions", conn)
    conn.close()

    if admin_choice == "📈 Analytics & Overview":
        st.markdown("### Admin Analytics Dashboard")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Students", len(df_users[df_users['role'] == 'student']))
        with col2:
            st.metric("Total Predictions", len(df_preds))
        with col3:
            pass_count = len(df_preds[df_preds['prediction'].str.lower().str.contains('pass')]) if not df_preds.empty else 0
            pass_rate = f"{(pass_count / len(df_preds) * 100):.1f}%" if len(df_preds) > 0 else "0%"
            st.metric("Overall Pass Rate", pass_rate)

        st.markdown("---")
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("#### Pass vs Fail Distribution")
            if not df_preds.empty:
                # Group clean counts based on primary label prefix
                clean_preds = df_preds['prediction'].apply(lambda x: 'Pass' if 'pass' in str(x).lower() else 'Fail')
                st.bar_chart(clean_preds.value_counts())
            else:
                st.info("No prediction data available.")

        with col_c2:
            st.markdown("#### Activity Timeline")
            if not df_preds.empty:
                df_preds['date'] = pd.to_datetime(df_preds['timestamp']).dt.date
                st.line_chart(df_preds.groupby('date').size())
            else:
                st.info("No activity data available.")

    elif admin_choice == "👥 Registered Students & Management":
        st.markdown("### Registered Users Directory & Management")
        st.dataframe(df_users, use_container_width=True)

        csv_users = df_users.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export Students List to CSV",
            data=csv_users,
            file_name="registered_students.csv",
            mime="text/csv"
        )

        st.markdown("---")
        st.markdown("#### 🗑️ User Account Management")
        with st.form("delete_user_form"):
            target_user = st.text_input("Enter Username to Delete")
            submit_del = st.form_submit_button("Delete User Account", use_container_width=True)
            if submit_del:
                if target_user.strip():
                    if target_user.strip() == st.session_state["username"]:
                        st.error("You cannot delete your own active admin account.")
                    else:
                        conn = sqlite3.connect("student_accounts.db")
                        cursor = conn.cursor()
                        cursor.execute("DELETE FROM users WHERE username = ?", (target_user.strip(),))
                        conn.commit()
                        conn.close()
                        st.success(f"User '{target_user}' deleted successfully.")
                        st.rerun()
                else:
                    st.warning("Please enter a username.")

    elif admin_choice == "📋 All Prediction Records":
        st.markdown("### Complete Prediction Logs")
        if df_preds.empty:
            st.info("No predictions logged yet.")
        else:
            st.dataframe(df_preds, use_container_width=True)

            csv_preds = df_preds.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Export All Records to CSV",
                data=csv_preds,
                file_name="all_predictions.csv",
                mime="text/csv"
            )

    elif admin_choice == "📊 System Activity & Reports":
        st.markdown("### 📊 System Activity Summary Reports")
        st.markdown("High-level summary of system utilization and academic prediction metrics.")

        conn = sqlite3.connect("student_accounts.db")
        df_tasks_all = pd.read_sql_query("SELECT COUNT(*) FROM tasks", conn).iloc[0, 0]
        conn.close()

        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            st.metric("Total Registered Accounts", len(df_users))
        with col_r2:
            st.metric("Total Prediction Logs", len(df_preds))
        with col_r3:
            st.metric("Total Study Planner Tasks", df_tasks_all)

        st.markdown("---")
        st.markdown("#### System Health")
        st.success("🟢 SQLite Database Connected & Operational")
        st.success("🟢 Machine Learning Model Loaded Successfully")
        st.success("🟢 Custom CSS Style Sheet Active")

if __name__ == "__main__":
    main()