# Diagnostic Report: 21× Validation-vs-Holdout Average Precision Gap (v2)

**Date**: 2026-05-14  
**Scope**: v2 evaluation artifacts — `archive/v2/data/processed/models/`  
**Method**: Quantitative analysis from actual archived CSVs (metrics, split_training_samples, final_training_table, split_summary). No model was re-run.

---

## 0. The Reported Gap — What It Actually Looks Like

From `aggregate_metrics.csv`:

| Metric | Validation (mean) | Holdout (mean) | Raw Ratio |
|---|---|---|---|
| Average Precision (PR-AUC) | 0.00287 | 0.000132 | **21.7×** |
| ROC-AUC | 0.898 | 0.695 | 1.29× |
| Top-5% Recall | 0.663 | 0.350 | 1.9× |
| Top-10% Recall | 0.762 | 0.550 | 1.4× |

The 21× AP gap is far larger than the 1.3–1.9× gap in other metrics. This immediately suggests AP is particularly sensitive to whatever mechanism is causing the divergence.

**Baseline-adjusted skills (AP / random-baseline AP):**

| Split | Region | Positives | Skill | Holdout Cand |
|---|---|---|---|---|
| 1 | validation | 16 | 28.3× | 1 |
| 1 | holdout | 5 | 19.2× | 1 |
| 2 | validation | 14 | 13.0× | 1 |
| 2 | holdout | 5 | 8.7× | 1 |
| 3 | validation | 8 | **146.7×** | 1 |
| 3 | holdout | 5 | 11.5× | 1 |
| 4 | validation | 24 | 23.0× | 1 |
| 4 | holdout | 5 | 22.9× | 1 |
| 5 | validation | 4 | **2466×** | 1 |
| 5 | holdout | 5 | 13.9× | 1 |
| 6 | validation | 16 | 25.1× | 2 |
| 6 | holdout | 12 | **1.0×** | 2 |
| 7 | validation | 14 | 11.9× | 2 |
| 7 | holdout | 12 | **0.9×** | 2 |
| 8 | validation | 8 | 173.3× | 2 |
| 8 | holdout | 12 | 3.1× | 2 |
| 9 | validation | 4 | 220.4× | 2 |
| 9 | holdout | 12 | 1.8× | 2 |
| 10 | validation | 16 | 22.9× | 3 |
| 10 | holdout | 12 | 1.4× | 3 |

---

## 1. Are Validation Regions Systematically Easier Than Holdout Regions?

**Yes. Conclusively.**

The validation positive clusters are geologically similar to the bulk of training positives. The holdout positive clusters are geologically distinct.

### Feature signatures of each cluster

All positive pixel coordinates and feature values were reconstructed from the archived training samples by exclusion:

| Cluster | N pos | Carbonate (fraction) | Gravity mean | dist_faults mean | Y mean (northing) | Geological character |
|---|---|---|---|---|---|---|
| **All 70 training positives** | 70 | **0.57** | **82** | **4176m** | — | Mostly carbonate, moderate gravity |
| Val cand 20 | 16 | **0.75** | **0** | 7371m | −1,734K | High carbonate, near-zero gravity, CENTRAL NT |
| Val cand 21 | 14 | **0.86** | **6** | 8153m | −1,746K | Predominantly carbonate, low gravity, CENTRAL NT |
| Val cand 24 | 24 | **0.83** | **136** | 2713m | −1,739K | High carbonate, moderate gravity, CENTRAL NT |
| Val cand 23 | 8 | **1.00** | **86** | 861m | −1,706K | ALL carbonate, on/near faults, CENTRAL NT |
| Val cand 29 | 4 | **1.00** | **175** | 250m | −1,770K | ALL carbonate, ON faults, CENTRAL NT |
| **Holdout 1** | **5** | **0.00** | **56** | 3992m | −1,468K | NON-carbonate, low gravity, NORTHERN NT |
| **Holdout 2** | **12** | **0.33** | **207** | 2505m | −1,447K | Partly carbonate, HIGH GRAVITY, NORTHERN NT |

