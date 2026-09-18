"""
Fraud Detection ML Model
- Generates synthetic training data if no dataset found
- Trains RandomForest classifier
- Saves model as fraud_model.pkl
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from sklearn.preprocessing import StandardScaler
import joblib
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "fraud_model.pkl")
SCALER_PATH = os.path.join(os.path.dirname(__file__), "scaler.pkl")


def generate_synthetic_data(n_samples: int = 10000) -> pd.DataFrame:
    """Generate realistic synthetic fraud data for training."""
    np.random.seed(42)

    # Legitimate transactions (90%)
    n_legit = int(n_samples * 0.90)
    legit = pd.DataFrame({
        "amount": np.random.exponential(scale=500, size=n_legit).clip(10, 5000),
        "hour": np.random.choice(range(8, 22), size=n_legit),       # daytime
        "is_foreign": np.random.choice([0, 1], size=n_legit, p=[0.95, 0.05]),
        "is_new_device": np.random.choice([0, 1], size=n_legit, p=[0.85, 0.15]),
        "transactions_today": np.random.randint(1, 6, size=n_legit),
        "velocity_score": np.random.uniform(0, 0.3, size=n_legit),
        "Class": 0,
    })

    # Fraudulent transactions (10%)
    n_fraud = n_samples - n_legit
    fraud = pd.DataFrame({
        "amount": np.random.exponential(scale=8000, size=n_fraud).clip(1000, 100000),
        "hour": np.random.choice(list(range(0, 6)) + list(range(22, 24)), size=n_fraud),  # late night
        "is_foreign": np.random.choice([0, 1], size=n_fraud, p=[0.3, 0.7]),
        "is_new_device": np.random.choice([0, 1], size=n_fraud, p=[0.2, 0.8]),
        "transactions_today": np.random.randint(5, 20, size=n_fraud),
        "velocity_score": np.random.uniform(0.6, 1.0, size=n_fraud),
        "Class": 1,
    })

    df = pd.concat([legit, fraud], ignore_index=True).sample(frac=1, random_state=42)
    return df


def train_model():
    """Train and save the fraud detection model."""
    print("🤖 Training Fraud Detection Model...")

    # Load or generate dataset
    dataset_path = os.path.join(os.path.dirname(__file__), "..", "dataset", "fraud.csv")
    if os.path.exists(dataset_path):
        print(f"📂 Loading dataset from {dataset_path}")
        df = pd.read_csv(dataset_path)
        feature_cols = [c for c in df.columns if c != "Class"]
        X = df[feature_cols]
        y = df["Class"]
    else:
        print("📊 Generating synthetic training data (10,000 samples)...")
        df = generate_synthetic_data(10000)
        X = df.drop("Class", axis=1)
        y = df["Class"]

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Scale
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train_scaled, y_train)

    # Evaluate
    y_pred = model.predict(X_test_scaled)
    acc = accuracy_score(y_test, y_pred)
    print(f"✅ Model Accuracy: {acc:.4f}")
    print(classification_report(y_test, y_pred, target_names=["Genuine", "Fraud"]))

    # Save
    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    joblib.dump(list(X.columns), os.path.join(os.path.dirname(__file__), "feature_names.pkl"))
    print(f"💾 Model saved → {MODEL_PATH}")
    return model, scaler


def load_model():
    """Load trained model and scaler."""
    if not os.path.exists(MODEL_PATH):
        train_model()
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    return model, scaler


def predict_fraud(amount: float, hour: int, is_foreign: int,
                  is_new_device: int, transactions_today: int,
                  velocity_score: float) -> dict:
    """Predict fraud probability for a transaction."""
    model, scaler = load_model()

    features = np.array([[amount, hour, is_foreign, is_new_device,
                           transactions_today, velocity_score]])
    features_scaled = scaler.transform(features)

    proba = model.predict_proba(features_scaled)[0]
    fraud_prob = round(float(proba[1]) * 100, 2)

    if fraud_prob < 30:
        risk = "Low"
        status = "Safe"
    elif fraud_prob < 70:
        risk = "Medium"
        status = "Review"
    else:
        risk = "High"
        status = "Fraud"

    return {
        "fraud_probability": fraud_prob,
        "risk_level": risk,
        "status": status,
    }


if __name__ == "__main__":
    train_model()
