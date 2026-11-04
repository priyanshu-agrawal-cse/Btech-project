# Landslide Susceptibility of Mizoram: Final Report

**Status:** verified on 2026-11-01. The main tables and key figures were tested against their source files by `scripts/phase5/verify/c6_check_verified_report.py` (65 of 65 pass). Descriptive text was reviewed by reading. This report replaces `documentation/FINAL_REPORT.md`, which is kept for the record but contains errors (DATA-044).

**Study area:** Mizoram, India. **Grid:** 30.3068 m, EPSG:32646, 9,437 rows × 3,959 columns, 22,918,792 land cells.

---

## Summary

### Research question
**What is the landslide susceptibility of Mizoram?** The project author confirmed this wording on 2026-11-01. It matches `data/raw/prof_document.txt`, which asks for a landslide susceptibility model and map for Mizoram.

### What was done
The work ran in five phases:
1. **Phase 1** built a first model from 41 NASA COOLR landslide pixels.
2. **Phase 2** added GSI landslide records and reported ROC-AUC 0.893. An audit later showed this score was caused by spatial leakage. Under 10 km spatial blocks the same model scored 0.68.
3. **Phase 3** rebuilt the pipeline with one pixel per landslide, 10 km block validation, real flow routing, roads, rivers and soil. It produced an all-factor map and a natural-terrain map with no road or land-cover factors.
4. **Phase 4** tested GSI 1:50,000 geology, which was rejected, and tested the maps on unseen GSI landslides.
5. **Phase 5** retrained the natural model with mapped polygons. Checks found that this result was inflated, so the v5 map is not recommended.

### Main results
ROC-AUC or map AUC. Higher is better, and 0.5 means no skill.

| Ranking | Held-out GSI landslides | Unseen mapped polygons (1,434 pixels) | Unused polygons outside the training sheets (1,045 pixels) | Unseen records from 2024 onward (708 pixels) |
|---|---|---|---|---|
| **Natural-terrain map v3** | 0.734 | **0.692** | 0.692 | 0.788 |
| Natural-terrain map v5 | Not comparable | Used in training | 0.704 | 0.758 |
| All-factor map v3 | 0.943 | 0.554 | 0.646 | 0.916 |
| Distance to a road alone | 0.919 | 0.429 | 0.649 | 0.930 |

Sources: `data/phase3/maps/rate_curve_summary.csv`, `data/phase4/verification/independent_validation.csv`, `data/phase5/verification/v5_unseen_test.csv`, `data/phase5/maps/independent_validation_2024_v5.csv`.

### What the results mean
1. **The all-factor score is mostly road proximity.** 76 % of GSI landslides lie within 60 m of a road, against 6 % of the land. Distance to a road alone scores 0.912 in spatial cross-validation, and the all-factor model falls to 0.554 on landslides away from roads.
2. **The natural-terrain map v3 carries over best across these tests,** and it is the recommended main result. Slope is its strongest factor. The final choice belongs to the author.
3. **Geology added nothing** to the model: 0.7014 against 0.702, where +0.010 was required.
4. **The v5 map should not replace v3.** It passed its decision rule, but that rule did not control for location, and the mapped polygons have a strong direction bias (Item 32).

No map here gives a probability of failure. The values are relative scores.

---

## Report items

The 38 items follow section 17 of the project specification. Each gives where the content comes from, why it matters, how it was done and what it means.

### 1. Project objective
**Where it comes from:** `data/raw/prof_document.txt`; main log, STEP 0.
**Why:** a state-wide map shows where landslides are more likely, which ground-based records alone cannot do.
**How:** the project built, validated and documented a reproducible 30 m model, then tested it on data it had not seen.
**What it means:** the deliverable is a relative susceptibility map with an honest statement of how far it can be trusted.

### 2. Research question
**Where it comes from:** confirmed by the author on 2026-11-01 (README 16.1).
**Why:** a single question keeps the report focused. Leakage, road bias and geology came up during the work, and they are reported as validation results.
**How:** the question is answered by ranking every land cell with a model validated on 10 km spatial blocks.
**What it means:** the answer is a map of relative susceptibility, not a forecast of when a landslide will happen.

