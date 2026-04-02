# Source: ME5660 Individual Report — Andia Roumina (2023-24)
# Appendix E: k-Nearest Neighbours Classifier
# Preserved as-is. No modifications.

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.impute import KNNImputer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
from tkinter import messagebox

df = pd.read_csv('Species Data.csv')
X = df.drop('Species', axis=1)
y = df['Species']

imputer = KNNImputer(n_neighbors=3)
X = pd.DataFrame(imputer.fit_transform(X), columns=X.columns)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

scaler = StandardScaler()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)

k_values = list(range(1, 25))
k_scores = []
for k in k_values:
    knn = KNeighborsClassifier(n_neighbors=k)
    knn.fit(X_train, y_train)
    k_scores.append(knn.score(X_test, y_test))

best_k = k_values[np.argmax(k_scores)]
plt.plot(k_values, k_scores)
plt.xlabel('k')
plt.ylabel('Accuracy')
plt.title('Accuracy of k values from 1 to 25')

knn = KNeighborsClassifier(n_neighbors=best_k)
knn.fit(X_train, y_train)
y_pred = knn.predict(X_test)
print('Accuracy:', accuracy_score(y_test, y_pred))
print(classification_report(y_test, y_pred))

cm = confusion_matrix(y_test, y_pred, labels=knn.classes_)
ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=knn.classes_).plot()

unlabelled_data = pd.read_csv('unlabelled data.csv')
Species_pred = unlabelled_data
Species_pred_scaled = scaler.transform(Species_pred)
prediction = knn.predict(Species_pred_scaled)
Species_pred['Species'] = prediction


def save():
    save_file = messagebox.askyesno('Results', 'Save results?')
    if save_file:
        Species_pred.to_csv('Species predictions.csv', mode='a', index=False)


save()
