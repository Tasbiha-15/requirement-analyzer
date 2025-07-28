import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
import pickle

# Load your dataset
df = pd.read_csv('requirements.csv')

# Print columns to verify
print("Columns in CSV:", df.columns)

# Features and labels
X = df['Requirement']  # Must match your CSV column name exactly
y = df['Label']
X = X.fillna('')  # Replace NaN with empty string


# Vectorize text data with TF-IDF
vectorizer = TfidfVectorizer(stop_words='english')
X_vec = vectorizer.fit_transform(X)

# Train Naive Bayes classifier
classifier = MultinomialNB()
classifier.fit(X_vec, y)

# Save the trained model and vectorizer to files
with open('classifier.pkl', 'wb') as f:
    pickle.dump(classifier, f)

with open('vectorizer.pkl', 'wb') as f:
    pickle.dump(vectorizer, f)

print("Model and vectorizer saved successfully!")