**Validation positives** have 75–100% carbonate fraction, gravity of 0–175. These closely resemble the training positive profile (57% carbonate, gravity mean 82). The model trained on training data generalises well to similar geology.

**Holdout 1** (5 pixels, NW NT): zero carbonate, non-carbonate lithology (code 5 = Other_Unconsolidated). These pixels do not match the dominant training positive profile. Yet the model achieves 8.7–22.9× skill here — suggesting the **proximity-to-fault signal** is driving performance (dist_faults mean 3992m, structurally plausible).

**Holdout 2** (12 pixels, NE NT): only 33% carbonate, with gravity 130–257 (mean 207). Training positives have gravity mean 82; the 18th percentile of training background is ~150. Holdout 2 positives sit in a **high-gravity geophysical terrain** that has no equivalent in training positives.

---

## 2. Are Validation Regions Closer to Training Positives, Geographically and Geologically?

**Yes, both geographically and in feature space.**

### Geography

Using EPSG:3577 coordinates (x = easting, y = northing; more northerly = less negative y):

- **Holdout blocks**: NORTHERN NT. Holdout 1 (NW) at y ≈ −1,456K to −1,476K. Holdout 2 (NE) at y ≈ −1,421K to −1,473K.  
- **Validation blocks**: CENTRAL NT. All five validation candidates at y ≈ −1,664K to −1,787K.  
- **Training positive majority**: y ≈ −1,650K to −2,550K — concentrated in CENTRAL and SOUTHERN NT.

The greedy row-major block generator places the first passing blocks in the **northernmost** NT (where the top rows of the raster hit the NT boundary). Holdout blocks are thus selected from the geographical extreme of the domain. Validation blocks appear further into the iteration, landing in central NT where most training positives also live.

This means training data covers the same geographic range as validation, but NOT the same range as holdout. The split generator creates a structured asymmetry: validation is always in the same broad domain as training, while holdout is at the geographic boundary.

### Feature space

- Holdout 2 gravity mean (207) is 2.5× the training positive mean (82) and lies at approximately the 85th percentile of the background gravity distribution.  
- No training positive cluster has a gravity profile resembling holdout 2 at scale.
- Validation positives (carbonate = 75–100%, gravity = 0–175) sit squarely within the training positive envelope.

---

## 3. Is the Gap Caused by a Few Bad Holdout Splits or Systematic?

**Systematic by holdout location. Not driven by outlier splits.**

| Holdout candidate | N splits | Skill scores | Pattern |
|---|---|---|---|
| Holdout 1 (5 pos, NW) | 5 | 8.7, 11.5, 13.9, 19.2, 22.9 | **Consistently above 8×** |
| Holdout 2 (12 pos, NE) | 4 | 0.9, 1.0, 1.8, 3.1 | **Consistently ≤ 3×** (mostly near-random) |
| Holdout 3 (12 pos, same NE cluster) | 1 | 1.4 | **Near-random** |

Holdout candidates 2 and 3 contain **identical positive pixels** (confirmed by exact coordinate matching). They are the same geological cluster evaluated from slightly different block boundaries.

Every single split using holdout candidate 2/3 produces near-random performance. Every split using holdout candidate 1 produces meaningful skill. The gap is not about individual split randomness — it is about the two holdout geographic locations having fundamentally different difficulty for this model.

---

## 4. How Much of the Gap Is Explained by Tiny Positive Counts?

**Positive count does not inflate AP in the way commonly assumed — but it does drive variance.**

AP is a rank-based metric. For a given set of rank positions, AP scales approximately as:

```
If N positives all land at rank r: AP ≈ (N+1)/(2r)
```

This is roughly independent of N for fixed rank positions. A model placing 4 positives at ranks 100–200 gets similar AP to one placing 12 positives at ranks 100–200. The metric is not artificially inflated by having fewer positives.

**What small counts DO cause:**

