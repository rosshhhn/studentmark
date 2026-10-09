import streamlit as st
import pandas as pd
import sqlite3
import pickle
import hashlib
import hmac
import secrets
import re
from pathlib import Path
from datetime import datetime, timezone

# ------------------------------------------
# 1. Application configuration
# ------------------------------------------

st.set_page_config(
    page_title="Student Pass/Fail Prediction",
    page_icon="🎓",
    layout="wide"
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "student_accounts.db"
MODEL_PATH = BASE_DIR / "student_model.pkl"

# ------------------------------------------
# 2. Database setup
# ------------------------------------------

def get_connection():
    connection = sqlite3.connect(
        DB_PATH,
        timeout=10
    )
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # New table: prediction history
        connection.execute("""
            CREATE TABLE IF NOT EXISTS prediction_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                study_hours REAL NOT NULL,
                attendance INTEGER NOT NULL,
                previous_marks REAL NOT NULL,
                predicted_result TEXT NOT NULL,
                pass_probability REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id)
                    REFERENCES users(id)
            )
        """)


initialize_database()

# ------------------------------------------
# 3. Password hashing
# ------------------------------------------

def hash_password(password, salt_hex=None):
    if salt_hex is None:
        salt = secrets.token_bytes(16)
        salt_hex = salt.hex()
    else:
        salt = bytes.fromhex(salt_hex)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        600_000
    ).hex()

    return salt_hex, password_hash


def verify_password(password, salt_hex, saved_hash):
    _, candidate_hash = hash_password(
        password,
        salt_hex
    )

    return hmac.compare_digest(
        candidate_hash,
        saved_hash
    )

# ------------------------------------------
# 4. Student registration
# ------------------------------------------

def register_user(full_name, email, password):
    full_name = full_name.strip()
    email = email.strip().lower()

    if not 2 <= len(full_name) <= 100:
        return False, "Name must contain 2–100 characters."

    if not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        email
    ):
        return False, "Enter a valid email address."

    if not 8 <= len(password) <= 128:
        return False, "Password must contain 8–128 characters."

    salt, password_hash = hash_password(password)

    try:
        with get_connection() as connection:
            connection.execute("""
                INSERT INTO users (
                    full_name, email, salt,
                    password_hash, created_at
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                full_name,
                email,
                salt,
                password_hash,
                datetime.now(timezone.utc).isoformat()
            ))

        return True, "Account created successfully."

    except sqlite3.IntegrityError:
        return False, "This email is already registered."

# ------------------------------------------
# 5. Student login
# ------------------------------------------

def authenticate_user(email, password):
    with get_connection() as connection:
        user = connection.execute("""
            SELECT id, full_name, email, salt, password_hash
            FROM users
            WHERE email = ?
        """, (email.strip().lower(),)).fetchone()

    if user is None:
        return None

    if not verify_password(
        password,
        user["salt"],
        user["password_hash"]
    ):
        return None

    return {
        "id": user["id"],
        "full_name": user["full_name"],
        "email": user["email"]
    }

# ------------------------------------------
# 6. Save a prediction
# ------------------------------------------

def save_prediction(
    user_id,
    study_hours,
    attendance,
    previous_marks,
    predicted_result,
    pass_probability
):
    with get_connection() as connection:
        connection.execute("""
            INSERT INTO prediction_history (
                user_id,
                study_hours,
                attendance,
                previous_marks,
                predicted_result,
                pass_probability,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            study_hours,
            attendance,
            previous_marks,
            predicted_result,
            pass_probability,
            datetime.now(timezone.utc).isoformat()
        ))

# ------------------------------------------
# 7. Retrieve only this student's history
# ------------------------------------------