### 3. Study area
**Where it comes from:** boundary from OpenStreetMap Nominatim (DATA-001), `data/raw/mizoram_boundary.geojson`. Statistics from the rasters (`data/phase5/verification/c3_fact_check.txt`).
**Why:** Mizoram is steep, wet and has many recorded landslides.
**How:** measured over the land mask:

| Property | Value |
|---|---|
| Land on the grid | 21,051 km2 (the commonly quoted state area is about 21,081 km2) |
| Extent | 21.94° to 24.52° N, 92.27° to 93.44° E |
| Elevation | 18.0 to 2,155.5 m, mean 611.4 m |
| Slope | 0 to 70.8°, mean 22.8° |
| Mean annual rainfall | 1,820.8 to 3,373.0 mm, mean 2,610.6 mm |
| Maximum monthly rainfall | 407.7 to 1,475.4 mm, mean 874.1 mm |

**What it means:** the land is steep nearly everywhere, so slope alone cannot explain every landslide. Rainfall comes from 5.5 km cells, so it varies only smoothly.

### 4. Initial workflow
**Where it comes from:** main log, STEP 0 A; DATA-006 and DATA-010.
**Why:** it was the first plan for moving from data to a map.
**How:** 14 steps from study area to map. The first model used 41 COOLR landslide pixels and randomly undersampled non-landslide pixels. Random Forest scored ROC-AUC 0.7276 and Logistic Regression 0.7051.
**What it means:** 41 pixels are too few, and most COOLR locations are only known to the nearest town.

### 5. Workflow review
**Where it comes from:** main log, STEP 0 B and C; DATA-017 and DATA-018.
**Why:** the Phase 2 score of 0.893 sat beside weak class balance, so the method was audited.
**How:** the audit measured how close test pixels were to training pixels, and added a coordinates-only control:
* Each landslide point had become a disk of about 41 pixels.
* Under random cross-validation, all test landslide pixels were within 100 m of a training pixel (median 30 m).
* A model given only coordinates scored 0.8956.
* Under 10 km blocks the Phase 2 model scored ROC-AUC 0.68 and macro-F1 0.61.
* The master DEM stored out-of-state cells as 0 m, which created false cliffs at the border.

**What it means:** the 0.893 measured gap-filling between neighbouring pixels, not prediction in new areas.

### 6. Final workflow
**Where it comes from:** main log, STEP 0 D and E; README 14; DATA-018 and DATA-024 to DATA-030.
**Why:** to remove the faults found in the review.
**How:** one pixel per landslide; a real land mask; negatives kept away from landslides; 10 km block cross-validation; tuning and thresholds inside training folds; a road-only baseline and coordinates-only control beside every main score; decision rules fixed before testing; and final tests on unseen landslides.
**What it means:** a high score alone is not accepted as evidence. Each must beat a simple baseline.

### 7. All data sources
**Where it comes from:** `documentation/SOURCES.md`, `documentation/DATA_INVENTORY.csv`.
**Why:** the factors describe terrain, water, soil, rain, geology and land cover.
**How:**

| Data | Source | Used for |
|---|---|---|
| Copernicus DEM GLO-30 | ESA, AWS Open Data | Terrain and hydrology |
| GSI landslide inventory | GSI, BharAtlas mirror | Training landslides |
| NASA COOLR | NASA GSFC | First model; 2 exact points kept |
| GSI data from NGDR | GSI, geodataindia.gov.in | Geology test; landslides for testing |
| OpenStreetMap | Geofabrik extract | Roads and rivers |
| SoilGrids 2.0 | ISRIC | Clay, sand, bulk density |
| CHIRPS v2.0, 2007 to 2017 | Climate Hazards Center | Rainfall |
| GEM Global Active Faults | GEM Foundation | Distance to faults |
| ESA WorldCover 2021 | ESA, Planetary Computer | Land cover |
| Sentinel-2 L2A | Copernicus, Planetary Computer | NDVI sensitivity test only |

