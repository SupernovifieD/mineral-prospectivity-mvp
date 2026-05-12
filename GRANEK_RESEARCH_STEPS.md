# Granek PhD Research Steps

Source PDF: https://open.library.ubc.ca/soa/cIRcle/collections/ubctheses/24/items/1.0340340

Thesis: Justin Granek, *Application of Machine Learning Algorithms to Mineral Prospectivity Mapping*, PhD thesis, University of British Columbia, December 2016.

This summary describes what Granek did in the thesis, with emphasis on evidential layer preparation, machine learning setup, and reported results. The thesis case study is not MVT mineralization; it is copper-gold porphyry prospectivity in the QUEST region of central British Columbia.

## High-Level Research Goal

Granek framed mineral prospectivity mapping as a supervised learning problem:

- geoscience layers are the input data;
- known mineral occurrences are the labels;
- the trained model estimates mineral potential in under-explored areas.

The research focused on two limitations of mineral prospectivity mapping:

- geoscience data and occurrence labels are uncertain;
- mineral targeting depends on spatial patterns, not only point values.

To address those limitations, he developed and tested two approaches:

- a modified Support Vector Machine / robust Support Vector Regression method that can incorporate uncertainty;
- a Convolutional Neural Network method that can learn spatial patterns from multi-layer geoscience images.

## Study Area And Deposit Type

The real-data case study used the QUEST project area in central British Columbia.

Main study characteristics:

- approximate area: 150,000 square kilometers;
- mineral system: copper-gold porphyry systems;
- setting: established porphyry belts in central British Columbia;
- exploration problem: many easier surface targets were already found, and the central area was partly obscured by thick overburden.

The goal was not to predict drill-hole locations directly. The goal was to highlight regions more likely to host the target mineralization style and reduce exploration risk.

## Data Sources

Granek acquired publicly available layers from:

- Geoscience BC;
- Natural Resources Canada Geophysical Data Repository;
- DataBC online catalogue;
- BC Minfile occurrence database.

The available QUEST datasets included:

- airborne gravity;
- airborne magnetic data;
- airborne electromagnetic / VTEM data;
- geochemical stream and sediment samples;
- ICP-MS analyses for 35 elements;
- bedrock geology era;
- bedrock geology period;
- bedrock geology class;
- bedrock geology type;
- faults;
- known mineral occurrence locations and classifications.

## Evidential Layer Selection

Granek did not simply feed all available data into the model without judgment. He emphasized that expert geological knowledge is necessary when choosing layers.

For copper-gold porphyry targeting, he considered these layer groups especially important:

- airborne isostatic residual gravity;
- airborne residual total magnetic field;
- airborne VTEM electromagnetic data;
- bedrock geology class;
- bedrock geology age;
- bedrock geology primary minerals;
- bedrock geology type;
- faults;
- geochemical pathfinder elements, including Cu, Au, Mo, Ag, As, Sb, Se, U, W, Cd, and Ca.

The geological reasoning was that porphyry systems are structurally controlled and often have combined geological, geochemical, magnetic, gravity, and electromagnetic signatures.

## Evidential Layer Processing

Granek processed the evidential layers in QGIS before machine learning.

The main processing steps were:

1. Load the public geoscience datasets into QGIS.
2. Visually inspect the datasets.
3. Select layers that were geologically relevant to copper-gold porphyry systems.
4. Derive additional geophysical products from magnetic and gravity data.
5. Convert categorical geology into binary indicator layers.
6. Build fault-related proximity and fracturing metrics.
7. Account for regional geochemical background variability.
8. Resample all layers onto a common 300 m by 300 m base grid.
9. Assemble the processed layers into machine-learning-ready inputs.

### Geophysical Processing

Because porphyry systems are structurally controlled, Granek created derivative products from magnetic and gravity data.

The thesis describes using directional filters of the geophysical data to image structures. These derivatives were intended to help identify:

- intrusions;
- faults;
- contacts;
- alteration-related geophysical patterns;
- structural trends relevant to porphyry systems.

### Fault Processing

Faults were treated as important structural evidence.

Granek derived fault-related layers such as:

- proximity to fault systems;
- metrics related to degree of fracturing.

The thesis does not provide a full implementation recipe for these fault metrics, but it clearly states that proximity and fracturing were considered useful predictors.

### Geological Categorical Processing

Granek avoided using arbitrary numeric codes directly for categorical geological classes.

Instead, categorical geology was split into binary indicator layers.

Reason:

