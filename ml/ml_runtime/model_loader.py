import os
import pandas as pd
import lightgbm as lgb

DEFAULT_MODEL_PATH = "ml/artifacts/models/lgbm_fhi_v2_grid_best.txt"

class FHIModel:
    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found: {model_path}")
        self.model_path = model_path
        self.booster = lgb.Booster(model_file=model_path)

    def predict_one(self, features: dict) -> float:
        """
        features: dict of {feature_name: value}
        returns: predicted label_fhi (float)

        This aligns input features to the model's training feature list.
        Missing features are filled with 0.0.
        """
        # ✅ model feature names (training-time)
        feat_names = self.booster.feature_name()

        # ✅ build row with exact columns
        row = {name: features.get(name, 0.0) for name in feat_names}

        df = pd.DataFrame([row]).apply(pd.to_numeric, errors="coerce").fillna(0.0)

        pred = self.booster.predict(df)[0]
        return float(pred)