**What it means:** most layers are open data. The NGDR layers need a registered login.

### 8. Data acquisition process
**Where it comes from:** DATA-001, 003, 004, 006 to 009, 012, 021 to 023, 026 and 037.
**Why:** another researcher must be able to obtain the same data.
**How:** most data came from scripts in `scripts/download/` and `scripts/phase3/`. NGDR data came through the site's own panel: choose a service, up to two layers and the state, add to the cart, and receive a link by email (README 16.9).
**What it means:** nearly everything can be repeated by script. The NGDR files need a person to sign in.

### 9. Every dataset collected
**Where it comes from:** `documentation/DATA_INVENTORY.csv`.
**Why:** each file needs a recorded source, format and status.
**How:** one row per dataset or major output, in 14 columns. SHA-256 values for the NGDR zips are in `data/phase4/logs/ngdr_download_manifest.csv`.
**What it means:** failed and unused datasets are listed as well as successful ones.

### 10. Dataset metadata
**Where it comes from:** `documentation/SOURCES.md`, `documentation/DATA_INVENTORY.csv`.
**Why:** resolution and date limit what a layer can show.
**How:** source, URL, provider, resolution, CRS, format and licence are recorded where known. No licence was shown during the NGDR download, so GSI is credited and the licence is recorded as not stated.
**What it means:** the coarsest layers are rainfall (5.5 km) and soil (250 m).

### 11. Download problems
**Where it comes from:** DATA-003, 004, 007, 012, 023, 032, 035 and 037.
**Why:** so others do not repeat dead ends.
**How:**
* Bhuvan downloads timed out (DATA-003, DATA-004).
* EONET gave 0 North-East India events, and the NASA GLC and NESDR sources added nothing (DATA-012).
* `GLiM.zip` from Phase 1 was not a valid file (DATA-023).
* `bhukosh.gsi.gov.in` could not be reached on 2026-11-01.
* NGDR was first wrongly recorded as view-only. Its download panel works, within a limit of two layers per state search, and links arrive by email (DATA-035, DATA-037).
* NDEM's public site shows Mizoram landslide layers, but its Downloads menu holds only apps and documents, as far as tested.

**What it means:** NRSC landslide data was not obtained.

### 12. Failed attempts
**Where it comes from:** failure fields in the main log.
**Why:** failed attempts limit what the results can claim.
**How:**
* Macrostrat and GLiM geology were effectively one class over Mizoram (DATA-017, DATA-023).
* WhiteboxTools could not read predictor-3 GeoTIFFs, so an uncompressed copy was used (DATA-020).
* Least-cost breaching ran about 15 minutes without finishing, so depression filling was used (DATA-020).
* Geology failed its decision rule (DATA-039).
* The Phase 5 decision rule proved too weak (DATA-045).

**What it means:** these results are reported, not hidden.

### 13. Successful attempts
**Where it comes from:** result fields in the main log.
**Why:** they show which steps can be relied on.
**How:** key steps were the corrected terrain and hydrology layers (DATA-019, DATA-020), the rebuilt inventory (DATA-024), honest validation (DATA-028, DATA-028c), both v3 maps (DATA-029, DATA-030) and the independent test (DATA-040). The reproduction test matched all 50 result rows when re-run (DATA-035).
**What it means:** the main results can be reproduced from the stored scripts.

### 14. Preprocessing
**Where it comes from:** DATA-005, 013, 014, 019 to 022 and 024; `scripts/phase3/`.
**Why:** all layers must align cell by cell, and border artefacts must be removed.
**How:**
* The land mask is DEM above 0.
* Terrain and hydrology were computed on a DEM with a 10 km margin, so border cells have real neighbours.
* Rainfall was resampled bilinearly and land cover by nearest neighbour.
* Float rasters use NoData −9999 on the master grid.

**What it means:** corrected maximum slope is 70.8°. The 88.18° in Phase 2 was a border artefact.

