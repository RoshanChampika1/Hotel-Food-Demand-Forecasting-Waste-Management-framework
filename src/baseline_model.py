import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin


class BaselineMeanModel(RegressorMixin, BaseEstimator):
    """Chef's-rule baseline: the mean per-guest rate from training, ignoring all features.

    Lives in its own module (not train.py) so a saved baseline can be loaded by predict.py and the app.
    """

    def fit(self, X, y):
        self.mean_ = float(np.mean(y))
        return self

    def predict(self, X):
        return np.full(len(X), self.mean_)
