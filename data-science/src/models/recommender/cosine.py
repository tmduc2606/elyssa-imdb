import numpy as np
import logging

logger = logging.getLogger(__name__)


class CosineRecommender:
    def __init__(self, train_embeddings: np.ndarray, train_ratings: np.ndarray):
        self.train_emb = train_embeddings
        self.train_ratings = train_ratings

    def predict(self, X: np.ndarray) -> np.ndarray:
        from sklearn.metrics.pairwise import cosine_similarity
        preds = []
        for vec in X:
            sims = cosine_similarity([vec], self.train_emb)[0]
            most_similar = np.argmax(sims)
            preds.append(self.train_ratings[most_similar])
        return np.array(preds)