- a numeric class code would impose a false ordering;
- for example, volcanic rocks are not more similar to sedimentary rocks just because of alphabetical or numeric order;
- binary indicators let the model treat each class as its own condition.

This is directly relevant to our project because it supports treating lithology classes carefully rather than blindly using ordinal codes.

### Geochemical Processing

Granek noted that regional geochemical data can have strong background variability.

He described the need to account for geochemical background because elemental composition can vary due to:

- bedrock differences;
- surface environment;
- regional effects unrelated to mineral prospectivity.

The thesis does not provide a detailed formula for this background correction in the extracted text, but it clearly identifies background variability as a preprocessing concern before modeling.

### Grid Alignment

All datasets were resampled to a shared 300 m by 300 m grid.

Result:

- more than 700,000 sample points;
- 91 distinct input layers;
- a mixture of continuous and discrete values.

This is similar in spirit to the current 500 m aligned-raster workflow: all predictors need to share a common spatial grid before model training.

## Label Preparation

Granek used the BC Minfile database for known mineral occurrences.

The selected positive labels were:

- 155 known alkalic copper-gold porphyry occurrences.

The Minfile records included:

- location;
- occurrence status;
- mineralization type.

Occurrence status ranged from lower-confidence records such as showings to higher-confidence records such as producers.

## SVM Label Construction

For the SVM workflow, Granek needed a label value for each base-grid sample point.

He created binary labels on the 300 m grid using a radial basis function spline interpolated from the known mineral occurrences.

He also generated label uncertainty estimates using:

- occurrence status from Minfile;
- confidence implied by whether an occurrence was a showing, prospect, mine, producer, etc.;
- overburden extent, because thick cover reduces confidence in mapping and exploration labels.

Label uncertainty ranged from:

- 1: confident label;
- 50: low-confidence label.

Important limitation:

- for the field test, data uncertainties were not applied for simplicity;
- label uncertainty was emphasized more strongly than data uncertainty in the QUEST field application.

## SVM Input Matrix

For the SVM case, each grid point became one row in a large tabular matrix.

The matrix had:

- more than 700,000 rows;
- 91 input layers;
- normalized and scaled input values from 0 to 1.

This was a point-sample formulation:

- each sample was a location;
- each feature was a layer value at that location;
- spatial context was not naturally represented unless manually engineered.

## SVM Algorithm

Granek began with support vector machines because they were a strong and widely used machine learning method.

He first investigated existing SVM software, including libSVM, but wrote custom MATLAB implementations because existing packages did not support the uncertainty handling he wanted.

He developed:

- a modified SVM objective that incorporated uncertainty;
- a robust support vector regression method called L1-RSVR.

The main idea was to make the model less sensitive to unreliable data and labels.

The uncertainty-aware formulation:

- down-weighted or handled labels with lower confidence;
- included a data-error term for uncertain input measurements;
- used robust optimization ideas related to total least squares and L1/L2 penalties.

## SVM Synthetic Test

Before applying the method to real data, Granek tested the robust SVM method on a synthetic dataset.

Synthetic setup:

- 70 sample points;
- two dimensions;
- binary labels;
- two separable Gaussian classes;
- deliberately corrupted by bad data points and bad label points;
- each sample had data uncertainty and label uncertainty.

He split the points into training and prediction subsets by random sampling.

Result:

- the L1-RSVR method handled the uncertain samples better than ordinary SVR without uncertainties;
- most errors occurred on the uncertain labels or intentional outliers;
- the example showed why uncertainty matters in mineral prospectivity mapping.

## SVM QUEST Split Strategy

For the QUEST field application, Granek split the study area geographically.

The split logic was:

- south QUEST: training;
- north QUEST: validation;
- central QUEST: prediction.

Reason:

- known mineralization occurred mostly in the north and south;
- the central area was obscured by thick overburden and had no known mineralization at the time.

This is an important precedent for spatial evaluation, but it is still a single split rather than repeated spatial train/validation/holdout evaluation.

## SVM QUEST Results

Granek did not show the full SVM result using all layers because of a request from NEXT Exploration.

Reported qualitative results:

- the validation map for northern QUEST highlighted known prospective regions;
- it also illuminated potential new exploration areas;
- incorporating uncertainty estimates provided a more robust framework for multidisciplinary data of varying quality.

He also ran a simplified SVM model using only potential-field data:

- magnetics;
- gravity.

That simplified map was less discriminating than the full-data result, which was expected because it used fewer evidence layers.

## CNN Motivation