### 15. CRS decisions
**Where it comes from:** DATA-002; README 4.1.
**Why:** slope and distance need metres.
**How:** WGS 84 / UTM Zone 46N (EPSG:32646). Its central meridian, 93° E, runs through Mizoram.
**What it means:** distances and areas are consistent across the state.

### 16. QGIS operations
**Where it comes from:** README 16.3; `gis/styles/susceptibility_zones_v3.qml`; DATA-046.
**Why:** the specification asks for this to be recorded.
**How:** **no analysis was done in QGIS.** All processing used Python. QGIS was used only to confirm that the style file loads and displays the zone maps (DATA-046).
**What it means:** every result can be repeated from scripts. The style file has five classes in an orange-to-brown ramp, from `#fbe3d0` (Very Low) to `#6f2108` (Very High).

### 17. Python scripts
**Where it comes from:** `scripts/`; README 9, 14.7, 16.9 and 18.
**Why:** scripts are the exact record of the method.
**How:** `scripts/download/`, `preprocessing/` and `modeling/` are Phases 1 and 2. `scripts/phase3/`, `phase4/` and `phase5/` are the later phases, and their `verify/` folders hold the checks.
**What it means:** the README gives the order for running each phase.

### 18. Feature engineering
**Where it comes from:** `scripts/phase3/02_terrain_features_v3.py`, `03_hydrology_features_v3.py`, `04_osm_roads_rivers.py`, `05_soilgrids_features.py`; DATA-019 to DATA-022.
**Why:** failure depends on steepness, water, material and position on the slope.
**How:**

| Factor | Method |
|---|---|
| Slope, aspect | Horn's method; aspect split into sine and cosine |
| Curvature | Zevenbergen and Thorne |
| TPI | z − mean(z) in 9×9, 33×33 and 99×99 windows |
| Relief | max(z) − min(z) in a 33×33 window |
| TWI | ln(SCA / tan β), D-infinity SCA, tan β ≥ 0.001 |
| SPI | ln(1 + SCA · tan β) |
| HAND, stream distance | D8 streams of at least 1 km2 |
| Road and river distance | OpenStreetMap lines, in metres |

Of 27 candidates, `curv_general` and `tri` were removed without using labels, which left 25 factors. The natural model uses 21: no roads, no land cover.
**What it means:** TWI now reflects upslope area. In Phase 2 it was only a function of slope.

### 19. Landslide sampling
**Where it comes from:** DATA-024, DATA-025; `data/phase3/inventory/inventory_v3_summary.json`.
**Why:** one landslide should count once, or neighbouring pixels inflate the score.
**How:** 2,041 GSI records inside the boundary held 165 identical duplicates, leaving 1,876 locations. Adding the 2 exact COOLR points gives 1,878 locations, which fall in 1,859 pixels.
**What it means:** 1,859 landslide pixels is smaller than the 61,726 used in Phase 2, but they are real, separate samples.

### 20. Non-landslide sampling
**Where it comes from:** DATA-025; `scripts/phase3/08_build_dataset_v3.py`.
**Why:** an inventory never proves a place is stable, so negatives need care.
**How:** cells near landslides were excluded by a 5-pixel dilation, about 107 to 152 m depending on direction. The closest negative is 135.5 m from a landslide. Three sets were drawn with seed 42: 1,859 random, 7,436 extra random for a ratio test, and 1,859 road-matched.
**What it means:** road-matched negatives show how much skill remains once road distance is equal.

### 21. Raster extraction
**Where it comes from:** DATA-025, DATA-038; `scripts/phase3/08_build_dataset_v3.py`.
**Why:** models need a table of factor values at each sample.
**How:** each sample's row and column come from the grid transform, and the value is read from each raster at that cell.
**What it means:** 57 rows have no soil value. XGBoost handles these directly; LR and SVM fill them with a median computed inside each training fold.

### 22. Final dataset schema
**Where it comes from:** README 16.2.
**Why:** another researcher needs to know each column.
**How:** `FINAL_DATASET_v3.csv` has 13,013 rows and 42 columns: 15 identity, location and block columns plus 27 factors. The v4 table adds 3 geology columns. The v5 table adds 2,868 rows of 21 natural factors.
**What it means:** the main models use the v3 table.