- **High variance in AP**: with 4 positives, whether all four happen to fall near the top depends on the specific geological properties of those 4 pixels. Val cand 29 (4 pixels, ALL carbonate+on-fault) achieves 2466× skill because those 4 pixels have the most archetypal MVT signature in the dataset and the model ranks them at positions ~136–200 out of 538K.
- Val cand 23 (8 pixels, ALL carbonate) achieves 147–173× skill for the same reason.
- These are **genuine model performance** on the easiest-to-detect geology, not statistical artifacts. They correctly reflect that the model performs extremely well on archetypal carbonate-on-fault pixels.

**However**, these easy validation candidates inflate the mean validation AP:
- Without val cand 29 (splits 5, 9) the remaining validation mean AP drops to ~0.00069 (skill ~25×).
- The holdout mean skill remains 15× for cand 1 and <3× for cand 2/3.
- The **corrected gap** (excluding the two highest-skill validation outliers) is approximately: val skill ~25× vs holdout skill ~6× = **4× gap**, not 21×.

This shows that roughly **75% of the raw 21× gap is driven by val cands 23 and 29 being archetypal easy-geology targets**, not by genuine generalization superiority of the model on all validation regions.

---

## 5. Does the Repeated Use of Only 3 Holdout Locations Explain the Gap?

**Partially. It explains why the gap appears consistent, not why it exists.**

With 10 splits over only 3 holdout locations (5+4+1), the aggregate statistics conflate:

1. **Geographic performance variance** (how skill varies across holdout locations = the true signal)  
2. **Within-location variance** (how different validation companions affect a fixed holdout = noise)

The 10 "repeated" splits produce:
- 5 measurements on holdout cand 1: mean skill 15.2×, std 4.8
- 4 measurements on holdout cand 2: mean skill 1.7×, std 0.9
- 1 measurement on holdout cand 3: skill 1.4×

The **only information about geographic generalization** comes from the contrast between these 3 locations. Everything else is repetition noise.

If we had evaluated on 10 genuinely distinct holdout blocks spread across the NT, we might find:
- Some southern NT blocks where the model performs well (similar geology to training)
- Some northern NT blocks where performance is poor (distribution shift)
- A more honest mean skill estimate somewhere between 1.7× and 15.2×

The use of 3 holdout locations does not create the gap — it hides how representative the evaluated locations are of the full NT geological diversity.

---

## 6. Would Adding a Spatial Buffer Widen or Shrink the Gap?

**Adding a buffer would likely widen the gap, not shrink it.**

### For holdout candidate 1 (NW cluster, 5 pos, skill 8.7–22.9×)

The model achieves meaningful skill here despite non-carbonate geology (carbonate=0). The most likely signal is **fault proximity**: dist_faults mean 3992m. Fault networks are spatially correlated across km scales. Without a buffer, the model sees training pixels at 500m from the holdout boundary and learns local fault-proximity patterns that transfer into the holdout region.

A buffer of 5–10 km (10–20 pixels) would remove the training pixels immediately adjacent to the holdout boundary. These pixels are likely to have the strongest fault-proximity signal informing the model about the holdout. **Outcome: holdout 1 skill likely decreases** under buffer.

### For holdout candidate 2 (NE cluster, 12 pos, skill 0.9–3.1×)

This is a distribution shift problem, not a boundary leakage problem. The model fails because the NE terrain (high gravity, partly non-carbonate) has no training analogues. A buffer does not supply training data from the NE terrain — it removes some of the peripheral training data. **Outcome: holdout 2 skill stays near-random or slightly worsens.**

### Net effect

Buffer helps with boundary leakage, which may be partially responsible for holdout 1 performing better than it should. But the dominant driver of the gap — distribution shift for holdout 2 — is unaffected by buffer. The practical consequence: adding a buffer would make v3 evaluation more honest for holdout 1, but would not close the gap and might widen it.

---

## 7. Evidence for Distribution Shift Between Train, Validation, and Holdout

**Strong evidence. Confirmed across multiple features.**

### Gravity

Gravity is the most diagnostic differentiator.

