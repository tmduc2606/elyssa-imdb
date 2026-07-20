import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Embedding, Bidirectional, LSTM, GlobalAveragePooling1D, Dropout, Dense
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


def build_bilstm_model(
    word_index: dict,
    embedding_dim: int = 128,
    embedding_matrix: np.ndarray = None,
    num_classes: int = 28,
    max_len: int = 100,
    lstm_units: int = 64,
) -> Sequential:
    model = Sequential()
    if embedding_matrix is not None:
        model.add(Embedding(
            input_dim=len(word_index) + 1,
            output_dim=embedding_dim,
            weights=[embedding_matrix],
            trainable=False,
        ))
    else:
        model.add(Embedding(
            input_dim=len(word_index) + 1,
            output_dim=embedding_dim,
            trainable=True,
        ))
    model.add(Bidirectional(LSTM(lstm_units, return_sequences=True)))
    model.add(GlobalAveragePooling1D())
    model.add(Dropout(0.5))
    model.add(Dense(num_classes, activation="sigmoid"))
    model.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
    logger.info(f"Built BiLSTM model: {len(word_index)+1} vocab, {embedding_dim} emb, {lstm_units} LSTM")
    return model


def tokenize_texts(
    texts_train: np.ndarray,
    texts_val: np.ndarray,
    texts_test: np.ndarray,
    max_len: int = 100,
    max_words: int = 20000,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    tokenizer = Tokenizer(num_words=max_words)
    tokenizer.fit_on_texts(texts_train)

    train_seq = tokenizer.texts_to_sequences(texts_train)
    val_seq = tokenizer.texts_to_sequences(texts_val)
    test_seq = tokenizer.texts_to_sequences(texts_test)

    train_pad = pad_sequences(train_seq, maxlen=max_len)
    val_pad = pad_sequences(val_seq, maxlen=max_len)
    test_pad = pad_sequences(test_seq, maxlen=max_len)

    return train_pad, val_pad, test_pad, tokenizer.word_index