Granek viewed SVMs as useful but limited for mineral prospectivity because they operate naturally on point values.

The key limitation:

- porphyry exploration depends on spatial arrangements and coincident patterns;
- simple point-value models can miss structures such as halos, contacts, trends, and overlapping anomalies.

He turned to Convolutional Neural Networks because CNNs can learn spatial filters and recognize patterns in image-like data.

## CNN Synthetic Test

Before applying CNNs to QUEST, Granek created a synthetic three-channel dataset.

The three channels represented simplified geoscience patterns:

- channel 1: a smoothly decaying ellipsoid;
- channel 2: a smoothly decaying ring or halo;
- channel 3: a discrete block.

Positive examples were locations where all three structures overlapped.

Negative examples were locations where they did not overlap.

Synthetic dataset:

- 500 positive examples;
- 500 negative examples.

CNN architecture:

- three convolution and pooling stages;
- final softmax classifier;
- 8,702 trainable parameters.

Training details:

- implemented in Julia;
- used nonlinear conjugate gradient optimization rather than the more common stochastic gradient descent;
- used early stopping when validation error increased;
- ran 20 random initializations and reported the best result.

Synthetic CNN result:

| Dataset | Success | Correct | False Positive | False Negative |
| --- | ---: | ---: | ---: | ---: |
| Training | 90.4% | 452/500 | 18 | 30 |
| Validation | 93.6% | 468/500 | 19 | 13 |

Interpretation:

- the CNN learned the intended overlapping spatial pattern;
- some false negatives and false positives were close to the decision boundary, which gave confidence that the model was detecting structure rather than only memorizing values.

## CNN QUEST Data Preparation

CNNs require image patches rather than single point rows.

Granek converted the geoscience grid into windows:

- each window represented a patch of the region;
- approximate window size was 10 km by 10 km;
- the size was chosen based on the expected footprint of a porphyry system.

Positive CNN samples:

- centered on known mineralization locations.

Negative CNN samples:

- selected randomly from locations more than 500 m from any known mineral occurrence;
- intended to represent average background signal;
- selected in equal number to positive samples to balance training.

Data augmentation:

- windows could be shifted;
- windows could be rotated;
- this was intended to reduce sensitivity to translation and orientation.

The thesis also notes that scale invariance could be approached by scaling the data up or down before prediction.

## CNN QUEST Model

The real-data CNN trial used only three input channels:

- gravity;
- magnetics;
- faults.

This was a simplified experiment, not a full 91-layer CNN.

Architecture:

- first layer: eleven 5 by 5 by 3 convolution kernels, sigmoid nonlinearity, 2 by 2 softmax pooling;
- second layer: fifteen 5 by 5 by 11 convolution kernels, sigmoid nonlinearity, 2 by 2 softmax pooling;
- third layer: twenty-seven 3 by 3 by 15 convolution kernels, sigmoid nonlinearity, 2 by 2 softmax pooling;
- final layer: softmax classifier;
- total parameters: 8,702.

Training setup:

- north/south spatial split, similar to the SVM example;
- 20 random initializations because CNNs are nonconvex and sensitive to starting conditions;
- best run was reported.

## CNN QUEST Results

Reported CNN field result:

| Dataset | Success | Correct | False Positive | False Negative |
| --- | ---: | ---: | ---: | ---: |
| Training | 74.3% | 165/222 | 17 | 40 |
| Validation | 80.8% | 42/52 | 8 | 2 |

He then used the trained classifier to create a prospectivity map for the full QUEST region.

Map output:

- values represented probability-like mineralization scores from 0 to 1;
- red indicated more favorable zones;
- blue indicated less favorable zones;
- known mineral occurrences were plotted for reference.

## Comparison Between SVM And CNN

Granek did not present the SVM and CNN comparison as a strict model competition.

Reasons:

- the SVM used the full processed dataset with 91 layers;
- the CNN used only 3 layers;
- the data formats and model assumptions were different.

SVM strengths:

- easier to incorporate data and label uncertainty;
- sparse model based on support vectors;
- easier to interpret through learned weights;
- computationally practical for large tabular data.

SVM weaknesses:

- limited natural handling of spatial structure;
- spatial context must be manually engineered, such as by adding neighboring pixels;
- adding large neighborhoods can make the matrix prohibitively large.

CNN strengths:

- learns spatial filters from the data;
- better suited to halos, contacts, trends, overlapping anomalies, and image-like structure;
- can detect patterns rather than only anomalous point values.

