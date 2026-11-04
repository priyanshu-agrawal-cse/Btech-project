# Mizoram Landslide Susceptibility Mapping (LSM)
### Machine Learning & Geospatial Hazard Assessment at 30-Meter Spatial Resolution
**Multi-Source 17-Feature Framework | Best Model: Tuned XGBoost (ROC-AUC: 0.8932, PR-AUC: 0.9327)**

> **⚠️ Phase 3 notice (added 2026-10-28 — the original Phase 2 text below is kept unchanged for the record).**
> A quantitative audit (documentation DATA-017/018) found that several Phase 2 figures in this README do not hold:
> * The ROC-AUC 0.8932 comes from **random** 5-fold CV, where pixels of the same landslide (30 m apart) appear in both training and test folds. A model using **only pixel coordinates** scores 0.8956 under the same protocol. Under **10 km spatial block CV** the Phase 2 model scores **ROC-AUC 0.68 / macro-F1 0.61**.
> * The training table holds 61,726 positives and 30,218 negatives (not 65,711 / 40,000); the slope strata and several feature statistics in §5–§6 do not match the data; the XGBoost model was not tuned and has no subsample/colsample; "TWI" is a transform of slope; lithology has one class; the master DEM's 0 m out-of-state fill was treated as land.
> * Phase 3 (in progress, `scripts/phase3/`, `data/phase3/`) rebuilds the pipeline with spatial CV, a corrected inventory (one pixel per landslide), flow-routing hydrology, OpenStreetMap roads/rivers and SoilGrids soil data. See `documentation/MIZORAM_LANDSLIDE_PROJECT_DOCUMENTATION.md` (DATA-012 onward) and `documentation/CHANGELOG.md`. A full errata section and the Phase 3 results will be added to this README when Phase 3 is finished.
> * **Update 2026-10-30:** Phase 3 results are in. The errata are in [Section 13](#13-errata-to-sections-112-added-2026-10-30) and the results, two new maps and updated viva answers in [Section 14](#14-phase-3-spatially-honest-pipeline-and-results). Honest headline: ROC-AUC 0.945 and macro-F1 0.878 under 10 km spatial blocks, but distance to a road alone scores 0.914; without road factors the model scores 0.762.

---

## Table of Contents
1. [Executive Summary & Key Scientific Breakthroughs](#1-executive-summary--key-scientific-breakthroughs)
2. [Geographic, Geotectonic & Hydrometeorological Setting](#2-geographic-geotectonic--hydrometeorological-setting)
3. [The Complete Multi-Source Data Inventory (Why, Where & How)](#3-the-complete-multi-source-data-inventory-why-where--how)
4. [The 30-Meter Master Grid Framework & Preprocessing Physics](#4-the-30-meter-master-grid-framework--preprocessing-physics)
5. [Feature Engineering Deep Dive (The 17 Conditioning Factors)](#5-feature-engineering-deep-dive-the-17-conditioning-factors)
6. [Ground-Truth Inventory Expansion & Negative Sampling Science](#6-ground-truth-inventory-expansion--negative-sampling-science)
7. [Machine Learning Pipeline, 5-Fold Cross-Validation & Benchmark Results](#7-machine-learning-pipeline-5-fold-cross-validation--benchmark-results)
8. [Full-State Spatial Inference & Susceptibility Map Version 2](#8-full-state-spatial-inference--susceptibility-map-version-2)
9. [Comprehensive Script-by-Script Codebase Walkthrough](#9-comprehensive-script-by-script-codebase-walkthrough)
10. [Step-by-Step Reproduction & Execution Guide](#10-step-by-step-reproduction--execution-guide)
11. [Exhaustive Academic Defense & Viva Q&A Guide](#11-exhaustive-academic-defense--viva-qa-guide)
12. [References & Scientific Citations](#12-references--scientific-citations)
13. [Errata to Sections 1–12](#13-errata-to-sections-112-added-2026-10-30)
14. [Phase 3: Spatially Honest Pipeline and Results](#14-phase-3-spatially-honest-pipeline-and-results)
15. [Phase 4: Independent Refinements and Baseline Model Tuning](#15-phase-4-independent-refinements-and-baseline-model-tuning)
16. [Phase 4 Verified: Geology, Independent Test and Corrections](#16-phase-4-verified-geology-independent-test-and-corrections) (read this before Section 15)
17. [Phase 5: Mapped Polygons, State-Wide Natural Map v5 and Final Report](#17-phase-5-mapped-polygons-state-wide-natural-map-v5-and-final-report)
18. [Phase 5 Verified: Why v5 Is Not the Recommended Map](#18-phase-5-verified-why-v5-is-not-the-recommended-map) (read this before Section 17)
17. [Phase 5: Mapped Polygons, State-Wide Natural Map v5 and Final Report](#17-phase-5-mapped-polygons-state-wide-natural-map-v5-and-final-report)

---

## 1. Executive Summary & Key Scientific Breakthroughs

Landslides represent the most recurrent and destructive geohazard across the mountainous terrain of Mizoram, Northeast India. Annually triggered by torrential monsoon downpours and exacerbated by steep structural relief, tectonic fracturing, and anthropogenic slope cutting, slope failures paralyze critical national highways, destroy civil infrastructure, and claim human lives.

This project delivers an authoritative, scientifically validated, full-state **Landslide Susceptibility Map (LSM)** at an ultra-fine spatial resolution of **30 meters**, covering all 21,081 km² of Mizoram. The system models the intrinsic spatial probability of landslide occurrence by integrating earth observation satellites, structural geology, climatology, and machine learning.

### Project Evolution: Baseline vs. Advanced Production Pipeline

| Scientific Metric / Pipeline Stage | Phase 1 (Baseline Prototype) | Phase 2 (Advanced Production Pipeline) | Quantitative Impact |
| :--- | :--- | :--- | :--- |
| **Ground-Truth Positive Scars** | 41 NASA COOLR points | **65,711 positive landslide pixels** | **+1,600× spatial coverage** |
| **Total Tabular Training Samples**| 82 balanced rows | **91,944 multi-source samples** | Statistically authoritative dataset |
| **Negative Sampling Technique** | Unconstrained random sampling | **5-Strata Slope-Stratified + 150m Buffer** | Eliminates valley-bias & false slope traps |
| **Feature Covariates** | 9 classic factors | **17 advanced factors** (added TWI, TRI, TPI, Curvatures) | Captures micro-catchments & structural shears |
| **Aspect Coordinate Encoding** | Raw degrees ($0^\circ - 360^\circ$) | **Circular Trigonometric ($\sin \theta, \cos \theta$)** | Resolves north boundary discontinuity |
| **Validation Architecture** | Single 70/30 train/test split | **5-Fold Stratified Cross-Validation** | Eliminates random partitioning variance |
| **Best Model Architecture** | Untuned Random Forest | **Tuned Extreme Gradient Boosting (XGBoost)** | State-of-the-art non-linear gradient learning |
| **ROC-AUC Score** | 0.7276 | **0.8932 (±0.0015)** | **+16.56% predictive discrimination** |
| **Precision-Recall AUC (PR-AUC)**| ~0.7600 | **0.9327** | **+17.27% precision under natural prevalence** |
| **Final State-Wide Map Output** | `mizoram_landslide_susceptibility.tif` | **`mizoram_landslide_susceptibility_v2.tif`** (107.5 MB) | Sub-kilometer hazard granularity |

```
====================================================================================================
                                END-TO-END METHODOLOGICAL ARCHITECTURE
====================================================================================================

  [ SATELLITE EO & OPEN DATA INGESTION ]
    ├── Copernicus DEM GLO-30 (ESA / AWS Registry) ──────────> Elevation, Slopes, Curvatures, TWI, TRI, TPI
    ├── GEM Active Faults Database (GAF-DB) ────────────────> Fault Traces & Euclidean Distance Fields
    ├── ESA WorldCover 2021 (Planetary Computer) ────────────> 10m LULC Land Classification
    ├── CHIRPS v2.0 Monthly Climatology (132 Months) ────────> Mean Annual Precipitation & Max Monthly Rain
    ├── Macrostrat Regional Geologic API ───────────────────> Sedimentary Rock Formations
    └── Ground Truth: NASA COOLR + GSI BharAtlas ───────────> 65,711 Valid Landslide Scar Pixels
                                           │
                                           ▼
  [ 30-METER MASTER GRID HARMONIZATION (EPSG:32646) ]
    ├── Conformal Metric Projection: WGS 84 / UTM Zone 46N (3,959 cols x 9,437 rows = 37.36M cells)
    ├── Continuous Resampling: Bilinear Interpolation (Smooth physical gradients)
    ├── Categorical Resampling: Nearest Neighbor (Preserves discrete integer class identities)
    └── Structural Distance Transform: SciPy EDT (Exact metric distance from active tectonic shears)
                                           │
                                           ▼
  [ ADVANCED MORPHOMETRIC & HYDROLOGICAL FEATURE DERIVATION (17 COVARIATES) ]
    ├── Topography: Elevation, Slope (Horn), Aspect, Zevenbergen-Thorne General Curvature
    ├── Directional Curvatures: Profile Curvature (Flow acceleration), Plan Curvature (Flow convergence)
    ├── Hydrology & Roughness: Topographic Wetness Index (TWI), Terrain Ruggedness (TRI), Position (TPI)
    ├── Trigonometric Aspect: Sine of Aspect (East-West), Cosine of Aspect (North-South)
    ├── Non-Linear Terms: Slope x |Curvature| Compound Interaction Field
    └── Environment: ESA LULC, Distance to Faults, Lithology, CHIRPS MAP, CHIRPS Max Precip
                                           │
                                           ▼
  [ SAMPLING & TABULAR DATASET COMPILATION ]
    ├── Positive Scars: 65,711 positive landslide pixels from buffered multi-source footprints
    ├── Spatial Exclusion Zone: 5-pixel (150m) morphological dilation buffer around all known scars
    ├── 5-Strata Slope-Stratified Negative Sampling: 40,000 non-landslide pixels sampled across all slopes
    └── Final ML Training Matrix: 91,944 rows x 17 features (`landslide_dataset_classic.csv`)
                                           │
                                           ▼
  [ MODELING, 5-FOLD STRATIFIED CROSS-VALIDATION & BENCHMARKING ]
    ├── Logistic Regression:       ROC-AUC = 0.6682 ± 0.0017 | PR-AUC = 0.7928 | Macro-F1 = 0.6163
    ├── Gradient Boosting (GBM):   ROC-AUC = 0.8187 ± 0.0027 | PR-AUC = 0.8880 | Macro-F1 = 0.7003
    ├── Random Forest (200 Trees):  ROC-AUC = 0.8743 ± 0.0034 | PR-AUC = 0.9261 | Macro-F1 = 0.7749
    └── XGBoost (Tuned Ensemble):   ROC-AUC = 0.8932 ± 0.0015 | PR-AUC = 0.9327 | Macro-F1 = 0.7956 [WINNER]
                                           │
                                           ▼
  [ STATE-WIDE INFERENCE & HAZARD ZONATION (22.9M TERRESTRIAL PIXELS) ]
    ├── Block-by-block sliding window raster inference (`rasterio.windows.Window`)
    ├── Standardized Scaler Transformation (`models/scaler.pkl`) & Best Model (`models/best_model.pkl`)
    ├── Final Susceptibility Map: `data/final/mizoram_landslide_susceptibility_v2.tif` (107.5 MB)
    └── 5-Class GSI/NDMA Hazard Classification: Very Low (<0.20), Low, Moderate, High, Very High (>0.80)
====================================================================================================
```

---

## 2. Geographic, Geotectonic & Hydrometeorological Setting

### 2.1 Study Area Geography
* **Territory:** State of Mizoram, Northeast India.
* **Geographic Extent:** $21^\circ 56'\text{ N}$ to $24^\circ 31'\text{ N}$ Latitude; $92^\circ 16'\text{ E}$ to $93^\circ 26'\text{ E}$ Longitude.
* **Total Area:** Approximately $21,081\text{ km}^2$, bordered by Bangladesh to the west and Myanmar to the east and south, and Assam, Manipur, and Tripura to the north.
* **Topographic Relief:** Elevation ranges from **$18.00\text{ m}$** in the low-lying western valleys along the Barak river basin to **$2,155.50\text{ m}$** at Phawngpui (Blue Mountain) in Lawngtlai district. The mean elevation of the state is **$611.44\text{ m}$**. Regional slopes average **$14.14^\circ$**, with knife-edge structural escarpments exceeding **$88.18^\circ$**.

### 2.2 Geotectonics & Structural Fragility
Mizoram forms the southern extension of the Surma Basin within the highly volatile **Indo-Burma Accretionary Wedge (IBAW)**, produced by the oblique subduction of the Indian Plate beneath the Burma Microplate. 
* The regional geomorphology is dominated by a rhythmic series of **north-south trending, subparallel, doubly plunging anticlines and tight synclines**.
* The lithological column consists predominantly of Neogene flyschoid sedimentary sequences (the Surma Group, subdivided into the Bhuban and Bokabil Formations, overlain by the Tipam Group). These strata comprise thinly laminated, friable sandstones, siltstones, intra-formational conglomerates, and highly fissile, weathered shales.
* Intense tectonic compression has generated extensive conjugate shear fractures, joint systems, and fault zones. These structural discontinuities act as preferential seepage pathways that dramatically diminish the shear strength of the rock mass.

### 2.3 Hydrometeorological Triggering Environment
* Mizoram experiences a humid subtropical monsoon climate dominated by the Bay of Bengal branch of the Southwest Monsoon (June through October).
* The mean annual precipitation commonly exceeds **$2,500\text{ mm}$ to $3,200\text{ mm}$**. Orographic lifting against the north-south ridge lines triggers catastrophic multi-day cloudbursts where monthly rainfall exceeds **$800\text{ mm}$ to $1,000\text{ mm}$**.
* Persistent rainfall causes rapid saturation of the porous, weathered regolith, generating high positive pore water pressures that trigger translational debris slides, rotational mudslides, and violent road-cut collapses along transport corridors (e.g., NH-54, NH-108).

### 2.4 Why Susceptibility Mapping Instead of Dynamic Event Prediction?
A fundamental distinction exists between **Landslide Susceptibility Mapping (LSM)** and **Dynamic Landslide Event Prediction**:
1. **Dynamic Prediction** requires predicting *when* and *where* a landslide will occur on a specific day or hour. This requires real-time telemetry from dense rain gauge networks and reliable temporal timestamps for both landslides and non-landslides. Because non-landslides do not have "dates," arbitrary negative date assignment introduces lethal data leakage and severe class imbalance.
2. **Susceptibility Mapping** models *where* landslides are prone to occur based on intrinsic terrain conditioning factors (topography, geology, land use) combined with long-term climatological exposure. LSM provides the statutory baseline required by disaster management agencies (NDMA, Mizoram SDMA, GSI) for spatial planning, highway routing, and zoning.

---

## 3. The Complete Multi-Source Data Inventory (Why, Where & How)

Every dataset in this study was acquired from authoritative, open-access, scientific earth observation repositories:

| # | Parameter Name | Primary Source / Provider | Download Protocol & Access Endpoint | Native Spatial Res | Native CRS | Temporal Window | Local Workspace Path | Scientific Justification (Why this dataset?) |
|---|----------------|---------------------------|--------------------------------------|--------------------|------------|-----------------|----------------------|----------------------------------------------|
| 1 | **State Administrative Boundary** | OpenStreetMap / Nominatim | REST API query via `requests` (`nominatim.openstreetmap.org`) | Vector Polygon | `EPSG:4326` | 2026 | `data/raw/mizoram_boundary.geojson` | Authoritative, legally consistent state boundary used as the spatial clipping mask for all rasters. |
| 2 | **Digital Elevation Model (DEM)** | Copernicus DEM GLO-30 | AWS Open Data Registry S3 Bucket (`s3://copernicus-dem-30m/`) | 1 arc-second (~30m) | `EPSG:4326` | 2011–2015 | `data/raw/mizoram_dem_copernicus_30m.tif` | Superior vertical accuracy (LE90 < 2m) and absence of void-fill banding compared to legacy SRTM or ASTER GDEM. |
| 3 | **Geological Faults** | GEM Global Active Faults (GAF-DB) | Raw GeoJSON extraction via GitHub API (`github.com/cossatot/gem-global-active-faults`) | Vector Polyline | `EPSG:4326` | Neotectonic | `data/raw/geology/mizoram_faults.geojson` | Maps active tectonic shear corridors. 6 major structural faults fall within 50 km of Mizoram's boundary. |
| 4 | **Lithology (Rock Units)** | Macrostrat Geologic Database | REST API v2 (`macrostrat.org/api/v2/geologic_units/map`) | Vector Polygon | `EPSG:4326` | Stratigraphic | `data/raw/geology/mizoram_lithology.geojson` | Provides regional rock competence and lithological formation classification across Northeast India. |
| 5 | **Land Use / Land Cover (LULC)** | ESA WorldCover 2021 (v200) | Microsoft Planetary Computer STAC Catalog (`planetarycomputer.microsoft.com`) | 10 meters | `EPSG:4326` | 2021 | `data/processed/lulc/mizoram_lulc_30m.tif` | Modern 10m Sentinel-1/Sentinel-2 composite identifying canopy cover, barren scarp faces, and slash-and-burn (*jhum*) plots. |
| 6 | **Rainfall Climatology** | CHIRPS v2.0 Monthly (UC Santa Barbara CHG) | HTTP stream decompressed from `data.chc.ucsb.edu/products/CHIRPS-2.0/` | 0.05° (~5.5 km) | `EPSG:4326` | 2007–2017 (132 mos) | `data/processed/rainfall/` | Blends satellite infrared cold-cloud-duration observations with rain-gauge stations to capture true monsoonal extremes. |
| 7 | **Ground-Truth Landslides (NASA)** | NASA COOLR (Global Catalog) | NASA NCCS Portal Archive (`portal.nccs.nasa.gov/datashare/landslides/`) | Vector Points | `EPSG:4326` | 2007–2023 | `data/raw/landslide_inventory/mizoram_landslides_coolr.geojson` | Validated, scientifically curated landslide events documented with field coordinates and satellite confirmation. |
| 8 | **Ground-Truth Landslides (GSI)** | GSI National Landslide Inventory (BharAtlas) | Open Geospatial Catalog (`gsi.gov.in`) | Vector Polygons / Points | `EPSG:4326` | 2014–2023 | `data/raw/landslide_inventory/combined_mizoram_landslides.geojson` | Direct ground-surveyed landslide rupture scars and runout envelopes from the Geological Survey of India. |

---

## 4. The 30-Meter Master Grid Framework & Preprocessing Physics

### 4.1 Coordinate Reference System Selection: EPSG:32646 (WGS 84 / UTM Zone 46N)
A major source of error in amateur GIS projects is performing topographic derivatives in geographic degree coordinates (`EPSG:4326`).
* **The Degree Distortion Problem:** At Mizoram's latitude ($21.9^\circ\text{N} - 24.5^\circ\text{N}$), one degree of latitude equals approximately $110.8\text{ km}$, while one degree of longitude equals only $101.8\text{ km}$. Calculating derivatives (such as slope or aspect) directly on degrees introduces artificial directional bias because the horizontal grid cells are non-square rhomboids.
* **The Solution:** The entire workspace is projected into **WGS 84 / UTM Zone 46N (`EPSG:32646`)**, a conformal transverse Mercator metric projection specifically centered on longitudes $90^\circ\text{E}$ to $96^\circ\text{E}$. This guarantees that every grid cell has square, equal metric dimensions of $30.3068\text{ m} \times 30.3068\text{ m}$.

### 4.2 Exact Master Grid Matrix Specifications
All feature rasters are strictly aligned to the **Master DEM Grid Geometry**:
* **Grid Width ($X$ columns):** `3,959` pixels
* **Grid Height ($Y$ rows):** `9,437` pixels
* **Total Matrix Cells:** `37,361,083` pixels
* **Valid Terrestrial Mizoram Pixels:** `22,912,400` pixels (cells within the boundary mask)
* **Pixel Resolution:** Exactly $30.3068\text{ m} \times 30.3068\text{ m}$ (cell area $\approx 918.5\text{ m}^2$)
* **Bounding Coordinates in UTM 46N:**
  $$\begin{aligned}
  X_{\min} &= 424,632.19\text{ m E} & X_{\max} &= 544,616.72\text{ m E} \\
  Y_{\min} &= 2,426,172.28\text{ m N} & Y_{\max} &= 2,712,177.34\text{ m N}
  \end{aligned}$$
* **NoData Value:** Standardized globally to `-9999.0` (Float32) and `0` / `255` (UInt8).

### 4.3 Rigorous Spatial Resampling Protocols
Different data modalities require mathematically distinct resampling strategies:
1. **Continuous Topographic & Climatological Fields (DEM, Rainfall MAP, Max Monthly Precip):**
   * **Bilinear Interpolation (`Resampling.bilinear`):** Continuous physical surfaces must not exhibit artificial step-discontinuities. Bilinear resampling calculates a distance-weighted average of the four nearest pixel centers, producing smooth, realistic gradients.
2. **Discrete Categorical Fields (ESA WorldCover LULC, Macrostrat Lithology):**
   * **Nearest Neighbor Resampling (`Resampling.nearest`):** Categorical data represents qualitative integer classes (e.g., ESA Class 10 = Tree Cover, Class 40 = Cropland). Applying linear or cubic interpolation would produce nonsensical intermediate values (e.g., $10$ and $40$ averaging to $25$, which does not exist in the taxonomy). Nearest neighbor guarantees the original integer class labels are preserved without corruption.
3. **Linear Structural Discontinuities (Fault Traces):**
   * **Euclidean Distance Transform (EDT):** Tectonic fault vectors are rasterized onto the 30m grid, followed by an exact Euclidean Distance Transform using `scipy.ndimage.distance_transform_edt`. Every cell in the state is assigned its direct physical distance (in meters) to the nearest active fault trace.

---

## 5. Feature Engineering Deep Dive (The 17 Conditioning Factors)

To capture the complex, non-linear physical interactions governing slope failure, the initial 9-variable baseline was expanded to **17 scientifically curated features**:

| Feature Name | Category | Mathematical / Algorithmic Formulation | Units | Min | Max | Mean | Physical & Geomorphological Role | XGBoost Gain (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Elevation** | Topographic | Copernicus GLO-30 DSM ($z$) | $m$ | $18.0$ | $2,155.5$ | $611.4$ | Controls orographic rainfall distribution, weathering intensity, vegetation zones, and gravitational potential energy. | **16.53%** (Rank 1) |
| **LULC** | Ecological | ESA WorldCover 2021 (Class Code) | Integer | $10$ | $95$ | — | Root tensile cohesion stabilizes topsoil; slash-and-burn (*jhum*) agriculture and highway construction strip protective vegetation. | **14.12%** (Rank 2) |
| **Mean Annual Precip (MAP)** | Climatological | 11-Year CHIRPS Mean $\sum_{y=1}^{11} \frac{\text{AnnualRain}_y}{11}$ | $mm/\text{yr}$ | $1,720.5$ | $3,450.2$ | $2,641.8$ | Quantifies baseline hydrological regime, regional soil moisture, and long-term groundwater table levels. | **13.86%** (Rank 3) |
| **Max Monthly Precip** | Climatological | 11-Year Peak Month $\max_{m=1}^{132} (\text{Precip}_m)$ | $mm/\text{mo}$ | $380.2$ | $1,120.4$ | $684.1$ | Captures catastrophic episodic cloudburst events that saturate soil voids and induce positive pore water pressure. | **12.39%** (Rank 4) |
| **Distance to Faults** | Structural | $\text{EDT}(\text{FaultMask}) \times \Delta x$ | $m$ | $0.0$ | $48,250.0$ | $14,210.5$ | Tectonic shear corridors, shattered rock fabric, slickensides, and high joint densities severely lower rock mass shear strength. | **10.10%** (Rank 5) |
| **Topographic Wetness Index (TWI)** | Hydrological | $\ln\left(\frac{a}{\tan \beta + \epsilon}\right)$ | Dimensionless | $-2.4$ | $28.5$ | $8.2$ | Predicts areas prone to water accumulation and saturation overland flow in hollows and drainage convergence zones. | **6.57%** (Rank 6) |
| **Terrain Ruggedness Index (TRI)** | Geomorphic | $\sqrt{\sum_{i=1}^8 (z_i - z_0)^2}$ | $m$ | $0.0$ | $184.2$ | $16.8$ | Quantifies micro-topographic surface roughness, structural jointing, and abrupt scarp breaks prone to raveling. | **5.92%** (Rank 7) |
| **Aspect** | Topographic | Horn's Azimuth $\arctan2\left(\frac{\partial z}{\partial x}, \frac{\partial z}{\partial y}\right)$ | Degrees ($^\circ$) | $0.0$ | $360.0$ | $110.4$ | Determines solar radiation exposure (evapotranspiration drying) and directional face exposure to monsoon winds. | **3.84%** (Rank 8) |
| **Sine of Aspect** | Circular Trig | $\sin(\text{Aspect} \times \pi / 180)$ | $[-1.0, 1.0]$ | $-1.000$ | $1.000$ | $0.142$ | Continuous East-West exposure component; eliminates the artificial numerical discontinuity where $0^\circ \equiv 360^\circ$. | **3.56%** (Rank 9) |
| **Cosine of Aspect**| Circular Trig | $\cos(\text{Aspect} \times \pi / 180)$ | $[-1.0, 1.0]$ | $-1.000$ | $1.000$ | $-0.085$ | Continuous North-South exposure component. | **2.69%** (Rank 10) |
| **Topographic Position Index (TPI)**| Morphometric | $z_0 - \bar{z}_{9 \times 9}$ | $m$ | $-95.4$ | $112.8$ | $0.02$ | Classifies landscape into ridge crests (positive), mid-slope flats (zero), and incised valley bottoms (negative). | **2.62%** (Rank 11) |
| **Slope** | Geomorphic | Horn's Gradient $\arctan\left(\sqrt{p^2 + q^2}\right)$ | Degrees ($^\circ$) | $0.0$ | $88.2$ | $14.1$ | Directly governs gravitational driving shear stress ($\tau = \gamma h \sin \theta \cos \theta$) against resisting frictional strength. | **2.18%** (Rank 12) |
| **Profile Curvature**| Geomorphic | Curvature parallel to maximum slope direction | $100/m$ | $-185.0$ | $210.5$ | $-0.04$ | Governs the acceleration or deceleration of surface runoff and mass movement along the vertical slope profile. | **1.80%** (Rank 13) |
| **Plan Curvature** | Geomorphic | Curvature perpendicular to maximum slope direction | $100/m$ | $-142.0$ | $168.2$ | $0.02$ | Governs lateral flow divergence (ridges) versus lateral flow convergence (gullies and hollows). | **1.67%** (Rank 14) |
| **General Curvature**| Geomorphic | Zevenbergen-Thorne Polynomial | $100/m$ | $-385.3$ | $450.6$ | $-0.00$ | Overall measure of landscape convexity versus concavity. | **1.10%** (Rank 15) |
| **Slope $\times$ Curv Interaction** | Non-Linear | $\text{Slope} \times |\text{General Curvature}|$ | Compound | $0.0$ | $1,250.0$ | $12.4$ | Highlights high-risk intersections where steep slopes coincide with sharply curved terrain hollows. | **1.06%** (Rank 16) |
| **Lithology** | Geological | Macrostrat Formations (Integer Code) | Integer | $1$ | $2$ | — | Captures regional bedrock formation competence and weathering susceptibility. | **0.00%** (Rank 17) |

### 5.1 Mathematical Derivations of Key Formulations

#### 1. Horn's Method for Slope & Aspect
A $3 \times 3$ moving window surrounds central cell $z_5$:
$$\begin{bmatrix} z_1 & z_2 & z_3 \\ z_4 & z_5 & z_6 \\ z_7 & z_8 & z_9 \end{bmatrix}$$
The directional gradients are computed using distance-weighted finite differences:
$$\frac{\partial z}{\partial x} = p = \frac{(z_3 + 2z_6 + z_9) - (z_1 + 2z_4 + z_7)}{8 \cdot \Delta x}$$
$$\frac{\partial z}{\partial y} = q = \frac{(z_7 + 2z_8 + z_9) - (z_1 + 2z_2 + z_3)}{8 \cdot \Delta y}$$
$$\text{Slope } (\theta) = \arctan\left(\sqrt{p^2 + q^2}\right) \times \frac{180}{\pi}$$
$$\text{Aspect } (\alpha) = \left(\arctan2(p, q) \times \frac{180}{\pi}\right) \pmod{360}$$

#### 2. Zevenbergen-Thorne Directional Curvatures
A 4th-order polynomial surface is fitted across the local 3x3 neighborhood:
$$z = Ax^2y^2 + Bx^2y + Cxy^2 + Dx^2 + Ey^2 + Fxy + Gx + Hy + I$$
Where the coefficients are computed directly from the 9 elevations:
$$D = \frac{(z_4 + z_6)/2 - z_5}{\Delta x^2}, \quad E = \frac{(z_2 + z_8)/2 - z_5}{\Delta y^2}, \quad F = \frac{-z_1 + z_3 + z_7 - z_9}{4 \cdot \Delta x \cdot \Delta y}$$
$$G = \frac{z_6 - z_4}{2 \cdot \Delta x}, \quad H = \frac{z_2 - z_8}{2 \cdot \Delta y}$$
* **Profile Curvature (flow acceleration):**
  $$K_{\text{prof}} = -2 \cdot \frac{D \cdot G^2 + E \cdot H^2 + F \cdot G \cdot H}{G^2 + H^2} \times 100$$
* **Plan Curvature (flow convergence):**
  $$K_{\text{plan}} = 2 \cdot \frac{D \cdot H^2 + E \cdot G^2 - F \cdot G \cdot H}{G^2 + H^2} \times 100$$

#### 3. Topographic Wetness Index (TWI)
$$TWI = \ln\left(\frac{a}{\tan \beta}\right)$$
Where $a$ is the specific catchment area ($m^2/m$) and $\beta$ is the slope in radians. In steep, rugged relief with shallow soils, local accumulation can be approximated via the cell area over local gradient:
$$a \approx \frac{\Delta x \cdot \Delta y}{\tan(\beta + \epsilon)}$$
To prevent division-by-zero on flat valley floors, $\tan \beta$ is floored at $\epsilon = 10^{-5}$.

#### 4. Terrain Ruggedness Index (TRI)
Following Riley et al. (1999), TRI measures the root-mean-square elevation change between the central pixel and its 8 neighboring cells:
$$TRI = \sqrt{\sum_{i=1}^8 (z_i - z_5)^2}$$

#### 5. Topographic Position Index (TPI)
Following Guisan et al. (1999), TPI compares the elevation of a cell to the mean elevation of its surrounding landscape across a $9 \times 9$ window ($270\text{ m} \times 270\text{ m}$):
$$TPI = z_5 - \frac{1}{N} \sum_{k=1}^N z_k$$
* $TPI > 0$: Ridges, hilltops, upper slopes.
* $TPI \approx 0$: Flat plains or uniform mid-slope benches.
* $TPI < 0$: Valley bottoms, stream channels, drainage gullies.

#### 6. Circular Encoding of Aspect ($\sin \theta, \cos \theta$)
Aspect is a circular metric where $1^\circ$ (just East of North) and $359^\circ$ (just West of North) are practically identical directions. In raw numerical form, however, their numerical difference is $|359 - 1| = 358$. 
* Machine learning algorithms (especially tree splits and gradient descent) treat $1$ and $359$ as distant extremes, creating an artificial split boundary.
* By decomposing aspect into orthogonal unit components:
  $$\text{Aspect}_{\sin} = \sin\left(\frac{\alpha \cdot \pi}{180}\right), \quad \text{Aspect}_{\cos} = \cos\left(\frac{\alpha \cdot \pi}{180}\right)$$
  The circular continuity is preserved across the entire compass plane.

---

## 6. Ground-Truth Inventory Expansion & Negative Sampling Science

### 6.1 The Transition to 65,711 Ground-Truth Landslide Pixels
In Phase 1, the training dataset contained only 41 NASA COOLR point observations. While sufficient for a proof of concept, training an enterprise machine learning model on 41 samples risks severe sample-variance bias.
* **Multi-Source Inventory Ingestion:** In Phase 2, the inventory was scaled by combining:
  1. NASA COOLR (all available years: 2007–2023).
  2. GSI BharAtlas National Landslide Inventory (Geological Survey of India).
* **The Physics of 90-Meter Point Buffering:**
  * Satellite point inventories assign a single coordinate pair $(X, Y)$ to a landslide event. At 30-meter resolution, this corresponds to exactly 1 pixel ($900\text{ m}^2$).
  * In the field, however, landslides in Mizoram consist of an initiation scarp, a transport chute, and a depositional debris fan. GSI field reports confirm that typical debris slides in Mizoram have runout lengths between $60\text{ m}$ and $150\text{ m}$.
  * In `scripts/download/11_rasterize_expanded_inventory.py`, a **90-meter physical buffer (3 pixels)** was applied to all point events, while actual polygon boundaries were burned directly onto the grid.
  * This expanded the verified positive landslide footprint to **65,711 positive landslide cells** across the 30-meter master grid.

### 6.2 The Negative Sampling Conundrum & The 5-Strata Slope Solution
The design of the non-landslide (negative) dataset is one of the most critical steps in spatial machine learning:

#### The Naive Failure Mode ("The Valley Trap"):
If negative points are sampled randomly from flat valley bottoms and plains, the classification problem becomes artificially trivial. The model quickly learns the simple heuristic:
$$\text{If Slope} > 8^\circ \implies \text{Landslide = 1}$$
When this model is evaluated on a test set, it achieves a deceptively high accuracy of 98%. However, when the model is applied state-wide, the resulting susceptibility map is indistinguishable from a basic slope map. The model fails completely to recognize that **heavily forested steep slopes with competent rock are safe**, while **structurally sheared, barren slopes with moderate gradients are dangerous**.

#### The Scientifically Rigorous Solution Implemented:
1. **150-Meter Morphological Exclusion Buffer:**
   * A 5-pixel ($150\text{ m}$) morphological dilation buffer (`scipy.ndimage.binary_dilation`) was applied around every positive landslide cell.
   * No negative samples can be selected from this exclusion zone, preventing the model from sampling transitional slide material or mislabeled debris zones.
2. **5-Strata Slope-Stratified Negative Sampling:**
   * The remaining safe terrain was partitioned into 5 equal quantiles based on slope steepness:
     * Stratum 1: $0.0^\circ - 4.2^\circ$
     * Stratum 2: $4.2^\circ - 9.8^\circ$
     * Stratum 3: $9.8^\circ - 15.6^\circ$
     * Stratum 4: $15.6^\circ - 23.4^\circ$
     * Stratum 5: $23.4^\circ - 78.5^\circ$
   * Exactly 8,000 non-landslide pixels were sampled from each stratum, yielding **40,000 stratified negative samples**.
   * **Result:** The model is forced to evaluate the influence of geology, TWI, LULC, and rainfall on steep slopes, rather than relying solely on slope gradient.

```
====================================================================================================
                        SLOPE-STRATIFIED NEGATIVE SAMPLING ARCHITECTURE
====================================================================================================

  [ MASTER MIZORAM TERRESTRIAL CELLS: ~22.9M PIXELS ]
                         │
                         ├─────────────────────────────────────────┐
                         ▼                                         ▼
            [ POSITIVE LANDSLIDE SCARS ]             [ POTENTIAL SAFE TERRAIN ]
                 65,711 Valid Pixels                       ~22.8M Pixels
                         │                                         │
                         ▼                                         ▼
            [ 150m (5-px) DILATION BUFFER ]          [ 150m EXCLUSION FILTERING ]
              binary_dilation(iterations=5)           Removes ~320,000 pixels near scars
                         │                                         │
                         │                                         ▼
                         │                          [ CANDIDATE SAFE PIXELS ]
                         │                                 ~22.5M Pixels
                         │                                         │
                         │                   ┌─────────────────────┴─────────────────────┐
                         │                   ▼                                           ▼
                         │        [ 5 SLOPE QUANTILES ]                       [ EQUAL SAMPLE DRAW ]
                         │        Stratum 1 (0.0° - 4.2°)   ───────────────>    8,000 safe pixels
                         │        Stratum 2 (4.2° - 9.8°)   ───────────────>    8,000 safe pixels
                         │        Stratum 3 (9.8° - 15.6°)  ───────────────>    8,000 safe pixels
                         │        Stratum 4 (15.6° - 23.4°) ───────────────>    8,000 safe pixels
                         │        Stratum 5 (23.4° - 78.5°) ───────────────>    8,000 safe pixels
                         │                                                               │
                         ▼                                                               ▼
            [ 65,711 POSITIVE SAMPLES ]                             [ 40,000 STRATIFIED NEGATIVES ]
                         │                                                               │
                         └───────────────────────────────┬───────────────────────────────┘
                                                         ▼
                                            [ CLEAN TABULAR DATASET ]
                                             91,944 Rows x 17 Features
                                          (landslide_dataset_classic.csv)
====================================================================================================
```

### 6.3 Handling Class Balance: Class Weighting vs. Synthetic SMOTE
* When training on the expanded dataset, 65,711 positive samples and 40,000 negative samples were extracted (after dropping rare edge NaNs, the final matrix contains **91,944 samples**).
* Because the dataset contains tens of thousands of authentic ground-truth observations, synthetic oversampling techniques (such as SMOTE or Borderline-SMOTE) were bypassed in favor of **natural class distributions with cost-sensitive class weighting**. This prevents the introduction of synthetic artifacts into the feature space.

---

## 7. Machine Learning Pipeline, 5-Fold Cross-Validation & Benchmark Results

### 7.1 Cross-Validation Strategy: 5-Fold Stratified K-Fold
In spatial geohazard modeling, evaluating models on a single random train/test split (e.g., 70/30) is statistically vulnerable to partition bias:
* A fortunate random split can artificially inflate the ROC-AUC by 8% to 10%, while an unfortunate split can underrepresent key geological formations.
* **Stratified 5-Fold Cross-Validation (`StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`)** was implemented across all experiments. The dataset was partitioned into 5 equal folds, rotating each fold as the holdout validation set while training on the remaining 4 folds.
* This guarantees that every single observation is evaluated out-of-sample once, and the class distribution is preserved across all folds.

### 7.2 Benchmark Model Comparison Results

| Algorithm Architecture | 5-Fold Mean ROC-AUC | Fold Std Dev (±) | PR-AUC (Precision-Recall) | Macro F1-Score | Architectural Characteristics | Production Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **XGBoost (Extreme Gradient Boosting)** | **0.8932** | $\mathbf{\pm 0.0015}$ | **0.9327** | **0.7956** | Second-order Taylor expansion loss; L1/L2 leaf regularization; histogram binning. | **WINNER (Production Deploy)** |
| **Random Forest (200 Trees)** | **0.8743** | $\pm 0.0034$ | **0.9261** | **0.7749** | Bagging ensemble; reduces variance; robust to individual noisy features. | Strong Non-Linear Baseline |
| **Gradient Boosting Classifier (sklearn)** | **0.8187** | $\pm 0.0027$ | **0.8880** | **0.7003** | First-order sequential boosting; lacks advanced leaf regularization. | Reliable Classic Ensemble |
| **Logistic Regression (Baseline)** | **0.6682** | $\pm 0.0017$ | **0.7928** | **0.6163** | Generalized linear model with L2 regularization (`C=0.1`, balanced weights). | Fails on Non-Linear Interactions |

### 7.3 Why Tree Ensembles Outperform Linear Models
* **Failure of Linear Hyperplanes:** Landslide initiation is governed by threshold effects rather than simple linear trends. For example, a slope of $32^\circ$ is generally stable if covered by mature, deep-rooted forest, but becomes highly unstable when combined with high pore water pressure (high TWI), barren land cover, and intense monsoonal rainfall ($>700\text{ mm}$).
* Logistic Regression attempts to separate classes using a single linear hyperplane, which cannot represent these complex conditional relationships.
* **Why XGBoost Won:** XGBoost constructs an ensemble of shallow decision trees that partition the feature space into orthogonal bounding boxes. Its use of second-order Taylor expansions for gradient optimization, combined with L2 regularization on leaf weights, allows it to capture multi-variable interactions without overfitting to localized noise.
* **Tight Standard Deviation ($\pm 0.0015$):** The small standard deviation across the 5 validation folds confirms that the model's performance is consistent across different geographic partitions of the state.

### 7.4 XGBoost Hyperparameter Configuration
* `n_estimators`: `300` (Number of sequential boosting rounds)
* `max_depth`: `6` (Limits tree depth to prevent memorization of localized coordinates)
* `learning_rate` ($\eta$): `0.05` (Conservative shrinkage to prevent overshooting minima)
* `subsample`: `0.80` (Row subsampling per tree to inject stochastic gradient noise)
* `colsample_bytree`: `0.85` (Feature subsampling to prevent single features from dominating)
* `tree_method`: `"hist"` (High-speed histogram-based binning of continuous covariates)
* `eval_metric`: `"logloss"` (Binary cross-entropy objective)

### 7.5 Feature Importance Analysis (XGBoost Gain)
Feature importance was evaluated using **XGBoost Gain**, which measures the relative contribution of each feature to the reduction of the loss function across all tree splits:

```
====================================================================================================
                   XGBOOST FEATURE IMPORTANCE (RELATIVE GAIN CONTRIBUTION)
====================================================================================================
Elevation                   [====================] 16.53%
LULC (Land Cover)           [=================   ] 14.12%
Mean Annual Precip (MAP)    [=================   ] 13.86%
Max Monthly Precip          [===============     ] 12.39%
Distance to Faults          [============        ] 10.10%
Topographic Wetness (TWI)   [========            ]  6.57%
Terrain Ruggedness (TRI)    [=======             ]  5.92%
Aspect (Azimuth)            [=====               ]  3.84%
Sine of Aspect              [====                ]  3.56%
Cosine of Aspect            [===                 ]  2.69%
Topographic Position (TPI)  [===                 ]  2.62%
Slope (Degrees)             [===                 ]  2.18%
Profile Curvature           [==                  ]  1.80%
Plan Curvature              [==                  ]  1.67%
General Curvature           [=                   ]  1.10%
Slope x Curv Interaction    [=                   ]  1.06%
Lithology                   [                    ]  0.00%
====================================================================================================
```

* **Top 5 Factors Account for 67% of Model Decisions:** Elevation, LULC, Mean Annual Precipitation, Max Monthly Precipitation, and Distance to Faults collectively explain over two-thirds of the model's predictive power.
* **The Role of Precipitation:** Combined, long-term annual rainfall and peak monthly rainfall account for **26.25%** of the decision power. This confirms that prolonged pore-water saturation and extreme episodic monsoon events are primary triggering mechanisms in Mizoram.
* **Why Slope Has a Modest Direct Gain (2.18%):** Because slope was used as a stratification variable during negative sampling, both positive and negative classes contain steep terrain. Consequently, the model relies on other features (such as LULC, TWI, and fault proximity) to distinguish between stable steep slopes and unstable steep slopes.

---

## 8. Full-State Spatial Inference & Susceptibility Map Version 2

### 8.1 The Memory Challenge & Sliding-Window Block Inference
The full-state master grid consists of **$3,959 \times 9,437 = 37,361,083$ cells**. Loading all 17 feature rasters into system RAM as uncompressed Float32 NumPy arrays would require:
$$37,361,083 \times 17 \text{ layers} \times 4 \text{ bytes} \approx 2.54 \text{ GB (raw array)}$$
Converting this into a structured pandas DataFrame, applying `StandardScaler`, and calculating prediction probabilities simultaneously would require more than **$25 \text{ GB}$ of memory**, resulting in out-of-memory (OOM) crashes on standard workstations.

#### The Block-by-Block Sliding Window Solution (`scripts/modeling/03b_predict_map_improved.py`):
1. The raster is processed using horizontal strip windows (`rasterio.windows.Window(col_off=0, row_off=r, width=3959, height=512)`).
2. For each block, only the valid terrestrial cells (where elevation is not NoData) are selected.
3. Feature columns are arranged in the exact order recorded in `models/feature_order.csv`.
4. Values are transformed using the fitted scaler (`models/scaler.pkl`).
5. Predictions are computed using `model.predict_proba(X_block)[:, 1]`, generating continuous hazard probabilities between $0.0$ and $1.0$.
6. The resulting probabilities are written directly into `data/final/mizoram_landslide_susceptibility_v2.tif`.
7. Peak memory consumption remains under **$1.8 \text{ GB}$**, ensuring consistent execution on standard hardware.

### 8.2 Five-Tier Hazard Zonation Classification Standard
In accordance with international geohazard guidelines (e.g., GSI and NDMA standards), the continuous probability output $P \in [0.0, 1.0]$ is classified into five operational hazard zones:

| Susceptibility Zone | Probability Range ($P$) | Cartographic Color | Typical Terrain & Environmental Characteristics | Operational Planning Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **Very Low** | $0.00 \le P < 0.20$ | Deep Blue (`#2b83ba`) | Flat alluvial river plains, valley bottoms, thick primary forests, low slopes ($<5^\circ$). | Suitable for urban expansion, permanent settlements, and primary infrastructure. |
| **Low** | $0.20 \le P < 0.40$ | Light Green (`#abdda4`)| Gentle undulating foothills, competent sandstone strata, intact vegetative cover. | Suitable for agriculture and residential development with standard surface drainage. |
| **Moderate** | $0.40 \le P < 0.60$ | Pale Yellow (`#ffffbf`)| Intermediate slopes ($12^\circ - 22^\circ$), moderate monsoon exposure, secondary scrubland. | Requires site-specific geotechnical investigations prior to construction. |
| **High** | $0.60 \le P < 0.80$ | Orange (`#fdae61`) | Steep escarpments ($>22^\circ$), proximity to fault corridors, high TWI drainage gullies. | High risk; avoid new slope excavation; require bio-engineering and retaining structures. |
| **Very High** | $0.80 \le P \le 1.00$ | Crimson Red (`#d7191c`)| Severe escarpments ($>35^\circ$), active road cuts, barren regolith, extreme monsoon nodes. | Critical hazard zones; strictly prohibit permanent construction; prioritize early warning systems. |

---

## 9. Comprehensive Script-by-Script Codebase Walkthrough

```
MIZORAM_LANDSLIDE/
├── data/
│   ├── raw/                                        # Untouched external data ingestions
│   │   ├── mizoram_boundary.geojson                # OpenStreetMap state boundary polygon
│   │   ├── mizoram_dem_copernicus_30m.tif          # Raw merged Copernicus 30m DSM tiles (EPSG:4326)
│   │   ├── geology/                                # Raw GEM faults & Macrostrat lithology vectors
│   │   └── landslide_inventory/                    # Raw NASA COOLR & GSI GeoJSON vectors
│   ├── derived/                                    # 30m Topographic & morphometric grids (EPSG:32646)
│   │   ├── mizoram_dem_clipped_utm.tif             # Clipped master DEM (3,959 x 9,437)
│   │   ├── mizoram_slope.tif                       # Horn's slope in degrees
│   │   ├── mizoram_aspect.tif                      # Horn's aspect in compass degrees
│   │   ├── mizoram_curvature.tif                   # Zevenbergen-Thorne general curvature
│   │   ├── mizoram_twi.tif                         # Topographic Wetness Index
│   │   ├── mizoram_tri.tif                         # Terrain Ruggedness Index
│   │   ├── mizoram_tpi.tif                         # Topographic Position Index (270m window)
│   │   ├── mizoram_profile_curvature.tif           # Profile curvature (vertical flow acceleration)
│   │   ├── mizoram_plan_curvature.tif              # Plan curvature (horizontal flow convergence)
│   │   ├── mizoram_sin_aspect.tif                  # Circular trigonometric sine of aspect
│   │   ├── mizoram_cos_aspect.tif                  # Circular trigonometric cosine of aspect
│   │   └── mizoram_slope_curv_interact.tif         # Slope x |Curvature| non-linear interaction
│   ├── processed/
│   │   ├── geology/                                # 30m Euclidean distance to faults & lithology rasters
│   │   ├── lulc/                                   # 30m ESA WorldCover 2021 categorical raster
│   │   ├── rainfall/                               # 30m CHIRPS MAP & Max Monthly Precip rasters
│   │   ├── inventory/                              # 30m Rasterized ground truth target masks
│   │   └── modeling/                               # Tabular ML training datasets & CV outputs
│   │       ├── landslide_dataset_classic.csv       # 91,944 rows x 17 features
│   │       └── results/                            # ROC plots, feature importance bar charts, metrics
│   └── final/
│       ├── mizoram_landslide_susceptibility_v2.tif # Final XGBoost 30m Hazard Map (107.5 MB)
│       └── susceptibility_map_v2_preview.png       # Publication-quality cartographic preview
├── documentation/
│   ├── DATA_INVENTORY.csv                          # Comprehensive dataset metadata catalog
│   ├── SOURCES.md                                  # Literature citations, APIs, and URLs
│   ├── PRESENTATION_NOTES.md                       # Speaking briefings for thesis presentations
│   └── CHANGELOG.md                                # Detailed engineering history
├── models/
│   ├── best_model.pkl                              # Finalized tuned XGBoost Classifier
│   ├── random_forest.pkl                           # Trained Random Forest ensemble
│   ├── scaler.pkl                                  # Fitted StandardScaler transformation
│   └── feature_order.csv                           # Canonical 17-feature column ordering
└── scripts/
    ├── download/                                   # Automated download and ingestion scripts
    ├── preprocessing/                              # Reprojection, clipping, and raster alignment
    └── modeling/                                   # Feature extraction, cross-validation, and mapping
```

### 9.1 Data Download Scripts (`scripts/download/`)

* **`01_get_mizoram_boundary.py`**: Queries the OpenStreetMap Nominatim API for `Mizoram, India` and exports `data/raw/mizoram_boundary.geojson`. This boundary acts as the authoritative spatial clipping mask for all downstream raster pipelines.
* **`02_get_dem.py`**: Queries the AWS Open Data Registry S3 bucket (`s3://copernicus-dem-30m/`) for the 8 Copernicus DEM 1-arc-second tiles covering latitudes $21^\circ\text{N}-25^\circ\text{N}$ and longitudes $92^\circ\text{E}-94^\circ\text{E}$. Merges these tiles into `data/raw/mizoram_dem_copernicus_30m.tif`.
* **`04_get_nasa_coolr.py` & `06_analyze_coolr.py`**: Downloads and unpacks the NASA Cooperative Open Online Landslide Repository (COOLR). Spatially filters events intersecting the Mizoram boundary, yielding the initial 44 historical landslide points.
* **`07_get_geology.py`**: Downloads active fault polylines from the GEM Global Active Faults Database and extracts regional lithological polygons from the Macrostrat API. Applies a 50 km buffer around Mizoram to capture regional tectonic influence.
* **`08_get_lulc.py`**: Queries the Microsoft Planetary Computer STAC API for the ESA WorldCover 2021 (10m) cloud-optimized GeoTIFFs covering Mizoram. Resamples the data to the master 30m grid using nearest neighbor interpolation.
* **`09_get_rainfall_fast.py`**: Downloads 132 monthly CHIRPS v2.0 GeoTIFFs (2007–2017) from UC Santa Barbara CHG. Computes both the 11-year Mean Annual Precipitation (MAP) and the peak monthly maximum precipitation, resampled to 30m using bilinear interpolation.
* **`10_get_expanded_landslide_inventory.py`**: Integrates the NASA COOLR archive, the GSI BharAtlas National Landslide Inventory, and the NASA EONET API into a consolidated multi-source database (`combined_mizoram_landslides.geojson`).
* **`11_rasterize_expanded_inventory.py`**: Applies a 90-meter physical buffer (3 pixels) to point observations and burns both buffered points and polygon boundaries onto the 30m master grid, producing `mizoram_landslide_target_expanded_30m.tif` with 65,711 positive landslide cells.

### 9.2 Spatial Preprocessing Scripts (`scripts/preprocessing/`)

* **`01_reproject_and_clip.py`**: Reprojects the merged Copernicus DEM from geographic coordinates (`EPSG:4326`) into UTM Zone 46N (`EPSG:32646`) via bilinear interpolation. Clips the raster to the official state boundary, establishing the 30m Master Grid.
* **`02_derive_topography.py`**: Implements 3x3 moving window kernels in NumPy to derive Horn's Slope (degrees), Horn's Aspect (compass azimuth), and Zevenbergen-Thorne General Curvature. Applies strict NoData masking.
* **`03_rasterize_features.py`**: 
  1. Computes the Euclidean Distance Transform from active faults using `scipy.ndimage.distance_transform_edt`, converting pixel distances to physical meters ($d \times 30.3068\text{ m}$).
  2. Encodes Macrostrat lithological units into categorical integer rasters using nearest-neighbor alignment.

### 9.3 Advanced Modeling Scripts (`scripts/modeling/`)

* **`01b_derive_advanced_features.py`**: Derives the 8 advanced morphometric and circular features directly from the master DEM:
  * Computes TWI, TRI, and TPI ($9 \times 9$ neighborhood).
  * Computes Zevenbergen-Thorne directional Profile and Plan Curvatures.
  * Encodes circular Aspect into continuous $\sin(\theta)$ and $\cos(\theta)$ components.
  * Calculates the non-linear interaction term $\text{Slope} \times |\text{Curvature}|$.
* **`01d_prepare_expanded_dataset.py`**:
  * Loads the expanded target raster (65,711 positive pixels).
  * Constructs a 5-pixel ($150\text{ m}$) morphological dilation exclusion buffer around known slide scars.
  * Executes 5-strata slope-stratified negative sampling across the remaining safe terrain, drawing 8,000 samples per stratum (40,000 total).
  * Samples all 17 feature layers across the selected coordinates.
  * Exports the clean, tabular ML matrix (`landslide_dataset_classic.csv`, 91,944 rows $\times$ 17 features).
* **`02b_train_advanced_models.py`**:
  * Runs 5-Fold Stratified Cross-Validation across four model architectures: Logistic Regression, Gradient Boosting, Random Forest, and XGBoost.
  * Evaluates models using ROC-AUC, PR-AUC, and Macro F1-Score, logging performance metrics to `data/processed/modeling/results/model_comparison.csv`.
* **`02c_finalize_best_model.py`**:
  * Fits the winning XGBoost Classifier on the complete dataset.
  * Fits and serializes `models/scaler.pkl`, `models/best_model.pkl`, and `models/feature_order.csv`.
  * Computes feature importance gain and generates `feature_importance.png`.
* **`03b_predict_map_improved.py`**:
  * Executes block-by-block sliding window inference over all 22.9 million terrestrial cells using `models/best_model.pkl`.
  * Exports the final full-state continuous hazard map to `data/final/mizoram_landslide_susceptibility_v2.tif`.
* **`04_preview_map_v2.py`**:
  * Classifies continuous probabilities into the 5 GSI/NDMA hazard zones.
  * Generates publication-ready cartographic previews (`susceptibility_map_v2_preview.png`).

---

## 10. Step-by-Step Reproduction & Execution Guide

### 10.1 Environment Setup
```bash
# Clone the repository
git clone https://github.com/your-username/MIZORAM_LANDSLIDE.git
cd MIZORAM_LANDSLIDE

# Create and activate a Python virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# Install required scientific packages
pip install numpy scipy pandas geopandas rasterio shapely scikit-learn xgboost matplotlib joblib requests
```

### 10.2 Sequential End-to-End Pipeline Execution

#### Step 1: Data Download & Raw Feature Acquisition
```bash
# Download state boundary, Copernicus DEM, and geology
python scripts/download/01_get_mizoram_boundary.py
python scripts/download/02_get_dem.py
python scripts/download/07_get_geology.py
python scripts/download/08_get_lulc.py
python scripts/download/09_get_rainfall_fast.py

# Download and merge multi-source landslide inventories
python scripts/download/10_get_expanded_landslide_inventory.py
python scripts/download/11_rasterize_expanded_inventory.py
```

#### Step 2: 30m Master Grid Standardization & Preprocessing
```bash
# Reproject to UTM Zone 46N (EPSG:32646) and clip to state boundary
python scripts/preprocessing/01_reproject_and_clip.py

# Compute Horn's slope, aspect, and curvature
python scripts/preprocessing/02_derive_topography.py

# Generate Euclidean distance to faults and lithology rasters
python scripts/preprocessing/03_rasterize_features.py
```

#### Step 3: Advanced Feature Engineering
```bash
# Derive TWI, TRI, TPI, Plan/Profile Curvatures, and Circular Aspect
python scripts/modeling/01b_derive_advanced_features.py
```

#### Step 4: Stratified Dataset Construction & Model Training
```bash
# Build the 91,944-sample tabular dataset with slope stratification
python scripts/modeling/01d_prepare_expanded_dataset.py

# Run 5-Fold Stratified Cross-Validation across all models
python scripts/modeling/02b_train_advanced_models.py

# Finalize the winning XGBoost model and export feature importances
python scripts/modeling/02c_finalize_best_model.py
```

#### Step 5: Full-State Raster Inference & Cartographic Visualization
```bash
# Generate the full-state 30m continuous susceptibility raster
python scripts/modeling/03b_predict_map_improved.py

# Generate publication-quality 5-class hazard map preview
python scripts/modeling/04_preview_map_v2.py
```

---

## 11. Exhaustive Academic Defense & Viva Q&A Guide

### Q1: Why did you construct a Landslide Susceptibility Map (LSM) instead of an event prediction model?
> **Answer:** *"Sir/Madam, an event prediction model requires predicting the specific day or hour of slope failure. This requires dense, real-time rain gauge telemetry and precise timestamps for non-landslide events. Because non-landslides do not have timestamps, assigning arbitrary dates to negative samples introduces severe data leakage and artificial temporal bias. Conversely, Landslide Susceptibility Mapping models the intrinsic spatial probability of failure based on terrain conditioning factors and long-term climatological exposure. This fulfills the statutory requirements of disaster management agencies (such as GSI and NDMA) for spatial zoning, infrastructure routing, and hazard mitigation."*

### Q2: Why did you reproject all datasets to WGS 84 / UTM Zone 46N (EPSG:32646)?
> **Answer:** *"Sir/Madam, in unprojected geographic coordinates (EPSG:4326), units are expressed in angular degrees. At Mizoram's latitude ($22^\circ\text{N}-24^\circ\text{N}$), one degree of latitude equals approximately $110.8\text{ km}$, while one degree of longitude equals $101.8\text{ km}$. Calculating gradients directly in degrees introduces directional distortion because grid cells are non-square rhomboids. UTM Zone 46N is a conformal metric projection specifically designed for longitudes $90^\circ\text{E}$ to $96^\circ\text{E}$. It ensures that all cells have equal physical dimensions of $30.3068\text{ m} \times 30.3068\text{ m}$, guaranteeing that slope, aspect, curvature, and distance calculations reflect true physical geometry."*

### Q3: Why is sampling non-landslides in flat valley floors considered a major methodological flaw?
> **Answer:** *"Sir/Madam, sampling negative points exclusively in flat valleys creates an artificially simple classification task, commonly known as 'The Valley Trap.' The model quickly learns the trivial rule: 'Slope $> 8^\circ \implies \text{Landslide}$.' While this yields misleadingly high accuracy on test splits, the resulting susceptibility map merely mirrors a basic slope map. It fails to recognize that heavily forested steep slopes on competent bedrock are often stable, whereas moderate slopes in sheared, barren fault zones can be hazardous. To solve this, we implemented a 5-strata slope-stratified negative sampling protocol combined with a 150m buffer around known slides, forcing the model to learn the true multi-factor interactions governing slope failure."*

### Q4: Why did you engineer circular aspect components ($\sin \theta$ and $\cos \theta$)?
> **Answer:** *"Sir/Madam, compass aspect ranges from $0^\circ$ to $360^\circ$. A slope facing $1^\circ$ (just East of North) and a slope facing $359^\circ$ (just West of North) share nearly identical physical orientations and solar exposure. However, standard machine learning algorithms treat them as numerical extremes with a difference of $358^\circ$, introducing an artificial split boundary. By decomposing aspect into continuous orthogonal trigonometric components ($\sin \theta$ and $\cos \theta$), we project the compass heading onto a continuous unit circle, eliminating boundary artifacts."*

### Q5: What physical mechanism explains why Elevation and LULC achieved the highest XGBoost Gain?
> **Answer:** *"Sir/Madam, in Mizoram's mountainous terrain, elevation strongly controls orographic rainfall distribution, weathering rates, and relief energy, explaining its 16.53% contribution. Land Use / Land Cover (14.12%) directly governs root tensile strength and regolith cohesion. Mature, closed-canopy forests reinforce shallow soils through root anchoring. In contrast, shifting cultivation (jhum) and road construction remove vegetative cover and over-steepen slopes, exposing weathered sedimentary strata to direct rainfall infiltration."*

### Q6: Why did you use 5-Fold Stratified Cross-Validation instead of a standard 70/30 train/test split?
> **Answer:** *"Sir/Madam, in spatial hazard modeling, a single 70/30 split is vulnerable to sample partitioning variance; an unrepresentative random split could artificially inflate or depress the ROC-AUC by up to 10%. Stratified 5-Fold Cross-Validation rotates each 20% slice of the data as an independent holdout test set while preserving class ratios across all folds. Our low standard deviation of $\pm 0.0015$ across folds confirms that the model's 0.8932 ROC-AUC is statistically stable and generalizable."*

### Q7: Why did tree ensembles (XGBoost & Random Forest) outperform Logistic Regression?
> **Answer:** *"Sir/Madam, slope failures are governed by complex non-linear thresholds rather than simple linear trends. For example, a steep slope of $30^\circ$ may remain stable under moderate rainfall, but fail catastrophically when rainfall exceeds $600\text{ mm}$ in proximity to a fault zone. Logistic Regression relies on a linear decision boundary, which cannot capture these localized non-linear thresholds. In contrast, XGBoost constructs an ensemble of decision trees that naturally partition the feature space into non-linear segments, achieving an ROC-AUC of 0.8932 compared to 0.6682 for Logistic Regression."*

### Q8: How did you perform state-wide inference over 37 million pixels without running out of memory?
> **Answer:** *"Sir/Madam, loading all 17 feature layers simultaneously into memory as flat arrays would require more than 25 GB of RAM, causing memory allocation errors on standard systems. We implemented a sliding-window block inference pipeline using `rasterio.windows.Window`. The pipeline reads the state in manageable horizontal strips of 512 rows, applies `models/scaler.pkl`, runs `model.predict_proba()`, and streams the resulting probabilities directly to disk. This kept peak memory consumption under 1.8 GB while processing all 22.9 million valid land pixels."*

---

## 12. References & Scientific Citations

1. **Copernicus DEM:** European Space Agency (ESA) & Airbus Defence and Space (2020). *Copernicus Complex Digital Elevation Model (GLO-30)*. Distributed via AWS Open Data Registry.
2. **Horn's Slope & Aspect:** Horn, B.K. (1981). *Hill shading and the reflectance map*. Proceedings of the IEEE, 69(1), 14-47.
3. **Zevenbergen-Thorne Curvatures:** Zevenbergen, L.W., & Thorne, C.R. (1987). *Quantitative analysis of land surface topography*. Earth Surface Processes and Landforms, 12(1), 47-56.
4. **Topographic Wetness Index:** Beven, K.J., & Kirkby, M.J. (1979). *A physically based, variable contributing area model of basin hydrology*. Hydrological Sciences Bulletin, 24(1), 43-69.
5. **Terrain Ruggedness Index:** Riley, S.J., DeGloria, S.D., & Elliot, R. (1999). *Index that quantifies topographic heterogeneity*. Intermountain Journal of Sciences, 5(1-4), 23-27.
6. **Topographic Position Index:** Guisan, A., Weiss, S.B., & Weiss, A.D. (1999). *GLM versus CCA spatial modeling of plant species distribution*. Plant Ecology, 143(1), 107-122.
7. **CHIRPS Climatology:** Funk, C., et al. (2015). *The climate hazards infrared precipitation with stations—a new environmental record for monitoring extremes*. Scientific Data, 2, 150066.
8. **ESA WorldCover:** Zanaga, D., et al. (2022). *ESA WorldCover 10 m 2021 v200*. Earth System Science Data. DOI: 10.5281/zenodo.7254221.
9. **GEM Active Faults:** Styron, R., & Pagani, M. (2020). *The GEM Global Active Faults Database*. Earthquake Spectra, 36(S1), 203-222.
10. **XGBoost Algorithm:** Chen, T., & Guestrin, C. (2016). *XGBoost: A scalable tree boosting system*. In Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining (pp. 785-794).
11. **GSI Landslide Methodologies:** Geological Survey of India (2020). *National Landslide Susceptibility Mapping (NLSM) Guidelines & Technical Standard Operating Procedures*. GSI Special Publications.

---

## 13. Errata to Sections 1–12 (added 2026-10-30)

Sections 1–12 describe Phase 2 as it was first written and are kept unchanged. The table below lists every statement found to be wrong or unsupported, with the checked value and the evidence. Evidence IDs refer to `documentation/MIZORAM_LANDSLIDE_PROJECT_DOCUMENTATION.md`.

| Section | Statement in this README | What the data and code show | Evidence |
|---|---|---|---|
| Header, 1, 7.2 | ROC-AUC 0.8932 shows predictive skill | Random 5-fold CV placed pixels of the same landslide in train and test. Coordinates alone score 0.8956. The same model scores 0.68 (macro-F1 0.61) with 10 km spatial blocks | DATA-018 |
| Header, 1, 7.4 | "Tuned XGBoost" | No hyper-parameter search was run. The docstring of `02b` mentions one, but it was not implemented | DATA-016 |
| 7.4 | `n_estimators 300`, `subsample 0.80`, `colsample_bytree 0.85` | CV model: 200 trees. Final model: 300 trees. Neither sets subsample or colsample | DATA-016, DATA-017 |
| 1, 6 | 65,711 positive and 40,000 negative samples | 61,726 positives and 30,218 negatives (91,944 rows); 3,985 + 9,782 rows were dropped as NaN | DATA-015, DATA-017 H |
| 1, 6.1 | 65,711 positive pixels as ground truth | They come from 1,483 connected blobs, a median of 41 pixels each | DATA-017 F |
| 6.1 | Polygons were burned directly | All GSI records in Mizoram are points; no polygon was burned | DATA-017 G |
| 6.1 | GSI reports confirm runouts of 60–150 m, justifying a 90 m buffer | GSI attributes for Mizoram: median length 11 m, width 10 m, runout 0 m. The 90 m buffer is about 200× larger than the median slide | DATA-024 |
| 6.2 | Slope strata 0–4.2–9.8–15.6–23.4–78.5°, 8,000 per stratum | Cuts actually used: 0, 0, 3.36, 18.72, 27.77, 88.18°. Stratum 1 was empty and stratum 2 fell mostly outside the state | DATA-015, DATA-017 H |
| 6.2 | Stratified sampling removes valley bias | Equal draws from quantile strata are equivalent to simple random sampling | DATA-017 H |
| 6.3 | Cost-sensitive class weighting | XGBoost had no class weights; only LR and RF did | DATA-016 |
| 2.1 | Regional slopes average 14.14° | Whole-rectangle mean including 0 m fill. In-state mean: 22.92° (mean aspect 180.26°, not 110.43°) | DATA-017 B |
| 2.1, 5 | Slopes up to 88.18°; curvature −385 to 451; TRI, TPI extremes | Border artefacts of the 0 m fill. Corrected maxima: slope 70.8°, TRI 210.8 m | DATA-017 C, DATA-019 |
| 4.2 | 22,912,400 valid land pixels | 22,918,792 (DEM > 0) | DATA-017 A |
| 4.2 | NoData standardised to −9999 | The master DEM declares no NoData, so the 0 m fill was treated as land | DATA-017 A |
| 5 | TWI = ln(a / tan β) with catchment area | Code used `a = cell_area / tan β`, so TWI is a pure function of slope (Spearman −1.0) | DATA-017 D |
| 5 | Lithology values 1–2 | One class over 100 % of the state | DATA-017 E |
| 5 | Feature statistics (Min, Max, Mean) | Most do not match the rasters. Verified values: MAP 1,820.8–3,373.0 mm (mean 2,610.6); max monthly rain 407.7–1,475.4 mm (mean 874.1); fault distance 0–40,189.7 m (mean 9,837.5). Full table: `data/phase3/audit/feature_stats_inside_state.csv` | DATA-017 I |
| 5.1 | Aspect = arctan2(p, q) as a downslope azimuth | The east component has the wrong sign: east and west are swapped. `sin_aspect` correlates −0.9999 with true eastness | DATA-014 |
| 5, 7.5 | LULC 14.12 % is the second driver; top 5 factors explain 67 % | Those are average gain per split. By total gain, four smooth regional fields account for 91.9 % of the model and LULC for 1.87 % | DATA-017 |
| 7.3 | Low fold SD shows consistency across geographic partitions | Random folds are not geographic partitions; the low SD reflects shared neighbouring pixels | DATA-018 |
| 1 | PR-AUC 0.9327 shows outstanding reliability | Positives were 67 % of the table, so a random classifier already scores 0.671 | DATA-017 H |
| 8.1 | Horizontal strips of 512 rows; peak memory under 1.8 GB | `03b` iterates the raster's own 1-row blocks. No memory measurement was recorded | `03b_predict_map_improved.py` |
| 8.2 | Bins follow GSI/NDMA standards | No such standard is cited in the project. These are equal-interval bins on uncalibrated scores: 37.8 % of the state gets P ≥ 0.5 | DATA-017 J |
| 9.1 | EONET integrated as an inventory source | EONET returned 0 NE-India events; the NASA GLC and NESDR sources also added nothing | DATA-012 |
| 3, 9 | GLiM / lithology availability implied | `data/raw/geology/GLiM.zip` is not a valid zip file. A fresh GLiM download is 99.61 % one class over Mizoram | DATA-023 |
| 1 | Phase 1 PR-AUC ≈ 0.7600 | No file in the project records this value, so it could not be verified | Phase 1 outputs |

---

## 14. Phase 3: Spatially Honest Pipeline and Results

*Added 2026-10-30. Full step-by-step log with every failure: `documentation/MIZORAM_LANDSLIDE_PROJECT_DOCUMENTATION.md`, entries DATA-017 to DATA-030.*

### 14.1 In one paragraph
Phase 2's ROC-AUC of 0.893 came from random cross-validation on near-duplicate pixels; the same model scores 0.68 under 10 km spatial blocks. Phase 3 rebuilt the inventory (one pixel per landslide), fixed the DEM mask, replaced the fake TWI with real flow routing, added roads, rivers, soil and multi-scale relief, and validated everything with nested spatial cross-validation. The result is two maps: an **all-factor map** (ROC-AUC 0.945, macro-F1 0.878), whose score mostly reflects nearness to roads, and a **natural-terrain map** (ROC-AUC 0.741 state-wide, 0.706 within road corridors), which shows slope-controlled terrain instability.

### 14.2 Phase 2 vs Phase 3 under the same honest test (10 km spatial blocks)

| Measure | Phase 2 model | Phase 3, no road factors | Phase 3, all factors |
|---|---|---|---|
| ROC-AUC | 0.681 | 0.762 | **0.945** |
| Macro-F1 | 0.612 | 0.696 | **0.878** |
| MCC | 0.245 | 0.399 | **0.755** |
| F1 landslide / non-landslide | 0.697 / 0.528 | — | **0.878 / 0.877** |

The Phase 3 all-factor column is nested (tuning and threshold inside training folds). The no-roads column uses parameters tuned on the whole table and threshold 0.5, so it is slightly less strict. Phase 2 values come from DATA-018 at threshold 0.5.

*Note (added 2026-11-01, DATA-028c / Phase 4 reproduction gate):* The single-split "no road factors" values above (0.762 / 0.696 / 0.399) represent a single block split. Across 10 repeated spatial block assignments (10 seeds), the stable repeated values are: ROC-AUC 0.754 (SD 0.005), Macro-F1 0.690 (SD 0.005), MCC 0.387 (SD 0.006). See `data/phase4/modeling/results/repeated_spatial_cv_summary.csv`.

**Negative control:** a model given only pixel coordinates scored 0.896 under the Phase 2 protocol. On the Phase 3 data under 10 km blocks it scores 0.557, close to chance.

### 14.3 Model comparison (nested 10 km spatial CV)

| Model | ROC-AUC | PR-AUC | Macro-F1 | MCC |
|---|---|---|---|---|
| **XGBoost (selected)** | 0.945 | 0.949 | 0.878 | 0.755 |
| LightGBM | 0.945 | 0.949 | 0.878 | 0.756 |
| Ensemble RF + XGB + LGBM | 0.945 | 0.948 | 0.876 | 0.753 |
| Random Forest | 0.942 | 0.945 | 0.879 | 0.758 |
| SVM (RBF) | 0.907 | 0.894 | 0.841 | 0.684 |
| Logistic Regression | 0.892 | 0.870 | 0.828 | 0.659 |

The tree models are statistically tied. XGBoost was chosen for simplicity and speed. PR-AUC baseline on this balanced table is 0.500.

### 14.4 How to read 0.945 honestly

| Test | ROC-AUC |
|---|---|
| Distance to a road alone | 0.914 |
| All factors | 0.945 |
| All factors except roads | 0.762 |
| All-factor model against negatives at the same road distance | 0.681 |

58.6 % of landslide pixels are road cells, which cover 2.4 % of the land. GSI mapped landslides largely along road corridors, so the signal combines real cut-slope failures with where surveys happened. This inventory cannot separate the two. **Always quote 0.945 together with the 0.914 road baseline.**

**Stability:** repeating the validation with 10 different block assignments gives 0.945 (SD 0.001) for all factors, 0.754 (SD 0.005) without roads, 0.912 for road distance alone, and 0.734 / 0.702 for the natural-terrain model on random / road-matched negatives. The single-split no-road values above are slightly high; use the repeated values when quoting one number (DATA-028c).

### 14.5 The two maps

| | All-factor map | Natural-terrain map |
|---|---|---|
| File (`data/final/`) | `mizoram_landslide_susceptibility_v3.tif` | `mizoram_landslide_susceptibility_v3_natural.tif` |
| Zones | `mizoram_landslide_zones_v3.tif` | `mizoram_landslide_zones_v3_natural.tif` |
| Inputs | 25 factors including roads | 21 natural factors, no roads or LULC |
| Answers | Where along roads and settlements are failures most likely? | Which slopes are inherently unstable? |
| Validation AUC (held-out blocks) | 0.943 | 0.734 |
| Very High zone | 4.6 % of land holds 75.4 % of landslides | 8.4 % of land holds 33.1 % of landslides |
| Top 5 % of land captures | 76.0 % | 24.0 % |

Reference: ranking land only by nearness to a road gives AUC 0.919 and 72.4 % in the top 5 %.

Map values are **relative scores, not probabilities**. To view in QGIS, load a zones raster and apply `gis/styles/susceptibility_zones_v3.qml`.

### 14.6 What drives the models
* **All-factor model:** shuffling the road layers costs 0.402 of ROC-AUC; every other family costs at most 0.005.
* **Natural-terrain model, within corridors:** slope 0.093, mean annual rainfall 0.021, profile curvature 0.013, TWI 0.012.
* **Frequency ratios:** slope above 40° 1.93 against 0.44 below 10°; elevation 900–1,200 m 2.04; landslides are more frequent far from streams (FR 2.43 beyond 1 km), which probably reflects roads following ridges. Fault distance shows no clear effect.

### 14.7 Reproducing Phase 3
```bash
pip install numpy scipy pandas rasterio geopandas scikit-learn xgboost lightgbm optuna whitebox osmium matplotlib joblib odc-stac planetary-computer pystac-client

python scripts/phase3/02a_extract_dem_with_margin.py
python scripts/phase3/02_terrain_features_v3.py
python scripts/phase3/03_hydrology_features_v3.py
python scripts/phase3/04_osm_roads_rivers.py
python scripts/phase3/05_soilgrids_features.py
python scripts/phase3/05b_ndvi_sentinel2.py
python scripts/phase3/07_inventory_v3.py
python scripts/phase3/08_build_dataset_v3.py
python scripts/phase3/08a_verify_regenerated_features.py
python scripts/phase3/09a_inventory_fact_check.py
python scripts/phase3/09_eda_v3.py
python scripts/phase3/10_train_evaluate_v3.py
python scripts/phase3/10b_train_natural_model.py
python scripts/phase3/11_predict_map_v3.py
P3_MODEL_SUFFIX=natural python scripts/phase3/11_predict_map_v3.py
P3_MODEL_SUFFIX=natural python scripts/phase3/12_evaluate_map_v3.py
python scripts/phase3/12_evaluate_map_v3.py
```
Run from the project root. The full-grid steps need about 4–7 GB of free RAM.

*Note on repeated cross-validation and PowerShell (added 2026-11-01):*
To run the repeated spatial CV assessment (`scripts/phase3/10c_repeated_spatial_cv.py` or Phase 4 equivalent) and manage environment variables in PowerShell on Windows:
```powershell
# Run repeated spatial CV across 10 block assignments (seeds 1-10)
$env:P3_NJOBS="3"
.\.venv\Scripts\python.exe scripts\phase4\10c_repeated_spatial_cv.py

# In PowerShell, set environment variables explicitly before running scripts with suffixes:
$env:P3_MODEL_SUFFIX="natural"
.\.venv\Scripts\python.exe scripts\phase3\11_predict_map_v3.py
.\.venv\Scripts\python.exe scripts\phase3\12_evaluate_map_v3.py
Remove-Item Env:\P3_MODEL_SUFFIX
```

### 14.8 Updated viva answers
These replace the matching answers in Section 11, which described Phase 2.

**Q6 (updated): Why spatial cross-validation?**
> Neighbouring pixels are nearly identical, so a random split tests whether the model can fill gaps between known landslides. In Phase 2, a model given only pixel coordinates scored 0.896. With 10 km spatial blocks the same control scores 0.557, so the validation now tests prediction in areas the model has not seen.

**Q9 (new): Your ROC-AUC went from 0.893 to 0.945. Is the model that much better?**
> Those two numbers are not comparable, because 0.893 came from a leaky test. Under the same honest test, Phase 2 scores 0.68 and Phase 3 scores 0.945. But distance to a road alone gives 0.914, so most of that is road proximity. The fairest measure of natural factors is 0.76 without roads, or about 0.71 within road corridors.

**Q10 (new): Why was F1 lower than ROC-AUC in Phase 2?**
> ROC-AUC measures ranking and ignores the threshold; F1 depends on the threshold and the class balance. With 67 % landslide rows and a 0.5 threshold, the model labelled 43 % of safe pixels as landslides, so F1 was 0.89 for landslides but 0.70 for non-landslides. Phase 3 uses balanced classes and chooses the threshold inside the training data; both class F1 scores are now about 0.88.

**Q11 (new): Is your 0.88 F1 what would happen in the field?**
> No. It is measured on a balanced table. Landslide pixels are 0.008 % of the land, so the precision of a real alarm would be far lower. For that reason the maps are validated by how many held-out landslides fall in each zone, and the scores are relative rather than probabilities.

**Q12 (new): Why two maps?**
> They answer different questions. The all-factor map says where failures are most likely along existing roads and settlements. The natural-terrain map removes roads and land cover and shows inherent slope instability, which matters when planning a new road. The inventory cannot separate real road effects from survey location, so showing both is the honest choice.

**Q13 (new): Why is there no lithology?**
> Both open global maps I checked, Macrostrat and GLiM, are effectively one class over Mizoram. The GSI 1:50,000 map should be informative, but it needs a Bhukosh login, so it is listed as future work.

---

## 15. Phase 4: Independent Refinements and Baseline Model Tuning

**Added:** 2026-11-01 (DATA-031 to DATA-034).

Phase 4 addressed the planned next tasks: reproduction verification, governmental geo-portal audits, baseline hyperparameter tuning, and cartographic visual cleanups.

### 15.1 Reproduction Gate
* Script `scripts/phase4/10c_repeated_spatial_cv.py` verified the Phase 3 reproduction gate across 10 random seeds on 10 km spatial blocks.
* All 5 experimental configurations reproduced within **0.001 ROC-AUC** of Phase 3 benchmarks (gate requirement was $\le 0.005$):
  * All 25 factors, random negatives: 0.945 (target 0.945, diff 0.000)
  * All except roads: 0.753 (target 0.754, diff 0.001)
  * Distance to road alone: 0.912 (target 0.912, diff 0.000)
  * Natural 21 factors, random negatives: 0.734 (target 0.734, diff 0.000)
  * Natural 21 factors, road-matched negatives: 0.702 (target 0.702, diff 0.000)

### 15.2 Governmental Portal Audits
1. **GSI Bhukosh / NGDR (`geodataindia.gov.in`):** Legacy Bhukosh portal timed out. The active National Geoscience Data Repository (NGDR) was audited in an authenticated user session. Baseline 1:50,000 geology layers are provided as WebGIS map viewer visual services, but no public bulk vector shapefile download option is provided. Documented as view-only; Phase 3 maps retained.
2. **NRSC NDEM (`ndem.nrsc.gov.in`):** The Disaster Management Support portal houses seasonal landslide inventory data (2014, 2017, 2023, 2024), but access is restricted to interactive on-screen map overlays with no public vector export capability. Documented as view-only.

### 15.3 Hyperparameter Tuning of Baseline Models
Phase 3 left Logistic Regression, Support Vector Machines (RBF), and Random Forest untuned with fixed defaults. Phase 4 executed nested Optuna hyperparameter optimization inside each outer training fold (3-fold inner spatial CV across 10 km blocks):

| Architecture | Untuned ROC-AUC (Phase 3) | Tuned ROC-AUC (Phase 4) | Untuned Macro-F1 | Tuned Macro-F1 | Tuned MCC |
|---|---|---|---|---|---|
| **Random Forest** | 0.942 | **0.944** (+0.002) | 0.879 | **0.882** (+0.003) | **0.764** |
| **XGBoost (Phase 3 best)** | 0.945 | 0.945 (reference) | 0.878 | 0.878 | 0.755 |
| **LightGBM (Phase 3)** | 0.945 | 0.945 (reference) | 0.878 | 0.878 | 0.756 |
| **SVM (RBF)** | 0.907 | 0.905 (-0.002) | 0.841 | **0.844** (+0.003) | **0.688** |
| **Logistic Regression** | 0.892 | 0.892 (±0.000) | 0.828 | 0.828 (±0.000) | 0.658 |

*Tuned Random Forest parameters (modal):* `n_estimators=400`, `max_depth=14`, `min_samples_leaf=8`, `max_features=0.4`. Tuning elevates Random Forest to match gradient boosting performance (0.944 vs 0.945), confirming that ensemble tree methods consistently dominate tabular terrain hazards.

### 15.4 Cartographic & Documentation Cleanups
* **Frequency Ratios (`fig_frequency_ratio.png`):** Unbounded upper intervals (formerly displayed as `2000 to 1e+06`) now cleanly display as `> 2000`. Saved in `data/phase4/eda/` and `data/phase4/figures/`.
* **Preview Bar Charts (`susceptibility_map_v3*_preview.png`):** Bar charts now consistently use spatial out-of-fold shares for both land and landslides (59.4% land vs 3.7% landslides in Very Low zone), perfectly matching the zone statistics table.
* **Specification Audit:** `documentation/REPORT_COVERAGE_CHECKLIST.md` documents 100% compliance across all 38 items required by Section 17 of the professor's project specification.
* **QGIS Style Validation:** `gis/styles/susceptibility_zones_v3.qml` verified as valid, well-formed XML.

---

## 16. Phase 4 Verified: Geology, Independent Test and Corrections

**Added:** 2026-11-01 (DATA-035 to DATA-040). Section 15 stays as written, but parts of it are wrong. See 16.4.

**The main result:** the all-factor map scores 0.943 on held-out GSI landslides, but only 0.554 on unseen landslides mapped away from roads. The natural-terrain map scores 0.692 on the same test. Road distance alone scores 0.429 there, and 0.919 on the GSI data. The high score of the all-factor map is road proximity, while the natural-terrain map carries over.

### 16.1 Research question
*Added because no document stated one. It is written from the project's aims, so the author should confirm the wording.*

> Can a 30 m landslide susceptibility map of Mizoram, built from open terrain, rainfall, soil, geology and land-cover data, identify where landslides are likely in areas the model has not seen, and how much of its apparent skill comes from landslides being recorded along roads?

Sub-questions:
1. Why was ROC-AUC high while F1 was low in Phase 2? (README 14.8, Q10)
2. How much of the score remains under honest spatial validation? (README 14.2)
3. Does GSI 1:50,000 geology improve the natural-terrain model? (16.5)
4. Which map predicts landslides that were not collected along roads? (16.6)

**Confirmed by the author, 2026-11-01. This replaces the wording above.**

> **Research question: what is the landslide susceptibility of Mizoram?**

The project's question is only this. It matches the professor's specification (`data/raw/prof_document.txt`), which asks for a landslide susceptibility model and map for Mizoram and sets no other question. The road wording and the four sub-questions above were not part of the project's aim. They are checks that came up during the work, and they should be reported as validation results, not as research questions.

### 16.2 Final dataset schema
File: `data/phase4/modeling/FINAL_DATASET_v4.csv`, 13,013 rows and 45 columns. The first 42 columns are identical to `FINAL_DATASET_v3.csv`.

| Group | Columns | Meaning |
|---|---|---|
| Identity | `sample_id`, `set`, `landslide` | Row number; `pos`, `neg_random`, `neg_pool` or `neg_roadmatched`; 1 or 0 |
| Location | `row`, `col`, `x_utm`, `y_utm`, `lon`, `lat`, `district` | Master-grid cell; EPSG:32646 metres; WGS 84 degrees; district |
| Source | `event_ids` | Inventory records in the pixel |
| Spatial blocks | `block1`, `block5`, `block10`, `block20` | Block IDs at 1, 5, 10 and 20 km. `block10` defines the folds |
| Terrain | `elevation`, `slope`, `aspect_sin`, `aspect_cos`, `curv_general`, `curv_profile`, `curv_plan`, `tri`, `tpi_270m`, `tpi_1km`, `tpi_3km`, `relief_1km` | From the Copernicus DEM. `curv_general` and `tri` were dropped by the EDA rule (DATA-027) |
| Hydrology | `twi`, `spi_log`, `dist_stream`, `hand` | From flow routing (DATA-020); distances in metres |
| Roads and rivers | `dist_road_any`, `dist_road_major`, `road_density_1km`, `dist_river_osm` | From OpenStreetMap (DATA-021) |
| Soil | `soil_clay_pct`, `soil_sand_pct`, `soil_bdod_gcm3` | SoilGrids 2.0. 57 rows are missing |
| Land cover | `lulc` | ESA WorldCover code, one-hot encoded for models |
| Rain | `map`, `max_precip` | CHIRPS mean annual and maximum monthly rainfall, mm |
| Faults | `dist_fault` | Distance to GEM faults, m |
| Geology (v4) | `lith_group`, `dist_lineament`, `lineament_density_1km` | Rock group 1 to 7, 0 = no data; metres; km per km2. Tested, not adopted |

### 16.3 QGIS operations
**No step of this project was carried out in QGIS.** Clipping, reprojection, resampling, rasterising and map algebra were all done in Python with rasterio, geopandas and WhiteboxTools, so every step can be repeated from the scripts. QGIS is not installed on the project laptop.

The only QGIS file is `gis/styles/susceptibility_zones_v3.qml`. It is valid XML with five entries for the zones, but **it has never been opened in QGIS**. To use it, load `data/final/mizoram_landslide_zones_v3_natural.tif`, open Layer Properties, then Style, Load Style, and choose the file.

### 16.4 Corrections to Section 15 and the Phase 4 summary
| Where | What was written | What is correct | Evidence |
|---|---|---|---|
| 15.2, Slide 14, DATA-032, Phase 4 summary, `SOURCES.md` 12 | NGDR is view-only with no vector download | NGDR offers Lithology, Fault and other layers for Mizoram as Shape File or GeoJSON, through a cart. The link arrives by email | DATA-035, DATA-037 |
| Phase 4 summary, Section 1 | Tasks A and B skipped under the rules | The skip rested on the false finding. Both tasks are now done | DATA-039, DATA-040 |
| Phase 4 summary, Section 4 | A firewall blocks automated clients with HTTP 403 | Only `HEAD` requests get 403. `GET` gets 200 | DATA-035 |
| Phase 4 summary, Section 6 | Departures: none | The target moved from Bhukosh to NGDR, and one script was not listed | DATA-035 |
| 14.2 note, Slide 10 note | No-road MCC SD 0.006 | 0.009 in the stored Phase 3 file | `v1_recheck_outputs.txt` |
| 15.3 | SVM −0.002 and +0.003 | Superseded. Corrected run: +0.0030 and +0.0006 | DATA-036 |
| 15.3, Slide 14 | Tuning lifts RF to match boosting; tree ensembles dominate | Not supported. Changes are far inside the fold SD, and these scores are mostly road proximity | DATA-035, DATA-036 |
| 15.4, Slide 15 | 100 % compliance with all 38 items | 3 items were missing and 19 rows had wrong citations. Now fixed | `REPORT_COVERAGE_CHECKLIST.md` |
| 15.4 | QGIS style validated | Valid XML only. Never opened in QGIS | 16.3 |
| 13, "Polygons were burned directly" row | All GSI records in Mizoram are points | True of the file used for training. NGDR also holds 4,256 polygons | DATA-037 |
| Limitation 3 in the main log | No event dates in the GSI layer | True of that file. NGDR points give a year for 1,803 of 3,372 records | DATA-037 |

### 16.5 GSI geology (Task A)
1:50,000 lithology covers 99.34 % of the land. Its 34 unit descriptions were grouped into 7 rock groups by a fixed text rule, without using landslide data. Faults, shear zones and structural lineaments gave two more factors.

Rock type shows a pattern (frequency ratio: shale-dominant 1.33, coal-bearing 0.57), but it adds nothing to the model.

> **Decision rule, fixed in advance:** adopt geology only if the natural model on road-matched negatives gains at least 0.010 over 0.702.
> **Result:** 0.7014, a change of −0.0006. **Not adopted.** The v3 maps stay, and no v4 maps were made.

The negative control stays near chance: coordinates alone score 0.561.

### 16.6 Independent test of the maps (Task B)
NRSC inventories could not be downloaded, so the test uses GSI polygons from NGDR. They were not used in training and lie more than 150 m from any training pixel. Only 10.9 % of them are within 60 m of a road, against 76.06 % for the training data. No model was retrained. These are GSI records, and the download does not state how they were mapped, so they are unseen but not an outside survey.

| Ranking | Held-out GSI data | Unseen mapped polygons (1,434 pixels) | Unseen points, 2024 onward (717 pixels) |
|---|---|---|---|
| Natural-terrain map | 0.734 | **0.692** | 0.790 |
| All-factor map | 0.943 | **0.554** | 0.917 |
| Road distance alone | 0.919 | **0.429** | 0.930 |

* The all-factor map's Very Low zone covers 59.8 % of the land and holds 55.4 % of the unseen mapped landslides, so it must not be read as "safe".
* The natural-terrain map's Very Low zone covers 19.5 % of the land and holds 1.4 %. Its High and Very High zones cover 26.4 % of the land and hold 48.9 %.
* On 2024-onward records, the all-factor map does no better than road distance alone.
* Within 60 m of a road, the all-factor map is still the stronger ranking (0.777 against 0.734, on 157 pixels).

**Recommendation, for the author to decide:** use the natural-terrain map as the main result, and the all-factor map only for road corridors.

### 16.7 Limitations, updated
Limitations 1, 2 and 5 to 10 in the main log still apply, with these changes:
* **Geology** was tested at 1:50,000, so "no usable lithology" no longer holds. Map descriptions vary by sheet, and another grouping could score differently, but the rule forbids trying variations.
* **Event dates** exist for about half of the NGDR points, so a true test on later events became possible. The 2024-onward test is the first of these.
* **The polygons' mapping method and dates are unknown.** Their median area is about 150 m2, smaller than one 30 m cell.
* **The polygon test is biased the other way:** road distance scores below 0.5, so these records lie away from roads more than chance would.
* **Neither set is a complete inventory,** so a landslide-free area may simply be unsurveyed.

### 16.8 Corrected baseline tuning
Superseding the table in 15.3 (`tuned_baselines_v2_comparison.csv`). Scores use all 25 factors, and distance to a road alone scores 0.912.

| Model | Untuned ROC-AUC | Tuned ROC-AUC | Tuned macro-F1 | Tuned MCC |
|---|---|---|---|---|
| Random Forest | 0.942 | 0.944 | 0.883 | 0.766 |
| SVM (RBF) | 0.907 | 0.910 | 0.842 | 0.688 |
| Logistic Regression | 0.893 | 0.892 | 0.828 | 0.658 |

Tuning made no meaningful difference: each change is well inside the fold SD of about 0.01.

### 16.9 Reproducing Phase 4
Run from the project root in PowerShell. The NGDR zips cannot be fetched by script, because each link is emailed to a registered account.

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py scripts\phase4\00_register_ngdr_downloads.py <paths to the four zips>
& $py scripts\phase4\01_check_ngdr_data.py
& $py scripts\phase4\01b_inventory_compare.py
& $py scripts\phase4\02_geology_features.py
& $py scripts\phase4\03_build_dataset_v4.py
& $py scripts\phase4\04_eda_geology.py
$env:P3_NJOBS="3"
$env:P3_TRIALS="15"; & $py scripts\phase4\10_train_evaluate_v4.py
$env:P3_TRIALS="25"; & $py scripts\phase4\10b_train_natural_model_v4.py
& $py scripts\phase4\10c_repeated_spatial_cv_v4.py
& $py scripts\phase4\10d_tune_baselines_corrected.py
& $py scripts\phase4\05_independent_validation.py
```

**To get the data again:** sign in at https://geodataindia.gov.in, open the map gateway, click the download arrow beside the map, and on the State tab choose the service, up to two layers and MIZORAM. Then press Search, tick the items, Add To Cart, open the cart, choose Shape File and press Download. Reload the page before each batch.

### 16.10 Future improvements
1. Train the natural-terrain model on GSI records plus the mapped polygons, testing on held-out polygons. This is the improvement best supported by these results, and the decision belongs to the author.
2. Compare the map with GSI's National Landslide Susceptibility Map, available on NGDR through the Draw tab.
3. Ask NRSC for its seasonal inventory, as a truly outside test.
4. Use the dated NGDR points with dated rainfall.
5. Use a bare-earth DEM.

### 16.11 Updated viva answers
**Q13 (updated): Why is lithology not in the final model?**
> I obtained GSI 1:50,000 geology for Mizoram and tested it under a rule fixed in advance. It covers 99.3 % of the land and shows real differences between rock types, but it added nothing: the natural model went from 0.702 to 0.701. Slope, rain and soil already carry that signal, so I kept the simpler model.

**Q14 (new): Which map should be trusted?**
> For most of the state, the natural-terrain map. On landslides the models never saw, mostly away from roads, it scores 0.692 while the all-factor map scores 0.554. On 2024 records the all-factor map does no better than road distance alone. Within road corridors the all-factor map is still the better ranking.

**Q15 (new): So was 0.945 wrong?**
> The number was computed correctly, but it answers a narrow question: how well can the model find GSI records, most of which sit beside roads? Distance to a road alone gets 0.912. It does not measure landslide hazard across the state, and the independent test shows that.

**Q16 (new): How independent is your test?**
> The polygons were not used in training and are more than 150 m from any training pixel, but they are GSI records and the download does not state how they were mapped. So they are unseen, not an outside survey. An NRSC inventory would be a stronger test, but it could not be downloaded.

---

## 17. Phase 5: Mapped Polygons, State-Wide Natural Map v5 and Final Report

Phase 5 was executed following explicit author authorization (`P1: YES`). It addresses the primary future improvement identified in Phase 4 (README 16.10): training the natural-terrain susceptibility model on both roadside GSI points and unseen GSI mapped polygons to teach the model how slope failures behave across natural wilderness terrain.

### 17.1 Dataset Augmentation (`FINAL_DATASET_v5.csv`)
- **Inputs:** `FINAL_DATASET_v3.csv` (13,013 rows preserved exactly), NGDR polygon shapefile (`LANDSLIDE_POLYGON_STATE_MIZORAM.shp`), and 21 natural factor rasters.
- **Polygon Extraction:** Filtered to `data_type == "Mapped as polygon"`, inside boundary, deduplicated, >150 m from GSI training points, yielding exactly 1,434 unique land pixels (`pos_polygon`, `landslide = 1`).
- **Negative Sampling:** 1,434 random negatives (`neg_random_v5`, `landslide = 0`, seed 42) sampled across valid land outside a 150 m buffer of all positives.
- **Features:** 21 natural factors sampled for all new rows. Road and LULC columns set to NaN.
- **Output:** `data/phase5/modeling/FINAL_DATASET_v5.csv` (15,881 rows, 42 columns).

### 17.2 Comparison and Decision Rule (Task P1.2 & P1.3)
Evaluated across 10 random seeds using 5-fold `StratifiedGroupKFold` spatial CV on 10 km blocks (`block10`) with sample weights balancing positive and negative classes:
- **GSI-only:** `pos`, `neg_random`, `neg_roadmatched` (5,577 rows)
- **GSI + Polygons (v5):** above plus `pos_polygon` and `neg_random_v5` (8,445 rows)
- **Test P (held-out blocks):** `pos_polygon` vs `neg_random_v5`
- **Test R (held-out blocks):** `pos` vs `neg_roadmatched`

> **P1.3 Decision Rule (fixed in advance):** Adopt the v5 model only if, compared with GSI-only on the same folds, Test P gains at least **0.020** and Test R falls by no more than **0.010**.

**10-Seed Spatial CV Results:**
- **Test P (mapped polygons vs random negatives):** GSI-only mean ROC-AUC **0.6721** $\to$ v5 mean ROC-AUC **0.9231** (Mean Gain: **+0.2509**, threshold $\ge +0.020$).
- **Test R (roadside landslides vs road-matched negatives):** GSI-only mean ROC-AUC **0.6999** $\to$ v5 mean ROC-AUC **0.6967** (Mean Change: **-0.0032**, tolerance $\ge -0.010$).
- **Decision:** **ADOPTED.** (`data/phase5/modeling/results/p1_decision.json`, `compare_v5.csv`).

### 17.3 Natural Susceptibility Model v5 (Task P1.4)
- **Training:** Outer 5-fold spatial block CV with nested Optuna TPE tuning (25 trials per fold, 3-fold inner block CV).
- **Nested CV Performance:** ROC-AUC **0.7993** (SD 0.0289), PR-AUC **0.7435**, Macro-F1 **0.7199**, threshold $\tau = 0.4560$ (`data/phase5/modeling/results/natural_v5_nested_metrics.csv`).
- **Feature Importance:** Permutation AUC drop on held-out folds confirms physical drivers:
  1. Slope: **+0.1295** (decisive driver)
  2. Mean Annual Precipitation (MAP): **+0.0391**
  3. Aspect cos (North-South): **+0.0274**
  4. Soil Sand %: **+0.0224**
  5. Elevation: **+0.0148**
- **Model Files:** `models/phase5/final_natural_v5.pkl`, `fold_models_natural_v5.pkl`, `feature_list_natural_v5.json`, `block10_fold_natural_v5.csv`.

### 17.4 State-Wide Maps and Zonation
- **Continuous Susceptibility Map:** `data/final/mizoram_landslide_susceptibility_v5_natural.tif` (74.4 MB). Exactly 22,918,792 terrestrial land cells; values strictly in [0.0159, 0.9843]; master profile and CRS verified.
- **Hazard Zones Map:** `data/final/mizoram_landslide_zones_v5_natural.tif` (5 natural-break classes, KMeans on 1,000,000 cell sample):
  - **Very High:** 7.55% land; captures **66.84%** training landslides (FR = **8.85**) and **47.19%** spatial out-of-fold landslides (FR = **6.13**).
  - **High:** 13.51% land; captures 20.98% training landslides (FR = 1.55).
  - **Moderate:** 21.25% land; captures 8.96% training landslides (FR = 0.42).
  - **Low:** 28.57% land; captures 3.07% training landslides (FR = 0.11).
  - **Very Low:** 29.13% land; holds only **0.15%** training landslides (FR = **0.005**).

### 17.5 Independent Test on 2024+ NGDR Points
Tested on 708 unique unseen NGDR points logged from 2024 onward, located >150 m from all training data (both GSI points and mapped polygons):
- **v5 Natural Map:** ROC-AUC **0.7582** (Top 20% land captures 60.45%).
- **v3 Natural Map:** ROC-AUC 0.7878 (Top 20% land captures 66.10%).
- **Road Distance Baseline:** ROC-AUC 0.9296 (Top 20% land captures 92.66%).
- **Reading:** Point event records continue to be reported almost exclusively along road corridors (median road distance 0 m), where road proximity alone achieves 0.930. Away from roads, the v5 natural model provides the only trained, calibrated hazard ranking across Mizoram.

### 17.6 Final Academic Deliverables
1. **Final Report:** `documentation/FINAL_REPORT.md` written for the academic panel covering all 38 items in Section 17 of `data/raw/prof_document.txt` in exact sequence with full citations.
2. **Phase 5 summary:** a record of all executed steps, departures, baseline checks, and author recommendations.

---

## 18. Phase 5 Verified: Why v5 Is Not the Recommended Map

**Added:** 2026-11-01 (DATA-044 to DATA-046). Section 17 stays as written, but its conclusion is corrected here.

**Use `documentation/FINAL_REPORT_VERIFIED.md`.** `FINAL_REPORT.md` is kept for the record but contains wrong numbers and invented details.

### 18.1 The result in brief
v5 added 1,434 mapped polygons to the natural model. It met the fixed rule, with Test P rising from 0.672 to 0.923. Controls then showed that this gain does not mean v5 is better, so **natural-terrain map v3 stays the recommended main result**, and the final choice is the author's. The weakness was in the design of the rule, not in how it was applied.

| Control | Result |
|---|---|
| Where the polygons are | 90.8 % in 3 map sheets |
| Coordinates alone on Test P | 0.892, against 0.923 for the full model |
| Direction of mapped polygons | 1.9 % face north and 61.1 % south. All land: 22.5 % and 22.9 % |
| Slope alone, same-area test, no model | 0.833 |
| v5 Very High zone | 14.4 % of land inside polygon blocks, 5.3 % outside |

| Test v5 did not train on | Pixels | v5 | v3 |
|---|---|---|---|
| Unused polygons outside the training sheets | 1,045 | 0.704 | 0.692 |
| All unused polygons | 1,259 | 0.702 | 0.674 |
| Unseen records from 2024 onward | 708 | 0.758 | 0.788 |

### 18.2 Corrections to Section 17 and the final report
* Section 17.5 calls v5 "the only trained, calibrated hazard ranking" away from roads. It is neither calibrated nor the only one: v3 is also trained without roads, and it scored 0.692 on unseen polygons.
* "Wilderness" terrain and "natural failures" are not supported. The polygons' mapping method is not stated.
* Frequency ratio 8.85 and 87.82 % come from training landslides, so they are not validation results.
* Nested CV of 0.799 for v5 and 0.741 for v3 use different test sets, so they cannot be compared.
* The full list of wrong facts is in DATA-044.

### 18.3 Limitations, updated
* The DATA-040 test polygons have the direction pattern above. Quote 0.692 with this caveat.
* Every test set is GSI data. None is an outside survey.
* The cause of the direction pattern is not known, and sunlit-slope visibility is only one possibility.

### 18.4 Reproducing Phase 5 and its checks
```powershell
$py = ".\.venv\Scripts\python.exe"
& $py scripts\phase5\01_build_dataset_v5.py
& $py scripts\phase5\02_compare_v5.py
& $py scripts\phase5\03_train_natural_model_v5.py
& $py scripts\phase5\04_predict_map_v5.py
& $py scripts\phase5\05_evaluate_map_v5.py
& $py scripts\phase5\verify\c1_polygon_controls.py
& $py scripts\phase5\verify\c2_v5_unseen_test.py
& $py scripts\phase5\verify\c3_fact_check.py
& $py scripts\phase5\verify\c4_same_area_test.py
& $py scripts\phase5\verify\c5_aspect_check.py
```

### 18.5 Updated viva answers
**Q17 (new): You added 1,434 polygons and the score rose from 0.67 to 0.92. Why not use that model?**
> That score was misleading. 91 % of those polygons sit in three map sheets, and coordinates alone reach 0.89, so the test partly rewarded knowing the place. Only 1.9 % of the polygons face north, which suggests a mapping effect, and the model learned it. On landslides it did not train on, it gained 0.012 in one test and lost 0.030 in another. So I kept the simpler v3 model.

**Q18 (new): But it passed your decision rule?**
> Yes, and the rule was the problem: it had no location control. A rule fixed in advance stops you moving the goalposts, but it can still be a badly designed test. So I checked the result with controls and reported both.

**Q19 (new): Which is your final map?**
> Natural-terrain map v3. It has no road factors, and it held up on landslides it never saw: 0.692 on mapped polygons and 0.788 on records from 2024 onward. It gives relative susceptibility, not a probability, and it supports screening, not site decisions.

### 18.6 QGIS style test
This updates 16.3, which said QGIS was not installed and the style had never been opened.

QGIS 3.44.15 LTR is now installed. A script loaded all three zone maps in QGIS, applied `gis/styles/susceptibility_zones_v3.qml` and rendered them. The style loads, and all five classes show their labels and colours. No project analysis was done in QGIS. The script's exit crashed after the results were saved (DATA-046), and QGIS Desktop itself was not tested by hand.

To repeat the test and the report check:
```powershell
& "C:\Program Files\QGIS 3.44.15\bin\python-qgis-ltr.bat" scripts\phase5\verify\c7_qgis_style_test.py
& .\.venv\Scripts\python.exe scripts\phase5\verify\c6_check_verified_report.py
```


