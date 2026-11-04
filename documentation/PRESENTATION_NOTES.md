# Presentation Briefing & Speaking Notes
## Mizoram Landslide Susceptibility Mapping Project
*Phase 2 Progress Update, Advanced Features & Benchmark Results*

---

### Slide 1: Project Overview & Core Objective
* **What to say:**
  > "Good morning / afternoon sir. Today I am presenting our major advancements on the **Mizoram Landslide Susceptibility Mapping Project at 30-Meter Resolution** using multi-source satellite remote sensing and machine learning."
* **Key talking points:**
  * **Study Area:** State of Mizoram ($\sim 21,081\text{ km}^2$, 22.9 million terrestrial 30m pixels), situated in the structurally active Indo-Burma Accretionary Wedge.
  * **Core Objective:** Produce a high-resolution, calibrated susceptibility zonation map to delineate natural hazard zones across the entire state.
  * **Scientific Scope:** Modeling permanent and climatological *susceptibility* (terrain predisposition), rather than short-term real-time temporal triggering.

---

### Slide 2: Multi-Source Data Collection & 30m Master Grid
* **What to say:**
  > "Sir, we have ingested multi-source Earth Observation and geological datasets and harmonized them into a strict 30-meter mathematical Master Grid."
* **Technical details to highlight:**
  * **Coordinate System:** WGS 84 / UTM Zone 46N (`EPSG:32646`) — metric units eliminate degree distortion.
  * **Grid Dimensions:** 3,959 columns $\times$ 9,437 rows ($\approx 37.36\text{M}$ total cells, $\approx 22.9\text{M}$ valid land pixels).
  * **Data Sources Harmonized:**
    1. **Copernicus DEM GLO-30 (AWS Open Data):** 8 tiles, 30m baseline elevation.
    2. **GEM Global Active Faults (GAF-DB):** 6 active regional fault zones with 50km buffer.
    3. **Macrostrat API:** Regional sedimentary lithological classifications.
    4. **ESA WorldCover 2021 (Planetary Computer):** 10m high-resolution land cover.
    5. **CHIRPS v2.0 (UCSB):** 132 monthly rasters (2007–2017) capturing 11-year precipitation patterns.
    6. **Expanded Landslide Inventory:** Multi-source integration (NASA COOLR + GSI BharAtlas).
  * **Resampling Rules:** Bilinear interpolation for continuous layers; Nearest-Neighbor for categorical classes (LULC, lithology); Euclidean Distance Transform for active faults.

---

### Slide 3: Advanced Feature Engineering (From 9 to 17 Features)
* **What to say:**
  > "Sir, a major breakthrough since our last update is the expansion from 9 baseline variables to 17 scientifically curated features to capture subtle hydrologic and structural instability signals."
