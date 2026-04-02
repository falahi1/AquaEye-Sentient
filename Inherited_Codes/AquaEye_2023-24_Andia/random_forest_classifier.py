# Source: ME5660 Individual Report — Andia Roumina (2023-24)
# Appendix C: Random Forest Classifier
# Preserved as-is. No modifications.

import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import accuracy_score, classification_report
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
from tkinter import messagebox

df = pd.read_csv('Species Data.csv')
X = df.drop('Species', axis=1)
y = df['Species']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

rf = RandomForestClassifier()
param_distributions = {
    'random_state': range(1, 50),
    'max_depth': range(1, 100),
    'n_estimators': [100, 150, 200, 250, 500, 600, 750, 800]
}
search = RandomizedSearchCV(rf, param_distributions, cv=5, scoring='accuracy')
search.fit(X_train, y_train)
rf = search.best_estimator_

y_pred = rf.predict(X_test)
print('Accuracy:', accuracy_score(y_test, y_pred))
print(classification_report(y_test, y_pred))

cm = confusion_matrix(y_test, y_pred, labels=rf.classes_)
ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=rf.classes_).plot()

feature_scores = pd.Series(rf.feature_importances_, index=X.columns).sort_values(ascending=False)
feature_scores.plot.bar(figsize=(16, 12))
plt.xticks(rotation=45, fontsize=12)
plt.title('Species Classification Feature Importance')

unlabelled_data = pd.read_csv('unlabelled data.csv')
Species_pred = unlabelled_data
prediction = rf.predict(Species_pred)
Species_pred['Species'] = prediction


def save():
    save_file = messagebox.askyesno('Results', 'Save results?')
    if save_file:
        Species_pred.to_csv('Species predictions.csv', mode='a', index=False)


save()
