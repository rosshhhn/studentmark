import pandas as pd
import pickle

from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score

# Load CSV data
data = pd.read_csv("students.csv")

features = [
    "study_hours",
    "attendance",
    "previous_marks"
]

X = data[features]

y = data["result"].str.strip().str.lower().map({
    "fail": 0,
    "pass": 1
})

if y.isna().any():
    raise ValueError("Check the result column in students.csv")

# Split data for training and testing
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.25,
    random_state=42,
    stratify=y
)

# Create and train the model
model = make_pipeline(
    StandardScaler(),
    LogisticRegression()
)

model.fit(X_train, y_train)

# Test the model
predictions = model.predict(X_test)

accuracy = accuracy_score(y_test, predictions)

print("Model trained successfully!")
print("Test accuracy:", round(accuracy * 100, 2), "%")

# Save the trained model
with open("student_model.pkl", "wb") as file:
    pickle.dump((model, features), file)

print("Model saved as student_model.pkl")