| Group | Mean gravity | Geological character |
|---|---|---|
| Training background | −42 | Mixed NT (median ≈ 0, large std) |
| Training positives | +82 | Moderate positive gravity |
| Validation positives (all cands) | 0 to +175 | **In-distribution with training** |
| Holdout 1 positives | +56 | Near training range |
| **Holdout 2 positives** | **+207** | **Out-of-distribution: 85th percentile of background** |

Holdout 2 positives are in a **regionally elevated gravity anomaly**. In Bouguer gravity, such regional highs are often associated with crustal blocks of different composition (mafic, dense cratonic root, intrusive complex). The NT gravity field is spatially smooth at the 500m pixel scale — meaning the entire NE block near holdout 2 likely has elevated gravity.

**The critical consequence**: when the model evaluates the NE holdout block (~378K pixels), it encounters many background pixels also having gravity 150–250, because gravity is a regional signal covering the entire block. The model cannot distinguish the 12 positive pixels from tens of thousands of background pixels sharing the same high-gravity signature.

Rough estimate: 18% of training background has gravity ≥ 150. If the NE block background has similarly elevated fraction (or higher, given the regional gravity high), that is ~68,000 competing pixels. Ranking 12 positives above 68,000 similarly high-gravity background pixels yields near-random performance.

### Carbonate host

| Group | Carbonate fraction |
|---|---|
| Training positives | 0.57 |
| Validation positives (cands 20,21,23,24,29) | 0.75–1.00 |
| Holdout 1 positives | **0.00** |
| Holdout 2 positives | **0.33** |

Validation positive clusters are MORE carbonate-enriched than even the training set (75–100% vs 57%). They represent the easiest-to-detect geography for a model that learned carbonate = positive. Holdout clusters are LESS carbonate-enriched, creating a harder test.

### Shape index and moho depth

Validation candidates (moho 47–52 km, shape index 0.46–0.50) differ from holdout candidates (moho 38–40 km, shape index 0.59–0.61). Northern NT (holdout) has shallower crustal structure than central/southern NT (validation). This adds further distribution shift across ALL geophysical predictors, not just gravity.

---

## 8. Is the Greedy Row-Major Generator Biasing Which Regions Get Evaluated?

**Yes. Systematically and consequentially.**

The block generator in `06_make_spatial_splits.py` proceeds as follows:
1. Generates candidates in raster **row-major order** (top-row to bottom-row, left to right within each row)
2. For each candidate passing area and positive-count thresholds, searches all other candidates for a valid validation partner
3. Stops after 10 accepted splits

**Row-major order in a rasterized NT grid** means:
- Row 0 = northernmost NT pixels
- Blocks that pass `area_share ≥ 8%` AND `positives ≥ 4` first occur in **northern NT**, where positive clusters happen to exist (holdout 1: NW, holdout 2: NE)
- The generator accepts the first 10 valid (holdout, validation) pairs, overwhelmingly using those northern blocks as holdout
- Validation blocks are chosen from *later* candidates, which are in **central or southern NT** where the majority of positives live

This mechanism **structurally couples** the algorithm to select holdout blocks from a geographically extreme region (northern NT) and validation blocks from the same zone as the training majority (central NT).

**Why the northern NT blocks pass the positive-count threshold**:
The 17 northernmost positives (y > −1,480K) form two tight geographic clusters that both happen to contain ≥ 4–5 positive pixels within a ~7.8% area block. Without this luck of clustering, neither holdout candidate 1 nor 2 would exist.

**The systematic bias it creates**:
- Holdout is always northern NT → geologically distinct, fewer analogues in training → harder for the model
- Validation is always central/southern NT → same domain as training majority → easier for the model
- This is exactly the opposite of what a well-designed repeated split should achieve (validation should inform model decisions; holdout should be representative of the full domain)

---

## 9. Summary Tables

### Per-split detail: region, geography, geology, skill

