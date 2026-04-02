# Source: ME5660 Individual Report — Andia Roumina (2023-24)
# Appendix D: Histogram-Based Gradient Boosting Classifier
# Preserved as-is. No modifications.

import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import accuracy_score, classification_report
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
from tkinter import messagebox

df = pd.read_csv('Species Data.csv')
X = df.drop('Species', axis=1)
y = df['Species']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = HistGradientBoostingClassifier()
param_distributions = {
    'random_state': range(1, 50),
    'min_samples_leaf': range(1, 50)
}
search = RandomizedSearchCV(model, param_distributions, cv=5, scoring='accuracy')
search.fit(X_train, y_train)
model = search.best_estimator_

y_pred = model.predict(X_test)
print('Accuracy:', accuracy_score(y_test, y_pred))
print(classification_report(y_test, y_pred))

cm = confusion_matrix(y_test, y_pred, labels=model.classes_)
ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=model.classes_).plot()

unlabelled_data = pd.read_csv('unlabelled data.csv')
Species_pred = unlabelled_data
prediction = model.predict(Species_pred)
Species_pred['Species'] = prediction


def save():
    save_file = messagebox.askyesno('Results', 'Save results?')
    if save_file:
        Species_pred.to_csv('Species predictions.csv', mode='a', index=False)


save()