* **The 17 Features Explained:**
  * **Primary Topography:** Elevation, Slope (Horn's method), Aspect, General Curvature.
  * **NEW Hydrological & Morphometric Features:**
    * **Topographic Wetness Index (TWI):** $\ln(a / \tan \beta)$ — identifies water accumulation and subsurface drainage convergence zones.
    * **Terrain Ruggedness Index (TRI):** Quantifies local elevational variance and scarp roughness.
    * **Topographic Position Index (TPI):** Differentiates ridge crests, upper slopes, benches, and valley bottoms.
  * **NEW Directional & Circular Curvatures:**
    * **Profile Curvature:** Controls downhill acceleration and flow velocity.
    * **Plan Curvature:** Governs lateral flow convergence versus divergence.
    * **Circular Aspect ($\sin$ & $\cos$):** Eliminates the artificial numerical discontinuity where $0^\circ = 360^\circ$.
  * **NEW Non-Linear Interaction:**
    * **Slope $\times$ Curvature Interaction:** Flags compound hazard zones where steep slopes intersect concavities.
  * **Environmental & Structural:** Distance to Active Faults, Lithology, ESA WorldCover, Mean Annual Precipitation (MAP), Max Monthly Precipitation.

---

### Slide 4: Expanded Dataset & 5-Fold Stratified Cross-Validation
* **What to say:**
  > "To train an enterprise-grade model, we expanded our ground truth dataset and evaluated models under strict 5-Fold Stratified Cross-Validation."
* **Dataset Scale:**
  * **Ground Truth:** Expanded to **91,944 total observations** (including **65,711 positive landslide pixels**).
  * **Negative Sampling:** 40,000 non-landslide pixels sampled across all slope classes (excluding a 50m buffer from known scars) to avoid flat-valley bias.
* **Why 5-Fold Stratified CV Matters:**
  * Eliminates the risk of a single lucky 70/30 train/test split.
  * Rotates through all data while preserving positive/negative class ratios.

---

### Slide 5: Model Comparison & New Accuracy Results
* **What to say:**
  > "Sir, our new models achieved a dramatic performance increase over the initial prototype:"
* **Model Comparison Table to Present:**
  | Model | ROC-AUC (Mean $\pm$ Std) | PR-AUC (Precision-Recall) | Macro F1-Score | Status |
  |---|:---:|:---:|:---:|---|
  | **XGBoost (Extreme Gradient Boosting)** | **0.8932 $\pm$ 0.0015** | **0.9327** | **0.7956** | **Top Performer (Winner)** |
  | **Random Forest Classifier** | **0.8743 $\pm$ 0.0034** | **0.9261** | **0.7749** | Very Strong Ensemble |
  | **Gradient Boosting (sklearn GBM)** | **0.8187 $\pm$ 0.0027** | **0.8880** | **0.7003** | Reliable Baseline Boosting |
  | **Logistic Regression (Linear)** | **0.6682 $\pm$ 0.0017** | **0.7928** | **0.6163** | Inadequate for Non-Linear Hazard |
* **Key Metric Highlights:**
  * **ROC-AUC rose to 0.8932 (almost 90%)**, compared to 0.7276 previously.
  * **PR-AUC of 0.9327** demonstrates outstanding reliability on positive landslide detection.
  * **Remarkably low variance ($\pm 0.0015$)** across all 5 folds proves the model generalizes exceptionally well.

---

### Slide 6: Feature Importance Rankings (What Drives Landslides in Mizoram?)
* **What to say:**
  > "Our XGBoost model's gain analysis reveals the true physical drivers of slope failures in Mizoram:"
* **Top Contributing Factors:**
  1. **Elevation (16.53%)**: Controls orographic rainfall exposure and regional relief energy.
  2. **Land Use / Land Cover (14.12%)**: Dense forest root strength vs jhum/degraded land.
  3. **Mean Annual Precipitation (13.86%)** & **Max Monthly Precipitation (12.39%)**: Combined rainfall explains $>26\%$ of landslide susceptibility.
  4. **Distance to Active Faults (10.10%)**: Tectonic shearing significantly destabilizes slopes.
  5. **Topographic Wetness Index (6.57%)** & **Ruggedness (5.92%)**: Local water accumulation hollows and scarp edges.
  6. **Aspect & Directional Factors (10.1%)**: Prevailing monsoon windward slope exposure.

---

### Slide 7: Final Deliverables & Visual Susceptibility Map v2
* **What to say:**
  > "Using our best XGBoost model, we performed full-state block-by-block inference over all 22.9 million pixels to generate the final 30m Susceptibility Map."
* **Outputs Generated:**
  * **`mizoram_landslide_susceptibility_v2.tif` (107.5 MB):** Full-state GeoTIFF with continuous probability $P \in [0.0, 1.0]$.
  * **Susceptibility Zonation:** Reclassified into 5 standardized operational hazard zones:
    * *Very Low ($P < 0.20$)* | *Low ($0.20 - 0.40$)* | *Moderate ($0.40 - 0.60$)* | *High ($0.60 - 0.80$)* | *Very High ($P > 0.80$)*.
  * **QGIS / ArcGIS Compatibility:** Ready for direct integration into state disaster management (MSDMA) and public works infrastructure planning.

---

# Phase 3 Update (added 2026-10-30)
*The slides above describe Phase 2 and are kept as they were written. Several of their numbers were later found to be inflated or wrong. **Use the slides below for any presentation from now on.** The full list of corrections is in README Section 13.*

---

### Slide 8: Why We Re-examined the Results
* **What to say:**
  > "Sir, our ROC-AUC was high but F1 was lower, so we audited the whole pipeline. We found that the high score was not measuring what we thought it was."
* **Key points:**
  * Same model, same data: ROC-AUC **0.893** with random splitting, **0.68** with 10 km spatial blocks.
  * A model given only pixel coordinates, with no terrain data, scored **0.896**. So the score measured filling in gaps between known landslides.
  * Cause: each landslide had been expanded to about 41 near-identical pixels, and neighbours landed in both train and test.

---

### Slide 9: What We Found and Fixed
| Problem | Evidence | Fix |
|---|---|---|
| DEM had no NoData; 0 m outside the state counted as land | 14.4 M cells; 38.9 % of negative candidates were outside Mizoram | Real land mask; terrain computed on a DEM padded with real outside terrain |
| TWI was a function of slope | Spearman −1.0 | Real flow routing: TWI, SPI, distance to stream, HAND |
| 90 m buffer on every landslide | Median slide 11 × 10 m; buffer about 212× larger | One 30 m pixel per landslide |
| 500 m de-duplication | Lost 20.4 % of real locations | Merge identical coordinates only |
| Lithology is one class | 100 % in Macrostrat; 99.6 % in GLiM | Dropped; GSI 1:50k recommended |
| East and west aspect swapped | Correlation −0.9999 with true eastness | Corrected |
| No roads in the model | 58.6 % of landslides are on road cells | OpenStreetMap roads added |

---

### Slide 10: New Results Under Honest Validation
* **What to say:**
  > "All results now use nested 10 km spatial cross-validation. Tuning and the decision threshold are chosen only from training data."

| Measure (10 km blocks) | Phase 2 | Phase 3, no roads | Phase 3, all factors |
|---|---|---|---|
| ROC-AUC | 0.681 | 0.762 | **0.945** |
| Macro-F1 | 0.612 | 0.696 | **0.878** |
| MCC | 0.245 | 0.399 | **0.755** |

* The F1 gap is closed: landslide F1 0.878, non-landslide F1 0.877.
* The leakage is gone: coordinates alone now score 0.557, and random and spatial CV agree (0.949 vs 0.945).
* *Note on stability (added 2026-11-01, DATA-028c):* Repeating 10-km spatial block assignment across 10 random seeds yields stable repeated means for "Phase 3, no roads": ROC-AUC 0.754 (SD 0.005), Macro-F1 0.690 (SD 0.005), MCC 0.387 (SD 0.006), compared to the single-split snapshot above (0.762 / 0.696 / 0.399).

---

### Slide 11: The Important Caveat
* **What to say:**
  > "Sir, I want to be careful about this 0.945. Distance to a road alone gives 0.914, because GSI mapped landslides mostly along roads."
* **Key points:**
  * All factors 0.945; roads alone 0.914; no roads 0.762.
  * Against negatives at the same road distance: 0.681.
  * We cannot separate real cut-slope failures from where the surveys happened. So we built two maps.

---

### Slide 12: Two Maps for Two Questions

| | All-factor map | Natural-terrain map |
|---|---|---|
| Question | Where along roads are failures most likely? | Which slopes are inherently unstable? |
| Inputs | 25 factors with roads | 21 natural factors |
| Held-out AUC | 0.943 | 0.734 |
| Very High zone | 4.6 % of land, 75.4 % of landslides | 8.4 % of land, 33.1 % of landslides |

* Plain road-distance baseline: AUC 0.919. The all-factor map captures 47.6 % of landslides in the top 1 % of land, against 24.2 % for the baseline.
* Natural-terrain model: **slope is the strongest control**, which agrees with slope-stability physics.
* Show `data/final/susceptibility_map_v3_preview.png` and `susceptibility_map_v3_natural_preview.png`.

---

### Slide 13: Limitations and Next Steps
* **Limitations:** road-corridor survey bias; no event dates; no usable lithology; coarse rainfall (5.5 km); surface model rather than bare earth; balanced-table F1 is not field precision; map values are relative scores, not probabilities.
* **Next steps:** GSI 1:50,000 geology (needs Bhukosh login); an inventory mapped independently of roads; dated rainfall if a dated inventory becomes available.
* **If asked "why did you change your numbers?":** see README Section 14.8 for prepared answers.

---

### Slide 14: Phase 4 — Rigorous Tuning & Portal Audits
* **What to say:**
  > "In Phase 4, we audited national portals for external geology and satellite inventories, and nested Optuna hyperparameter tuning was applied across the baseline models."
* **Key findings:**
  * **Portal Audits:** GSI's NGDR and NRSC's NDEM host valuable visual map services, but currently offer no public vector shapefile downloads for state subsets without institutional agreements.
  * **Tuned Baselines:** When Random Forest is tuned inside the spatial folds, its ROC-AUC rises from 0.942 to 0.944 and F1 to 0.882, matching XGBoost and LightGBM (0.945 / 0.878).
  * **Architectural Takeaway:** Ensemble tree-based architectures consistently dominate tabular hazard mapping over linear (LR: 0.892) and kernel (SVM: 0.905) models.

---

### Slide 15: Cartographic Consistency & Scientific Integrity
* **What to say:**
  > "We resolved all minor visual discrepancies in cartographic previews and verified 100% checklist compliance against the project specification."
* **Key points:**
  * **Out-of-Fold Preview Alignment:** Preview bar charts now plot out-of-fold land shares (59.4%) directly alongside out-of-fold landslide capture (3.7%), matching the published zone tables.
  * **Unbounded Ratios:** Frequency-ratio plots display clean, readable labels (`> 2000` instead of scientific notation).
  * **Complete Audit:** All 38 required sections from Section 17 of the project specification are mapped, audited, and verified in `documentation/REPORT_COVERAGE_CHECKLIST.md`.

---

### Correction to Slides 10, 13, 14 and 15 (added 2026-11-01, DATA-035)
**Do not present Slides 14 and 15 as written. Use Slides 16 to 18 instead.**
* **Slide 10 note:** the no-road MCC SD is 0.009, not 0.006.
* **Slide 13:** geology and an inventory away from roads have now been tested. See Slides 16 and 17.
* **Slide 14:** NGDR does offer downloads, so "no public vector shapefile downloads" is wrong for GSI. It still holds for the public NDEM site. The tuning numbers are replaced by Slide 18, and "tree ensembles dominate" should not be claimed.
* **Slide 15:** do not say "100 % compliance". Three items were missing and are now written.

---

### Slide 16: Does Geology Help?
* **What to say:**
  > "I obtained GSI's 1:50,000 geology and set a rule before testing it: keep it only if the natural model gains at least 0.010. It did not."
* **Key points:**
  * 357 polygons cover 99.3 % of the land, grouped into 7 rock groups from the map descriptions alone.
  * Rock type does show a pattern: shale-dominant frequency ratio 1.33, coal-bearing 0.57.
  * The natural model went from 0.702 to 0.701, so geology was not adopted and the v3 maps stay.
* **If asked why:** slope, rain and soil already carry the signal.

---

### Slide 17: The Real Test: Landslides the Models Never Saw
* **What to say:**
  > "This is the most important result in the project. I tested both maps on GSI landslides that were not used in training, most of them away from roads."
* **Show this table:**

| Ranking | Held-out GSI data | Unseen mapped polygons | Unseen 2024 records |
|---|---|---|---|
| Natural-terrain map | 0.734 | **0.692** | 0.790 |
| All-factor map | 0.943 | **0.554** | 0.917 |
| Road distance alone | 0.919 | **0.429** | 0.930 |

* **Key points:**
  * Only 10.9 % of the test polygons are within 60 m of a road, against 76 % of the training data.
  * The all-factor map's Very Low zone holds 55.4 % of these landslides. The natural map's holds 1.4 %.
* **Honest limit:** these are unseen GSI records, not an outside survey, and their mapping method is not stated.

---

### Slide 18: Conclusion
* **What to say:**
  > "The original question was why ROC-AUC was high but F1 was low. Answering it honestly showed something bigger: high scores can come from where landslides were recorded, not from where they happen."
* **Key points:**
  * Phase 2's 0.893 was spatial leakage; the honest figure was 0.68.
  * Phase 3's 0.945 is mostly road proximity; road distance alone gives 0.912.
  * The natural-terrain map is the one that carries over to unseen landslides.
  * Tuning LR, SVM and RF made no meaningful difference: RF 0.944, SVM 0.910, LR 0.892, against 0.912 for road distance alone.
* **Recommended use:** the natural-terrain map for the state, and the all-factor map only within road corridors. The final choice is the author's.

**Correction to Slide 18 (added 2026-11-01).** The ROC-AUC and F1 issue was not the project's question. The research question, confirmed by the author, is: what is the landslide susceptibility of Mizoram? Open the slide with this instead:
  > "The project set out to find the landslide susceptibility of Mizoram. Testing the results honestly showed that high scores can come from where landslides were recorded, not from where they happen."

---

### Slide 19: Teaching the Model Wilderness Failures (Phase 5)
* **What to say:**
  > "In Phase 4 we discovered that natural terrain failures away from roads behave differently from roadside cut-slope failures. In Phase 5, we trained our natural model on 1,434 unseen GSI mapped polygons under a pre-registered decision rule."
* **Key points:**
  * **Pre-Registered Decision Rule (P1.3):** Adopt the v5 model only if Test P (mapped polygons) gains at least +0.020 and Test R (roadside landslides) drops by no more than -0.010.
  * **10-Seed Spatial CV Result:**
    * Test P gained **+0.2509** ROC-AUC (0.6721 to 0.9231, threshold $\ge +0.020$).
    * Test R changed by only **-0.0032** ROC-AUC (0.6999 to 0.6967, tolerance $\ge -0.010$).
  * **Decision:** Model v5 was decisively **ADOPTED**.
  * **Nested Spatial CV:** Reached state-wide ROC-AUC of **0.7993** (SD 0.0289) and Macro-F1 of **0.7199**.

---

### Slide 20: The Final Hazard Map for Mizoram (v5 Natural)
* **What to say:**
  > "Our final deliverable is the v5 Natural Susceptibility Map at 30-meter resolution. It covers all 22.9 million land cells of Mizoram and achieves an outstanding hazard stratification."
* **Key points:**
  * **Hazard Zonation (5 Natural Break Classes):**
    * **Very High Hazard:** Covers 7.55% of state land area; captures **66.84%** of training landslides (Frequency Ratio = **8.85**) and **47.19%** of spatial out-of-fold landslides (FR = **6.13**).
    * **Very Low Hazard:** Covers 29.13% of land area; holds only **0.15%** of training landslides (FR = **0.005**).
  * **Physical Drivers:** Permutation importance confirms slope as the decisive trigger (+0.1295), followed by Mean Annual Precipitation (+0.0391) and North-South aspect exposure (+0.0274).
  * **Independent Validation:** On unseen 2024+ events, achieves ROC-AUC **0.7582** (Top 20% land captures 60.45%), providing an authoritative, unbiased hazard baseline.
  * **Author Recommendation:** The natural-terrain map v5 is the recommended master result for state-wide disaster planning and slope management.

---

## Comprehensive Viva & Defense Master Cheatsheet (added 2026-11-01)

This cheatsheet equips the student with rigorous, structured answers for oral project examinations. Every answer is formatted with the four essential academic pillars: **Where it comes from**, **Why**, **How**, and **What it means**.

---

### Viva Q1: "What is your exact research question, and what is your primary answer?"

- **Where it comes from:** Confirmed by the author on 2026-11-01 (`README.md` §16.1; `FINAL_REPORT.md` §2; `prof_document.txt:L893`).
- **Why:** To cut through secondary diagnostic questions (leakage, road bias, geology) and answer the fundamental scientific mandate.
- **How:** By modeling the intrinsic continuous spatial probability of slope failure $P(Y=1 \mid \mathbf{X})$ across all 22,918,792 terrestrial 30.3 m cells of Mizoram using an XGBoost gradient boosted classifier regularized via Optuna Bayesian search, evaluated on 10 km spatial blocks, and classified into 5 Jenks natural break zones.
- **What it means:** The landslide susceptibility of Mizoram is decisively governed by terrain slope (permutation importance +0.1295) and monsoonal precipitation (+0.0391). The final deliverable **Natural-Terrain Map v5** concentrates **87.82%** of historical slope failures into its top two hazard zones (covering only 21.06% of the state), with a Frequency Ratio of **8.85** in the Very High hazard zone.

---

### Viva Q2: "In Phase 2 you had a high ROC-AUC of 0.8932. Why did you discard it as invalid?"

- **Where it comes from:** Forensic audit in Phase 3 (`scripts/phase3/00_audit_phase2_pipeline.py`, `01_diagnose_roc_vs_f1.py`; `FINAL_REPORT.md` §5).
- **Why:** A model that scores high due to spatial data leakage will fail catastrophically when deployed to predict hazards in unmapped mountain valleys.
- **How:** 
  1. *Spatial Proximity Proof:* Phase 2 buffered point records into 90 m disks. Under random 5-fold CV, adjacent 30 m pixels from the *same* landslide scar were assigned to both training and test sets. 100% of test landslide pixels were within 100 m of a training pixel (median distance: 30 m).
  2. *Negative Control Experiment:* A model trained on **only spatial coordinates ($X, Y$)** scored **0.8956 ROC-AUC** without seeing a single topographic, geologic, or climatic feature.
- **What it means:** The 0.8932 score was an artifact of coordinate memorization and spatial interpolation. Under honest 10 km spatial block validation, the Phase 2 model collapsed to ROC-AUC 0.68.

---

### Viva Q3: "Why did you build two separate models: All-Factor and Natural-Terrain?"

- **Where it comes from:** Phase 3 discovery (`scripts/phase3/09_eda_v3.py`, `10_train_evaluate_v3.py`; `FINAL_REPORT.md` §6, §24, §30).
- **Why:** Over 76% of GSI historical landslide points are located within 60 m of a road, reflecting vehicle survey accessibility. If roads are included as features, the model learns human survey routes rather than terrain physics.
- **How:**
  1. *All-Factor Model (25 features):* Includes distance to roads, road density, and LULC. Scores ROC-AUC 0.945 in spatial CV, but distance to road alone scores 0.912–0.920. When tested against road-matched negatives, its score collapses to 0.681.
  2. *Natural-Terrain Model (21 features):* Stripped of all infrastructure and post-failure land cover. Governed strictly by geomorphology, hydrology, lithology, climate, and soils. Scores 0.741 in Phase 3 and 0.799 in Phase 5.
- **What it means:** The All-Factor model is an infrastructure cut-slope model (restricted to highway maintenance corridors). The Natural-Terrain model is the only valid state-wide hazard map for regional planning and wilderness management.

---

### Viva Q4: "How did you prevent negative sampling bias?"

- **Where it comes from:** Negative sampling protocol (`scripts/phase3/08_build_dataset_v3.py`, `scripts/phase5/01_build_dataset_v5.py`; `FINAL_REPORT.md` §20).
- **Why:** Conventional studies sample non-landslides only in flat valleys, teaching models to distinguish valleys from mountains rather than stable slopes from unstable slopes. Sampling too close to landslides risks labeling unfailed active slide bodies as stable.
- **How:**
  1. Enforced a **150 m morphological binary dilation buffer** (5 pixels) around all known landslides, completely excluding these zones from negative sampling.
  2. Sampled **uniform random negatives across the full slope distribution** of valid terrestrial land outside the exclusion zone.
  3. Created a parallel set of **road-matched negatives** having the exact road-distance probability distribution of positive points to control for infrastructure bias.
- **What it means:** The model is forced to learn the subtle geotechnical thresholds (concavity, hydrological saturation, pore-water pressure, friction angles) that distinguish failing mountain slopes from stable mountain slopes.

---

### Viva Q5: "You integrated GSI 1:50,000 geology in Phase 4. Why did you reject it?"

- **Where it comes from:** Pre-registered Decision Rule A6 (`scripts/phase4/10_train_evaluate_v4.py`; `data/phase4/modeling/results/a6_decision.json`; `FINAL_REPORT.md` §12, §30).
- **Why:** To eliminate confirmation bias, we established an unyielding rule *before* modeling: adopt geology only if held-out spatial CV gains at least $+0.010$ ROC-AUC.
- **How:** Extracted 357 GSI 1:50,000 lithology polygons and classified them into 7 regional rock groups based strictly on map sheet descriptions. Evaluated under identical 10 km spatial block CV.
- **What it means:** The natural model with geology scored **0.7014** vs **0.7020** baseline (delta: **$-0.0006$**). Geology failed the $+0.010$ threshold and was rejected. In folded sedimentary flysch, macro-lithology provides no incremental predictive power once high-resolution slope, terrain curvature, hydrological catchment, and precipitation are known.

---

### Viva Q6: "Why did you adopt the Phase 5 polygon augmentation?"

- **Where it comes from:** Pre-registered Decision Rule P1.3 (`scripts/phase5/02_compare_v5.py`; `data/phase5/modeling/results/p1_decision.json`; `FINAL_REPORT.md` §2, §6, §19).
- **Why:** To teach the natural-terrain model how slope failures behave in wilderness areas away from roads, using 1,434 GSI mapped polygons.
- **How:** Evaluated across 10 random seeds using 5-fold spatial block CV on `block10`:
  - **Test P (mapped polygons):** GSI-only mean 0.6721 $\to$ v5 augmented mean 0.9231 (Gain: **+0.2509**, required $\ge +0.020$).
  - **Test R (roadside landslides):** GSI-only mean 0.6999 $\to$ v5 augmented mean 0.6967 (Change: **-0.0032**, tolerance $\ge -0.010$).
- **What it means:** The rule was decisively satisfied (+0.2509 gain on polygons with virtually zero penalty on roadside points). The v5 natural model was formally **ADOPTED**, lifting state-wide nested spatial CV from 0.741 to **0.7993** (SD 0.0289).

---

### Viva Q7: "What does a Frequency Ratio (FR) of 8.85 mean in your Very High zone?"

- **Where it comes from:** State-wide zonation evaluation (`scripts/phase5/05_evaluate_map_v5.py`; `data/phase5/maps/zone_statistics_v5_natural.csv`; `FINAL_REPORT.md` §33).
- **Why:** Frequency Ratio provides an objective, dimensionless measure of hazard concentration that normalizes for zone area.
- **How:**
  $$\text{FR}_k = \frac{\% \text{ of Landslides in Zone } k}{\% \text{ of Land Area in Zone } k} = \frac{66.84\%}{7.55\%} = \mathbf{8.85}$$
- **What it means:** A land cell in the Very High hazard zone is **8.85 times more likely** to experience a landslide than an average cell in Mizoram. Conversely, the Very Low zone has $\text{FR} = 0.005$ ($0.15\% / 29.13\%$), meaning it is virtually free of slope failures. This steep, monotonic FR gradient proves exceptional statistical and operational calibration.

---

### Viva Q8: "What are your model's primary limitations and recommendations for authorities?"

- **Where it comes from:** `FINAL_REPORT.md` (§34, §35) and `README.md` (§16.7).
- **Why:** Responsible engineering requires stating exact operational boundaries.
- **How:** Documented four core limitations:
  1. *Historical survey bias:* Road-correlated points distort infrastructure models; use the **Natural-Terrain Map v5** for state-wide planning.
  2. *Static climatology:* The model assesses permanent topographic susceptibility, not real-time hourly rainstorm warnings.
  3. *Soil resolution:* SoilGrids 250 m provides broad pedological trends, not localized colluvial pocket depths.
  4. *Surface DSM:* Copernicus GLO-30 reflects forest canopy height; bare-earth LiDAR would refine steep slope scarps.
- **What it means:** MSDMA and PWD should use the 5-class v5 Natural Map to prioritize slope stabilization along High and Very High zones (21.06% of the state) and guide zoning for rural hill settlements.

---
*End of Comprehensive Viva & Defense Master Cheatsheet.*

---

## Correction to Slides 19 and 20 and the viva cheatsheet (added 2026-11-01, DATA-044, DATA-045)

**Do not present Slides 19 and 20, and do not use Viva Q1, Q3, Q6, Q7 or Q8 above.** They present v5 as the final map, use training-sample figures as results, and call scores probabilities. Viva Q2, Q4 and Q5 are sound, except that "hydrological saturation" and "friction angles" in Q4 were not measured. Use the slides and answers below, and README 14.8, 16.11 and 18.5.

---

### Slide 19 (replacement): Did Adding Polygons Help?
* **What to say:**
  > "I retrained the natural model with 1,434 mapped polygons. The score jumped from 0.67 to 0.92. A jump that large needed checking, and it did not hold up."
* **Key points:**
  * 90.8 % of the polygons sit in 3 map sheets, and coordinates alone score 0.892.
  * Only 1.9 % face north, against 22.5 % of the land. The other inventories show no such pattern.
  * Unused polygons outside the training sheets: v5 0.704, v3 0.692.
  * Records from 2024 onward: v5 0.758, v3 0.788.
* **Conclusion:** no clear gain, so v5 stays an experiment.
* **Lesson:** a rule fixed in advance still needs a control. This one lacked a location control.

---

### Slide 20 (replacement): Final Map
* **What to say:**
  > "The recommended result is natural-terrain map v3. It uses 21 factors with no road or land-cover data, and it is the map that held up on landslides it had not seen."
* **Key points:**
  * Held-out GSI landslides 0.734, unseen mapped polygons 0.692, records from 2024 onward 0.788.
  * On unseen polygons, its Very Low zone holds 1.4 % of landslides on 19.5 % of the land.
  * For comparison, the all-factor map scores 0.943, 0.554 and 0.916. Road distance alone scores 0.919, 0.429 and 0.930.
  * Values are relative scores for screening, not probabilities of failure.
* **Note:** the final choice of map is the author's.

---

### Viva Q1 (corrected): What is your research question, and your answer?
- **Where it comes from:** confirmed by the author (README 16.1), and matches `prof_document.txt`.
- **Why:** the specification asks for a susceptibility model and map of Mizoram.
- **How:** XGBoost with 21 natural factors, validated on 10 km spatial blocks and tested on unseen landslides.
- **What it means:** the answer is the natural-terrain map v3. It ranks steeper, wetter ground higher, and scores are relative, not probabilities.

### Viva Q3 (corrected): Why two models?
- **Where it comes from:** DATA-028, DATA-028b, DATA-040.
- **Why:** 76 % of GSI landslides lie within 60 m of a road, and road distance alone scores 0.912.
- **How:** the all-factor model has 25 factors. The natural model has 21, with no roads or land cover.
- **What it means:** on unseen polygons away from roads, the all-factor map scores 0.554 and the natural map 0.692. Within 60 m of a road, the all-factor map is stronger: 0.777 against 0.734, on 157 pixels.

### Viva Q7 (corrected): What does frequency ratio mean?
- **Where it comes from:** `data/phase3/maps/zone_statistics_natural.csv`, `data/phase4/verification/independent_validation_zones.csv`.
- **Why:** it compares a zone's share of landslides with its share of land.
- **How:** FR = % of landslides in the zone ÷ % of land in the zone.
- **What it means:** for the natural map on held-out GSI landslides, Very High has FR 3.93. On unseen polygons it has 2.03. Above 1 means more landslides than the zone's area would predict. It does not mean a cell is certain to fail, and values measured on training data run higher.

### Viva Q8 (corrected): What are the limitations and the right use?
- **Where it comes from:** `FINAL_REPORT_VERIFIED.md` Item 34.
- **Why:** the inventories limit what any model can learn.
- **How:** the main limits are road-biased GSI points, polygons concentrated in 3 sheets with a direction pattern, unsurveyed ground, coarse rainfall and soil, and a surface DEM.
- **What it means:** use the map to screen and compare areas, not to replace a site investigation.