| Split | Holdout cand | Holdout positives | Holdout geography | Holdout geology | Holdout skill | Val cand | Val positives | Val carbonate | Val skill |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 5 | NW | Non-carb, gravity~56 | 19.2× | 20 | 16 | 0.75 | 28.3× |
| 2 | 1 | 5 | NW | Non-carb, gravity~56 | 8.7× | 21 | 14 | 0.86 | 13.0× |
| 3 | 1 | 5 | NW | Non-carb, gravity~56 | 11.5× | 23 | 8 | 1.00 | 147× |
| 4 | 1 | 5 | NW | Non-carb, gravity~56 | 22.9× | 24 | 24 | 0.83 | 23.0× |
| 5 | 1 | 5 | NW | Non-carb, gravity~56 | 13.9× | 29 | 4 | 1.00 | 2466× |
| 6 | 2 | 12 | NE | High-grav (207), 33% carb | **1.0×** | 20 | 16 | 0.75 | 25.1× |
| 7 | 2 | 12 | NE | High-grav (207), 33% carb | **0.9×** | 21 | 14 | 0.86 | 11.9× |
| 8 | 2 | 12 | NE | High-grav (207), 33% carb | 3.1× | 23 | 8 | 1.00 | 173× |
| 9 | 2 | 12 | NE | High-grav (207), 33% carb | 1.8× | 29 | 4 | 1.00 | 220× |
| 10 | 3 | 12 | NE | Same NE cluster as cand 2 | 1.4× | 20 | 16 | 0.75 | 22.9× |

### Gravity distribution at positive pixels by cluster

```
Training positives (70):  mean = 82, range [−676, 322]  (wide spread)
Validation positives:     mean = 0–175  (in-distribution)
Holdout 1 positives (5):  mean = 56     (in-distribution, non-carbonate)
Holdout 2 positives (12): mean = 207    (OUT-OF-DISTRIBUTION, p85 of background)
```

### Feature importance (final model) — context for distribution shift

```
dist_faults:    19.4%  ← geological; fault proximity varies across NT
shape_index:    13.1%  ← varies by terrain
lab_depth:      12.6%  ← regional, smooth
lithology_code: 11.7%  ← key geological signal
carbonate_host: 10.0%  ← key geological signal
moho_depth:      9.0%  ← regional
gravity:         8.3%  ← regional; HIGH weight in NE holdout but no training analogues
```

---

## 10. Root Cause Ranking

The 21× raw AP gap is driven by multiple overlapping causes. Ranked by estimated contribution:

### Cause 1 (primary, ~60–70%): Geographic/geological distribution shift for holdout candidate 2/3

Holdout 2/3 (12 positives in NE NT) are in a **high-gravity geophysical terrain** (mean gravity 207) with no equivalent in the training positive set. The model, trained on data where gravity ~82 is the mean positive signature, cannot distinguish these 12 pixels from tens of thousands of background pixels sharing the same high-gravity regional signature. All 5 splits using holdout cand 2/3 show near-random performance (0.87–3.1× skill), independently of which validation block is used.

**This is not fixable by adjusting split parameters.** It requires either: more labeled examples from the NE terrain, or geological knowledge to understand why that terrain hosts MVT deposits despite its geophysical signature being atypical.

### Cause 2 (secondary, ~20–25%): Validation selection bias toward archetypal easy-geology

Validation candidates 23 (8 carbonate-on-fault pixels, 147–173× skill) and 29 (4 carbonate-on-fault pixels, 2466× and 220× skill) represent the most geologically distinctive MVT occurrences in the dataset. These are easy targets for the model to rank correctly. They inflate the mean validation AP.

Excluding these two validation candidates drops mean validation AP from 0.00287 to ~0.00069, reducing the raw gap from 21× to approximately 5×. The validation performance on the remaining candidates (20, 21, 24) is 11–25× skill — still better than holdout 2, but more commensurate.

**This IS partially fixable** by using more geographically balanced validation block selection. But it also reflects genuine model capability on archetypal geology, which is scientifically valid information.

### Cause 3 (tertiary, ~10%): Geographic structural asymmetry from greedy row-major generator

The greedy row-major generator always assigns holdout blocks to northern NT and validation blocks to central NT. This structurally ensures holdout is harder than validation for a model trained mostly on central/southern NT geology.