### 23. Data quality checks
**Where it comes from:** DATA-017, DATA-026, DATA-027.
**Why:** silent errors produce believable but wrong results.
**How:** regenerated rasters were compared with the stored table. 25 of 27 layers were identical; `dist_stream` differed in 4 rows (at most 12.55 m) and `hand` in 1 row (0.32 m). The cause was not traced.
**What it means:** the differences are small and were accepted with a stated tolerance.

### 24. Exploratory analysis
**Where it comes from:** DATA-027, DATA-038; `data/phase3/eda/`.
**Why:** to understand the data before modelling.
**How:**

| Measure | Result |
|---|---|
| Single-factor AUC, road distance | 0.92 (shown as 0.080, because nearer is higher risk) |
| Single-factor AUC, road density | 0.872 |
| Single-factor AUC, elevation / slope | 0.662 / 0.644 |
| Frequency ratio, slope | below 10°: 0.44; above 40°: 1.93 |
| Frequency ratio, road distance | 0 to 30 m: 24.2 |
| Frequency ratio, rock type | shale-dominant 1.33; coal-bearing 0.57 |

**What it means:** roads separate the classes far more than any natural factor. Road cuts may cause failures, and GSI also surveyed along roads. These data cannot separate the two.

### 25. Train/test strategy
**Where it comes from:** DATA-018, DATA-028, DATA-028c.
**Why:** random splits test only gap-filling.
**How:** 5 folds of 10 km blocks, with `StratifiedGroupKFold`. Median distance from a test landslide to the nearest training landslide is 3,738 m. Tuning used nested 3-fold block CV, and results were repeated over 10 block assignments.
**What it means:** the scores are stable (SD 0.001 to 0.005), so they do not depend on one split.

### 26. Leakage prevention
**Where it comes from:** DATA-017, DATA-018, DATA-028; README 13 and 14.4.
**Why:** leakage caused the Phase 2 result.
**How:** one pixel per landslide; spatial blocks; tuning, thresholds, imputation and scaling inside training folds; no landslide-layer attributes as features; feature choices made without labels; and a coordinates-only control. It scored 0.557 in Phase 3 and 0.561 with geology.
**What it means:** the control only protects a test that includes it. The Phase 5 test had none, which is why its score was inflated (Item 32).

### 27. ML models
**Where it comes from:** `scripts/phase3/10_train_evaluate_v3.py`; DATA-028, DATA-028b.
**Why:** to test whether the choice of algorithm matters.
**How:** Logistic Regression, SVM (RBF), Random Forest, XGBoost, LightGBM and a Random Forest, XGBoost and LightGBM ensemble.
**What it means:** XGBoost was used for the maps. The tree models tie, so the choice of algorithm matters far less than the choice of data.

### 28. Hyperparameters
**Where it comes from:** `data/phase3/modeling/results/best_params.json`; `models/phase3/feature_list_natural.json`.
**Why:** tuning on test data would be leakage.
**How:** Optuna TPE inside training folds.

| Model | Trees | Depth | Learning rate | Subsample | Columns | L2 | Min child weight |
|---|---|---|---|---|---|---|---|
| All-factor XGBoost | 250 | 6 | 0.0128 | 0.883 | 0.603 | 3.22 | 5 |
| Natural-terrain XGBoost | 150 | 5 | 0.0223 | 0.980 | 0.754 | 10.59 | 12 |

The natural model's macro-F1 threshold is 0.46.
**What it means:** tuning LR, SVM and RF made no meaningful difference (Item 30).

### 29. Evaluation metrics
**Where it comes from:** DATA-028, DATA-030; README 14.
**Why:** one metric hides too much.
**How:** ROC-AUC, PR-AUC, macro-F1, F1 per class, MCC and Brier score on balanced tests. On maps: rate curves, share captured in the top of the land, and frequency ratio by zone.
**What it means:** F1 and precision here come from balanced tables. Landslide pixels are 0.008 % of the land, so these are not field alarm rates.

