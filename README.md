# mineral-prospectivity-mvp

The data for this project comes from the following source:

https://www.sciencebase.gov/catalog/item/6193e9f3d34eb622f68f13a5

The initial goal is to perform machine learning on Australian portion of this data on MVT deposits in the Northern Territory region.

## Run Archive

- 2026-05-13 22:01:54 +0330 - Archived `v2` in `archive/v2/`: accepted splits = 10 (non-exploratory). Holdout aggregate PR-AUC (average precision, mean across splits) = 0.000132. Holdout top-area capture (mean recall across splits): top 1% = 0.0167, top 5% = 0.3500, top 10% = 0.5500. Major limitations: no spatial buffer, no probability calibration, no uncertainty map; scores are relative prospectivity rankings, not deposit probabilities.

- 2026-05-10 21:43:39 +0330 - Archived `v1` in `archive/v1/`: first end-to-end Northern Territory MVT 500 m workflow with aligned predictors, labels, training table, Random Forest model, prospectivity map, and top-5% map. Test ROC AUC was 0.8900 and average precision was 0.0647, but positive-class recall was 0.00, so this is a baseline run rather than a validated discovery model.