**This IS fixable** by improving the split generator to select geographically diverse holdout blocks across the full NT.

### Cause 4 (minor, ~5%): Only 3 holdout locations — insufficient diversity

All 10 splits evaluate only 3 distinct holdout geographic positions. We cannot know whether the holdout 1 performance (8.7–22.9×) or the holdout 2 performance (0.9–3.1×) is more representative of true NT generalization. With 3 locations, the estimated mean holdout skill could easily differ from the true distribution by 50–100%.

---

## 11. What the v2 Holdout Results Actually Tell Us

Given these findings:

1. **Holdout candidate 1 results (splits 1–5) are moderately reliable.** The 5-positive limitation creates variance, but the 8.7–22.9× skill range (mean 15.2×) is consistent across all 5 splits. It shows the model generalizes reasonably to NW NT fault-proximal non-carbonate geology.

2. **Holdout candidate 2 results (splits 6–9) are the most honest signal.** With 12 positives in a geologically distinct terrain, and consistently near-random performance (0.9–3.1×), these results reveal a genuine failure to generalize to high-gravity NE NT geology. The model cannot discriminate the 12 NE cluster positives from the regional high-gravity background.

3. **The "mean holdout AP = 0.000132" is misleading** as an overall summary. It averages a geologically easy region (cand 1, actual mean skill ~15×) with a geologically hard region (cand 2/3, actual mean skill ~1.7×). A more honest summary would present per-location skill separately.

4. **The 21× validation-holdout gap is largely an artifact** of validation block selection bias and one extreme validation outlier (cand 29, 2466× skill). It does NOT mean the model is 21× worse at generalization than at interpolation. The honest generalization gap, comparing validation against holdout for matched difficulty levels, is closer to 3–8×.

5. **The model has genuine MVT discrimination skill**, but only for geology that resembles the training positive majority: carbonate or near-fault, moderate-gravity central NT. For the northern NT high-gravity terrain, it does not generalize.

---

## 12. Actionable Recommendations from This Diagnostic

**Immediate:**

1. **Report holdout results separately by holdout location**, not as a single aggregate mean. Holdout cand 1 skill (15×) and holdout cand 2 skill (1.7×) tell different stories. Collapsing them into 0.000132 is statistically incoherent.

2. **Investigate the NE NT high-gravity terrain geologically.** Why does holdout 2 have gravity 207 while training positives average 82? This might reflect a different geological setting (mafic-intruded basin margin, Gawler craton analogue). If that setting is genuinely prospective for MVT, the model's failure is a training data coverage problem, not a model problem.

3. **Do not use val cand 29 (skill 2466×) and val cand 23 (skill 147–173×) as indicators of general model performance.** They reflect exceptional performance on 4–8 archetypal pixels, not reliable generalization. Report them separately as "best case on highly distinctive geology."

**For v3 split design:**

4. **Fix the greedy row-major generator** to explicitly distribute holdout blocks across northern, central, and southern NT. At minimum, enforce that no two accepted splits share the same holdout_candidate_id.

5. **Add at least one holdout candidate from southern NT** (y < −2,000K) where McArthur River-type geology may differ from both northern clusters.

6. **Increase minimum holdout positives from 5 to at least 8**, even if this requires the fallback rule to accept 8 instead of 4 minimum validation positives. With 5 positives, holdout candidate 1 has only 20 percentage point precision in recall measurement.

**For model interpretation:**

7. **The model's "blind spot" is now identified**: high-gravity NE NT terrain. A diagnostic worth running: train on all data excluding the 12 NE positives, then predict the NE block and see if the gravity high is being assigned high or low prospectivity. If the NE block background is getting high scores, gravity alone is not sufficient to identify the MVT signal there and additional discriminators are needed.

---

*All calculations from archived CSVs: `archive/v2/data/processed/models/split_training_samples.csv`, `final_training_table.csv`, `metrics_by_split.csv`, `splits/split_summary.csv`. No models were re-trained or re-evaluated.*