### 30. Model comparison
**Where it comes from:** `nested_metrics_summary.csv`, `pooled_auc_block_bootstrap.csv` in `data/phase3/modeling/results/`; `tuned_baselines_v2_summary.csv` in `data/phase4/modeling/results/`.
**Why:** to compare under the same test.
**How:** nested 10 km spatial CV, all 25 factors. Confidence intervals exist only for the first group.

| Model | ROC-AUC | 95 % CI | PR-AUC | Macro-F1 | MCC |
|---|---|---|---|---|---|
| XGBoost | 0.945 | 0.933 to 0.955 | 0.949 | 0.878 | 0.755 |
| LightGBM | 0.945 | 0.932 to 0.954 | 0.949 | 0.878 | 0.756 |
| Ensemble | 0.945 | 0.933 to 0.955 | 0.949 | 0.876 | 0.753 |
| Random Forest, tuned | 0.944 | Not computed | 0.948 | 0.883 | 0.766 |
| SVM (RBF), tuned | 0.910 | Not computed | 0.899 | 0.842 | 0.688 |
| Logistic Regression, tuned | 0.892 | Not computed | 0.869 | 0.828 | 0.658 |
| **Distance to a road alone** | **0.912** | | | **0.839** | **0.682** |

The last row comes from repeated CV (`repeated_spatial_cv_summary.csv`).
**What it means:** the tree models are tied, and most of their score is what road distance alone already gives.

### 31. Feature importance
**Where it comes from:** `feature_family_importance.csv`, `natural_feature_importance.csv` in `data/phase3/modeling/results/`; `data/phase4/modeling/results/feature_family_importance.csv`.
**Why:** to see what the model relies on outside its training blocks.
**How:** permutation importance on held-out blocks.
* **All-factor model:** shuffling the road layers costs about 0.40 of ROC-AUC. Every other group costs under 0.01, and geology costs nothing.
* **Natural model, on road-matched tests:** slope 0.093, mean annual rainfall 0.021, profile curvature 0.013, TWI 0.012.

**What it means:** in the natural model, steeper and wetter ground ranks higher. This is association, not proof of cause.

### 32. Final model
**Where it comes from:** `models/phase3/final_natural.pkl`, `models/phase3/final_xgboost.pkl`; DATA-041 to DATA-045.
**Why:** the map needs one model, chosen on evidence.
**How:** the recommended model is **natural-terrain v3**: XGBoost with 21 factors, trained on 1,859 landslides plus 3,718 negatives.

**Why v5 is not recommended.** v5 added 1,434 mapped polygons and passed its fixed rule: Test P rose from 0.672 to 0.923 and Test R changed by −0.003. Later checks showed that this does not mean v5 is better:

| Check | Result | Source in `data/phase5/verification/` |
|---|---|---|
| Polygon concentration | 90.8 % lie in 3 map sheets | `polygon_sheet_counts.csv` |
| Coordinates alone on Test P | 0.892, near the full model | `polygon_controls.csv` |
| Same-area test, slope alone | 0.833, with no model | `same_area_test.csv` |
| Direction of mapped polygons | 1.9 % face north, 61.1 % south; all land is 22.5 % and 22.9 % | `aspect_by_group.csv` |
| Very High zone inside and outside polygon blocks | v5: 14.4 % and 5.3 %; v3: 7.3 % and 9.2 % | `map_footprint_check.csv` |
| Unused polygons outside training sheets | v5 0.704, v3 0.692 | `v5_unseen_test.csv` |
| Unseen records from 2024 onward | v5 0.758, v3 0.788 | `data/phase5/maps/independent_validation_2024_v5.csv` |

The rule compared polygons from a few sheets with negatives from the whole state, so location alone could score well, and it had no location control. The polygons also have a direction pattern not seen in the GSI points or the 2024 records. The cause is not known. One possibility is that scars on sunlit slopes are easier to see in imagery. v5 learned this pattern: aspect is its third-strongest factor.