CNN weaknesses:

- harder to interpret;
- more computationally demanding;
- architecture selection is difficult and partly trial-and-error;
- uncertainty handling is less straightforward than in the SVM framework.

Granek noted that the SVM and CNN prospectivity maps had similarities despite being produced independently. He interpreted this as increasing confidence in both results.

## Main Limitations He Identified

Granek explicitly identified several unresolved issues:

- CNNs should eventually use the full geoscience dataset, not only gravity, magnetics, and faults.
- Categorical variables require careful treatment in CNNs so boundaries and classes remain meaningful.
- CNN architecture selection lacks a clear rule and was chosen partly by trial and error.
- Negative labels are uncertain because absence of known mineralization is not proof of barren ground.
- Some randomly selected negative examples may actually overlap undiscovered mineralized zones.
- The choice of training labels can strongly affect the classifier when the positive set is small.
- Adding data uncertainty to CNNs remains an open problem.

## Main Takeaways For This Project

The thesis has several direct lessons for my mineral prospectivity workflow:

1. Spatial alignment matters.
   Granek resampled all layers to a common grid before modeling. My 500 m raster-template workflow follows the same principle.

2. Expert feature selection matters.
   He did not treat all layers as automatically useful. Layer selection was guided by the mineral system model.

3. Categorical geology should be handled carefully.
   His binary-indicator approach avoids false ordinal relationships. My `lithology_code` layer may be useful, but one-hot or binary lithology indicators may be more defensible in later versions.

4. Background labels are not true negatives.
   His CNN negative examples were chosen away from known occurrences, but he acknowledged that some may still be mineralized. This matches my MVT problem.

5. Default classification accuracy is not enough.
   The thesis reports success rates, but for my rare-event MVT workflow I should also report top-area capture, enrichment, PR-AUC, and spatial holdout metrics.

6. Spatial split design matters.
   Granek used geographic splits in QUEST. My next version should go further by using repeated balanced spatial train/validation/holdout splits.

7. Uncertainty should be tracked.
   Granek’s SVM research strongly emphasizes data and label uncertainty. I should record uncertainty or confidence in occurrence labels and evidential layers where possible.

8. CNNs are not the next immediate step.
   The thesis supports CNNs for spatial patterns, but also shows that they add complexity. For my project, a stronger spatial evaluation framework should come before deep learning.

9. Derivative and proximity layers matter.
   He processed geophysics into derivatives and faults into proximity/fracturing evidence. The current distance-to-fault raster is aligned with this idea; future versions could add contacts, density, gradients, and texture features.

10. Prospectivity maps are screening tools.
    Granek emphasized that regional prospectivity maps reduce exploration risk; they do not guarantee discovery.

## Condensed Workflow He Followed

1. Defined the mineral system target: copper-gold porphyry.
2. Selected a data-rich case study: QUEST, central British Columbia.
3. Collected public geoscience data and occurrence labels.
4. Loaded and visually checked layers in QGIS.
5. Selected geologically relevant evidential layers.
6. Derived additional geophysical and structural predictors.
7. Converted categorical geology into binary indicator layers.
8. Considered geochemical background variability.
9. Resampled all layers to a common 300 m grid.
10. Built a 700,000-plus row by 91-layer data matrix for SVM.
11. Selected 155 alkalic Cu-Au porphyry occurrences as positive labels.
12. Interpolated occurrence labels over the grid for SVM using radial basis function splines.
13. Estimated label uncertainty from occurrence status and overburden.
14. Developed uncertainty-aware SVM / L1-RSVR algorithms in MATLAB.
15. Tested the uncertainty-aware SVM on a synthetic uncertain-label/data problem.
16. Trained the SVM on the southern QUEST region.
17. Validated the SVM on the northern QUEST region.
18. Predicted prospectivity in the central QUEST region.
19. Built a custom CNN package in Julia.
20. Tested the CNN on a synthetic three-channel spatial-pattern problem.
21. Converted QUEST data into 10 km image windows for CNN training.
22. Chose positive CNN windows from mineralization locations.
23. Chose negative CNN windows more than 500 m from known occurrences.
24. Used shifts and rotations for augmentation.
25. Trained a simplified CNN using gravity, magnetics, and faults.
26. Ran 20 CNN random initializations and reported the best.
27. Produced a CNN prospectivity map for QUEST.
28. Compared SVM and CNN qualitatively.
29. Concluded that data quality, processing, uncertainty, and expert review are central to useful prospectivity mapping.