def get_prediction_history(user_id):
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT
                id,
                study_hours,
                attendance,
                previous_marks,
                predicted_result,
                pass_probability,
                created_at
            FROM prediction_history
            WHERE user_id = ?
            ORDER BY id DESC
        """, (user_id,)).fetchall()

    return [dict(row) for row in rows]

# ------------------------------------------
# 8. Session state
# ------------------------------------------

if "user" not in st.session_state:
    st.session_state.user = None

# ------------------------------------------
# 9. Registration and login screen
# ------------------------------------------

def show_authentication():
    st.title("🎓 Student Pass/Fail Prediction")
    st.write(
        "Create an account or log in to predict "
        "your academic result and view prediction history."
    )

    register_tab, login_tab = st.tabs([
        "Create Account",
        "Student Login"
    ])

    with register_tab:
        st.subheader("Student Registration")

        with st.form("registration_form"):
            full_name = st.text_input("Full name")
            email = st.text_input("Email address")
            password = st.text_input(
                "Password",
                type="password"
            )
            confirm_password = st.text_input(
                "Confirm password",
                type="password"
            )

            submitted = st.form_submit_button(
                "Register",
                use_container_width=True
            )

        if submitted:
            if password != confirm_password:
                st.error("Passwords do not match.")
            else:
                success, message = register_user(
                    full_name, email, password
                )

                if success:
                    st.success(
                        message + " Please log in."
                    )
                else:
                    st.error(message)

    with login_tab:
        st.subheader("Student Login")

        with st.form("login_form"):
            login_email = st.text_input(
                "Email address",
                key="login_email"
            )
            login_password = st.text_input(
                "Password",
                type="password",
                key="login_password"
            )

            login_submitted = st.form_submit_button(
                "Login",
                use_container_width=True
            )

        if login_submitted:
            if not login_email.strip() or not login_password:
                st.error("Enter your email and password.")
            else:
                user = authenticate_user(
                    login_email,
                    login_password
                )

                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Invalid email or password.")

# ------------------------------------------
# 10. Student dashboard and prediction
# ------------------------------------------

def show_dashboard():
    user = st.session_state.user

    st.title("🎓 Student Dashboard")
    st.write(f"Welcome, **{user['full_name']}**!")
    st.caption(f"Logged in as {user['email']}")

    if st.button("Logout"):
        st.session_state.user = None
        st.rerun()

    st.divider()

    # Load this student's history
    history = get_prediction_history(user["id"])

    st.subheader("📊 Your Summary")

    total_predictions = len(history)
    pass_count = sum(
        item["predicted_result"] == "PASS"
        for item in history
    )
    fail_count = total_predictions - pass_count

    col1, col2, col3 = st.columns(3)

    col1.metric("Total predictions", total_predictions)
    col2.metric("Predicted PASS", pass_count)
    col3.metric("Predicted FAIL", fail_count)

    st.divider()

    # Prediction form
    st.subheader("🔮 Predict Your Result")

    with st.form("prediction_form"):
        study_hours = st.number_input(
            "Daily study hours",
            min_value=0.0,
            max_value=16.0,
            value=4.0,
            step=0.5
        )

        attendance = st.number_input(
            "Attendance (%)",
            min_value=0,
            max_value=100,
            value=75
        )

        previous_marks = st.number_input(
            "Previous exam marks (%)",
            min_value=0.0,
            max_value=100.0,
            value=50.0,
            step=1.0
        )

        predict_clicked = st.form_submit_button(
            "Predict and Save Result",
            type="primary",
            use_container_width=True
        )

    if predict_clicked:
        try:
            with open(MODEL_PATH, "rb") as file:
                model, features = pickle.load(file)

            student = pd.DataFrame([{
                "study_hours": study_hours,
                "attendance": attendance,
                "previous_marks": previous_marks
            }])[features]

            prediction = int(model.predict(student)[0])
            probabilities = model.predict_proba(student)[0]
            classes = list(model.classes_)

            pass_probability = float(
                probabilities[classes.index(1)]
            )

            predicted_result = (
                "PASS" if prediction == 1 else "FAIL"
            )

            # Save the result under the logged-in student ID
            save_prediction(
                user["id"],
                study_hours,
                attendance,
                previous_marks,
                predicted_result,
                pass_probability
            )

            st.session_state.latest_prediction = {
                "result": predicted_result,
                "probability": pass_probability
            }

            st.success("Prediction saved to your history!")

            # Refresh history and dashboard
            st.rerun()

        except FileNotFoundError:
            st.error(
                "Model not found. Run train_model.py first."
            )
        except Exception as error:
            st.error(f"Prediction failed: {error}")

    # Show most recent prediction after a rerun
    latest = st.session_state.get("latest_prediction")

    if latest:
        st.subheader("Latest Prediction")

        if latest["result"] == "PASS":
            st.success("Predicted result: PASS")
        else:
            st.error("Predicted result: FAIL")

        st.metric(
            "Estimated pass probability",
            f"{latest['probability']:.1%}"
        )

        st.caption(
            "This is an experimental estimate, not a guarantee. "
            "Your training dataset is very small, so the "
            "prediction may not be reliable for real students."
        )

    st.divider()

    # Prediction history table
    st.subheader("📜 Your Prediction History")

    # Reload so saved predictions are shown immediately
    history = get_prediction_history(user["id"])

    if history:
        history_df = pd.DataFrame(history)

        history_df = history_df.rename(columns={
            "id": "Record ID",
            "study_hours": "Study Hours",
            "attendance": "Attendance (%)",
            "previous_marks": "Previous Marks (%)",
            "predicted_result": "Predicted Result",
            "pass_probability": "Pass Probability",
            "created_at": "Date and Time"
        })

        history_df["Pass Probability"] = (
            history_df["Pass Probability"] * 100
        ).round(2).astype(str) + "%"

        history_df["Date and Time"] = pd.to_datetime(
            history_df["Date and Time"],
            utc=True
        ).dt.strftime("%Y-%m-%d %H:%M UTC")

        st.dataframe(
            history_df,
            use_container_width=True,
            hide_index=True
        )

        csv_data = pd.DataFrame(history).to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "Download My History as CSV",
            data=csv_data,
            file_name="my_prediction_history.csv",
            mime="text/csv"
        )
    else:
        st.info(
            "No prediction history yet. Make your first "
            "prediction above and it will appear here."
        )

# ------------------------------------------
# 11. Start application
# ------------------------------------------

if st.session_state.user is None:
    show_authentication()
else:
    show_dashboard()