**What it means:** on tests v5 did not train on, it gains 0.012 in one and loses 0.030 in the other. It offers no clear gain, and its Very High zone partly follows the survey footprint.

### 33. Susceptibility/prediction map
**Where it comes from:** `data/final/`; `data/phase3/maps/`; DATA-029, DATA-030, DATA-040.
**Why:** this is the deliverable.
**How:** every land cell was scored, then zoned by natural breaks (1-D k-means on 1,000,000 cells). Values are relative scores from 0 to 1.

| Zone | Natural v3, held-out GSI: % land / % landslides | Natural v3, unseen polygons: % land / % landslides | All-factor v3, unseen polygons: % land / % landslides |
|---|---|---|---|
| Very High | 8.4 / 33.1 | 8.7 / 17.8 | 4.6 / 10.3 |
| High | 15.6 / 25.4 | 17.7 / 31.1 | 6.6 / 5.6 |
| Moderate | 22.4 / 19.2 | 25.4 / 31.8 | 8.9 / 6.1 |
| Low | 26.4 / 14.5 | 28.7 / 17.9 | 20.1 / 22.6 |
| Very Low | 27.1 / 7.9 | 19.5 / 1.4 | 59.8 / 55.4 |

Main file: `data/final/mizoram_landslide_zones_v3_natural.tif`.
**What it means:** on unseen polygons, the natural map's Very Low zone holds 1.4 % of landslides. The all-factor map's holds 55.4 %, so "Very Low" on that map does not mean safe.

### 34. Limitations
**Where it comes from:** main log, "Phase 3 limitations"; README 16.7 and 18.
**Why:** these limit how the map may be used.
**How:**
1. Inventory bias: road corridors for GSI points; 3 map sheets and a direction pattern for mapped polygons.
2. Unsurveyed ground may hold unrecorded landslides that were labelled as stable.
3. GSI points may be recorded from the road, so their terrain values may describe the road bench.
4. Every test set is GSI data. None is an outside survey.
5. The polygons' mapping method and dates are unknown.
6. Rainfall (5.5 km) and soil (250 m) are coarse; straight-edged bands on the maps follow rainfall cells.
7. The DEM is a surface model, so canopy affects slope and flow routing.
8. An unmapped road counts as "far from a road".
9. Scores are relative and not calibrated. F1 values come from balanced tables.

**What it means:** the map supports screening and comparison between areas. It does not replace site investigation.

### 35. Future improvements
**Where it comes from:** README 16.10 and 18.
**Why:** each item addresses a limitation above.
**How:**
1. Ask NRSC for its seasonal inventory, the strongest available outside test.
2. Compare with GSI's National Landslide Susceptibility Map on NGDR.
3. Find out how the polygons were mapped, and why so few face north.
4. If polygons are used in training again, control for location and direction.
5. Use a bare-earth DEM, and dated rainfall with the dated NGDR points.

**What it means:** better data matters more now than a more complex model.

### 36. Complete source list
**Where it comes from:** `documentation/SOURCES.md`; README 12.
**Why:** every source must be credited.
**How:** data citations and method references are held there, including Chung and Fabbri (2003), Roberts et al. (2017), Tarboton (1997), Phillips et al. (2009), Funk et al. (2015), Poggio et al. (2021) and Styron and Pagani (2020).
**What it means:** the NGDR licence was not stated, so GSI is credited and use should be checked before redistribution.

### 37. Complete troubleshooting history
**Where it comes from:** the main log, `documentation/MIZORAM_LANDSLIDE_PROJECT_DOCUMENTATION.md`.
**Why:** the specification requires a real-time record.
**How:** entries DATA-000 to DATA-046 record each step, with failure fields where needed. Corrections are added, and earlier text is kept.
**What it means:** the log shows where earlier claims were wrong and how they were found.

### 38. Complete project changelog
**Where it comes from:** `documentation/CHANGELOG.md`.
**Why:** it gives a dated summary of each change.
**How:** entries run from 2026-08-22 to 2026-11-01, each with the change, reason and impact.
**What it means:** the main changes in the project's conclusions can be followed there in date order.
