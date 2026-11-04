# Data Sources

## 1. Study Area Boundary
- **Source:** OpenStreetMap via Nominatim API
- **Provider:** OpenStreetMap Foundation
- **URL:** https://nominatim.openstreetmap.org
- **Citation:** © OpenStreetMap contributors. Data available under the Open Database License (ODbL).

## 2. Digital Elevation Model (DEM)
- **Source:** Copernicus DEM GLO-30 (Digital Surface Model)
- **Provider:** European Space Agency (ESA) / Copernicus Programme
- **Distribution:** AWS Open Data Registry (`s3://copernicus-dem-30m/`)
- **Resolution:** ~30m (1 arc-second)
- **Citation:** © DLR e.V. 2014-2018 and © Airbus Defence and Space GmbH 2020. Copernicus DEM — Global and European Digital Elevation Model. Distributed via AWS Open Data.
- **Derived Products:** Elevation, Slope (Horn's method), Aspect (Horn's method), Curvature (Zevenbergen-Thorne method).

## 3. Landslide Inventory
- **Source:** NASA Cooperative Open Online Landslide Repository (COOLR)
- **Provider:** NASA Goddard Space Flight Center
- **URL:** https://portal.nccs.nasa.gov/datashare/landslides/
- **Temporal Coverage:** 2007–2017 (for Mizoram subset)
- **Records:** 44 unique events within Mizoram
- **Citation:** Kirschbaum, D.B., Adler, R., Hong, Y., Hill, S., & Lerner-Lam, A. (2010). A global landslide catalog for hazard applications: method, results, and limitations. *Natural Hazards*, 52(3), 561-575. Juang, C.S., Stanley, T.A., & Kirschbaum, D.B. (2019). Using citizen science to expand the global map of landslides. *Frontiers in Earth Science*, 7, 65.

## 4. Geological Factors

### 4a. Active Faults
- **Source:** GEM Global Active Faults Database (GAF-DB)
- **Provider:** Global Earthquake Model (GEM) Foundation
- **URL:** https://github.com/cossatot/gem-global-active-faults
- **Records:** 6 faults within 50km buffer of Mizoram
- **Citation:** Styron, R. and Pagani, M. (2020). The GEM Global Active Faults Database. *Earthquake Spectra*, 36(S1), 203-222. DOI: 10.1177/8755293020944182

### 4b. Lithology
- **Source:** Macrostrat Geologic Map Database (tiny scale)
- **Provider:** Macrostrat / University of Wisconsin–Madison
- **URL:** https://macrostrat.org/api/v2/
- **Citation:** Peters, S.E., Husson, J.M., & Czaplewski, J. (2018). Macrostrat: A platform for geological data integration and deep-time Earth crust research. *Geochemistry, Geophysics, Geosystems*, 19(4), 1393-1409.

## 5. Land Use / Land Cover (LULC)
- **Source:** ESA WorldCover 2021 (v200)
- **Provider:** European Space Agency (ESA) via Microsoft Planetary Computer
- **URL:** https://planetarycomputer.microsoft.com/ (STAC catalog: `esa-worldcover`)
- **Native Resolution:** 10m (resampled to 30m using Nearest Neighbor)
- **Year:** 2021
- **Citation:** Zanaga, D., Van De Kerchove, R., Daems, D., De Keersmaecker, W., Brockmann, C., Kirches, G., ... & Arino, O. (2022). ESA WorldCover 10m 2021 v200. DOI: 10.5281/zenodo.7254221

## 6. Rainfall (Climatology)
- **Source:** CHIRPS v2.0 (Climate Hazards Group InfraRed Precipitation with Station data)
- **Provider:** Climate Hazards Center, University of California Santa Barbara
- **URL:** https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_monthly/tifs/
- **Native Resolution:** 0.05° (~5.5km) (resampled to 30m using Bilinear interpolation)
- **Temporal Coverage:** 2007–2017 monthly (132 months)
- **Derived Products:** Mean Annual Precipitation (MAP), Maximum Monthly Precipitation
- **Citation:** Funk, C., Peterson, P., Landsfeld, M., Pedreros, D., Verdin, J., Shukla, S., ... & Michaelsen, J. (2015). The climate hazards infrared precipitation with stations — a new environmental record for monitoring extremes. *Scientific Data*, 2, 150066. DOI: 10.1038/sdata.2015.66

---

## Sources added in Phase 2 (recorded retroactively on 2026-10-28)

## 7. GSI National Landslide Inventory
- **Source:** Geological Survey of India landslide inventory (as published on Bhukosh), GeoJSON mirror on the BharAtlas CDN
- **URL:** https://pub-0429b8e3b5a946e69ea007df844a6f1c.r2.dev/environment/gsi-landslide-inventory/GSI_Landslide_Inventory.geojson
- **Records:** 30,842 (India); 2,041 inside Mizoram (all points, no event dates); 55 attributes
- **Licence:** stated as CC0 in the download script comment — not independently verified
- **Underlying reports (examples from the CITATION field):** Patra, S. K. & Tushipokla (2018); Rinmuanpuii, P. & Jena, D. K. (2020); Limpou L. et al. (2016); Shome, P. & Kapfo, K. U. (2020); Patra, S. K. & Soraisam, C. (2017) — GSI Macro-scale (1:50,000) Landslide Susceptibility Mapping reports, Mizoram.
- **Also queried (no usable data):** NASA EONET API v3 (0 NE-India events), NASA GLC CSV on data.nasa.gov (download failed silently), NESDR/NESAC WFS (not reachable).

## Sources added in Phase 3 (2026-10-28)

## 8. OpenStreetMap roads and rivers
- **Source:** OpenStreetMap, Geofabrik extract "India — North-Eastern Zone", file `north-eastern-zone-261027.osm.pbf` (data of 2026-10-27)
- **URL:** https://download.geofabrik.de/asia/india/north-eastern-zone-latest.osm.pbf
- **Citation / licence:** © OpenStreetMap contributors, Open Database License (ODbL) 1.0; extract by Geofabrik GmbH.

## 9. SoilGrids 2.0
- **Source:** ISRIC — World Soil Information, SoilGrids 2.0 (clay, sand, bulk density; 30–60 cm; mean)
- **URL:** https://files.isric.org/soilgrids/latest/data/
- **Licence:** CC-BY 4.0
- **Citation:** Poggio, L., de Sousa, L. M., Batjes, N. H., Heuvelink, G. B. M., Kempen, B., Ribeiro, E., & Rossiter, D. (2021). SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty. *SOIL*, 7, 217–240. DOI: 10.5194/soil-7-217-2021

## 10. GLiM — Global Lithological Map (checked, not used: single class over Mizoram)
- **URL:** https://www.dropbox.com/s/9vuowtebp9f1iud/LiMW_GIS%202015.gdb.zip?dl=1
- **Citation:** Hartmann, J., & Moosdorf, N. (2012). The new global lithological map database GLiM: A representation of rock properties at the Earth surface. *Geochemistry, Geophysics, Geosystems*, 13(12), Q12004. DOI: 10.1029/2012GC004370

## 10b. Sentinel-2 L2A (NDVI, sensitivity test only)
- **Source:** Copernicus Sentinel-2 Level-2A, Microsoft Planetary Computer STAC, collection `sentinel-2-l2a`
- **URL:** https://planetarycomputer.microsoft.com/api/stac/v1
- **Period:** 2021-11-01 to 2022-01-20; scene IDs in `data/phase3/features/ndvi_summary.json`
- **Citation / licence:** Contains modified Copernicus Sentinel data 2021–2022 (ESA Copernicus open data terms).

## 11. Software and method references used in Phase 3
- **WhiteboxTools v2.4.0:** Lindsay, J. B. (2016). Whitebox GAT: A case study in geomorphometric analysis. *Computers & Geosciences*, 95, 75–84.
- **Depression filling:** Wang, L., & Liu, H. (2006). An efficient method for identifying and filling surface depressions in digital elevation models for hydrologic analysis and modelling. *International Journal of Geographical Information Science*, 20(2), 193–213.
- **Least-cost breaching (attempt 2):** Lindsay, J. B., & Dhun, K. (2015). Modelling surface drainage patterns in altered landscapes using LiDAR. *International Journal of Geographical Information Science*, 29(3), 397–411.
- **D-infinity flow routing:** Tarboton, D. G. (1997). A new method for the determination of flow directions and upslope areas in grid digital elevation models. *Water Resources Research*, 33(2), 309–319.
- **Stream Power Index:** Moore, I. D., Grayson, R. B., & Ladson, A. R. (1991). Digital terrain modelling: a review of hydrological, geomorphological, and biological applications. *Hydrological Processes*, 5(1), 3–30.
- **HAND:** Nobre, A. D., et al. (2011). Height Above the Nearest Drainage — a hydrologically relevant new terrain model. *Journal of Hydrology*, 404(1–2), 13–29.
- **Spatial cross-validation:** Roberts, D. R., et al. (2017). Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure. *Ecography*, 40(8), 913–929. — Brenning, A. (2012). Spatial cross-validation and bootstrap for the assessment of prediction rules in remote sensing: the R package sperrorest. *Proc. IEEE IGARSS 2012*, 5372–5375.
- **Sampling-bias correction (target-group background):** Phillips, S. J., Dudík, M., Elith, J., Graham, C. H., Lehmann, A., Leathwick, J., & Ferrier, S. (2009). Sample selection bias and presence-only distribution models: implications for background and pseudo-absence data. *Ecological Applications*, 19(1), 181–197.
- **Metrics under class imbalance:** Saito, T., & Rehmsmeier, M. (2015). The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. *PLoS ONE*, 10(3), e0118432. — Chicco, D., & Jurman, G. (2020). The advantages of the Matthews correlation coefficient (MCC) over F1 score and accuracy in binary classification evaluation. *BMC Genomics*, 21, 6.
- **Validation of susceptibility maps (success/prediction-rate curves, planned for DATA-028):** Chung, C.-J. F., & Fabbri, A. G. (2003). Validation of spatial prediction models for landslide hazard mapping. *Natural Hazards*, 30(3), 451–472.

- **Optuna:** Akiba, T., Sano, S., Yanase, T., Ohta, T., & Koyama, M. (2019). Optuna: a next-generation hyperparameter optimization framework. *Proc. KDD 2019*, 2623–2631.
- **LightGBM:** Ke, G., et al. (2017). LightGBM: a highly efficient gradient boosting decision tree. *Advances in Neural Information Processing Systems 30*, 3146–3154.
- **SHAP values:** Lundberg, S. M., & Lee, S.-I. (2017). A unified approach to interpreting model predictions. *Advances in Neural Information Processing Systems 30*, 4765–4774.

## 12. Governmental Portals Audited in Phase 4
- **GSI National Geoscience Data Repository (NGDR):** Geological Survey of India, Ministry of Mines, Government of India. URL: `https://geodataindia.gov.in`. Audited 2026-11-01 (DATA-032). Baseline 1:50,000 geology layers viewable in Bhu-Chayan Map Service Gateway; no open bulk shapefile export.
- **NRSC National Database for Emergency Management (NDEM):** National Remote Sensing Centre, Indian Space Research Organisation (ISRO). URL: `https://ndem.nrsc.gov.in`. Audited 2026-11-01 (DATA-033). Seasonal Landslide Inventory (2014, 2017, 2023, 2024) available as interactive map layer; vector geometries are view-only.
- **ISRO Landslide Atlas of India (2023):** National Remote Sensing Centre, ISRO, Hyderabad, India. URL: `https://www.isro.gov.in/media_isro/pdf/LandslideAtlas_2023.pdf`. Comprehensive national synthesis of satellite-derived landslide inventories.

**Correction to Section 12 (added 2026-11-01, DATA-035, DATA-037).** The NGDR entry above is wrong. NGDR does offer state-level vector downloads, in shapefile or GeoJSON, through its Baseline Data download panel and cart, with the link sent by email. See Section 13. The NDEM entry stands for the public site: its Downloads menu holds only apps and documents. The Atlas was not opened in Phase 4, so the secondary-source count of 12,385 Mizoram events remains unverified.

## 13. GSI data from the National Geoscience Data Repository (added 2026-11-01, DATA-037)

These four downloads apply to all the datasets below.

- **Source:** National Geoscience Data Repository (NGDR), Bhu-Chayan map gateway, Baseline Data download panel
- **URL:** https://geodataindia.gov.in (registered login required)
- **Provider:** Geological Survey of India, Ministry of Mines, Government of India; portal by BISAG-N
- **Version:** none given. The `edition_nu` field shows editions 0, 1 and 2 by map sheet
- **Publication date:** not stated in the download
- **Temporal resolution:** static maps, except the landslide points, which carry dates in the `history` field
- **Coverage:** State selection, MIZORAM
- **CRS:** EPSG:4326 as delivered
- **Format:** zipped ESRI Shapefile (GeoJSON was also offered)
- **Licence:** none shown during download. The portal displayed no terms in this flow, so check before any redistribution. Credit the Geological Survey of India
- **Downloaded:** 2026-11-01. The controls were operated in the author's signed-in session; GSI emailed each link, valid for 72 hours, to the author's account; the author saved the zips. SHA-256 values are in `data/phase4/logs/ngdr_download_manifest.csv`
- **Preprocessing:** none to the originals, which are kept in `data/raw/geology/ngdr/` and `data/raw/landslide_inventory/ngdr/`. Reprojected to EPSG:32646 when used

| Dataset | File | Scale | Records | Known limitations |
|---|---|---|---|---|
| Lithology | `LITHOLOGY_STATE_MIZORAM` | 1:50,000 | 357 polygons, 34 descriptions, 99.4 % of the state | 16.7 km2 of border sheets are unmapped. Descriptions are per map sheet, so similar rocks can be worded differently |
| Faults | `FAULT_STATE_MIZORAM` | 1:50,000 | 631 lines (627 fault or inferred, 4 thrust) | 233 are inferred |
| Shear zones | `SHEAR_ZONE_STATE_MIZORAM` | 1:50,000 | 47 lines | |
| Folds | `FOLD_STATE_MIZORAM` | 1:50,000 | 382 lines | Downloaded, not used |
| Lineaments | `LINEAMENT_250K_STATE_MIZORAM` | 1:250,000 | 192 lines (109 structural, 83 geomorphic) | Coarser scale |
| Geomorphology | `GEOMORPHOLOGY_250K_STATE_MIZORAM` | 1:250,000 | 297 polygons | Downloaded, not used |
| Landslide points | `LANDSLIDE_POINT_STATE_MIZORAM` | Field records | 3,373 points, 3,372 inside Mizoram; 1,803 with a year | A later, larger release of the survey used for training. Has a `geology` attribute, which must never be a feature |
| Landslide polygons | `LANDSLIDE_POLYGON_STATE_MIZORAM` | Not stated | 4,256 polygons: 1,774 "Mapped as polygon", 1,058 "Mapped as point bufferred to polygon", 1,424 blank | The mapping method and date are not given. Not an NRSC product. Median area about 150 m2, below one 30 m cell |

Also available on NGDR and not downloaded: Geology 25k and 2M, Tectonic, Seismotectonic, and NLSM, which needs the Draw tab and one susceptibility layer at a time.

---

## 14. Phase 5 Datasets, Deliverables & Comprehensive Provenance Audit (added 2026-11-01)

This section provides the exhaustive four-pillar audit (**Where it comes from**, **Why it was used**, **How it was processed**, and **What it means**) for the final Phase 5 deliverables and the complete multi-source geospatial inventory.

### 14.1 Phase 5 Derived Datasets & Models

#### A. Final Modeling Matrix v5 (`data/phase5/modeling/FINAL_DATASET_v5.csv`)
- **Where it comes from:** Compiled via `scripts/phase5/01_build_dataset_v5.py`. Merged 13,013 preserved rows from Phase 3 (`FINAL_DATASET_v3.csv`) with 1,434 GSI mapped polygon scars (`data/raw/landslide_inventory/ngdr/`) and 1,434 random negatives (`neg_random_v5`, seed 42).
- **Why:** Incorporating 1,434 mapped polygons exposes the machine learning pipeline to wilderness, non-roadside slope failures, eliminating the roadside survey bias of the historical GSI point survey.
- **How:** Polygons filtered to `data_type == "Mapped as polygon"`, deduplicated by centroid coordinates, restricted to $>150\text{ m}$ from all GSI training points, and sampled across 21 natural terrain factors via affine transformation indexing. Negatives drawn uniformly across all slope strata outside the 150 m morphological dilation buffer.
- **What it means:** 15,881 total observations (42 columns) representing the most complete, leak-free, multi-source landslide modeling database in Northeast India.

#### B. Full-State Continuous Susceptibility Raster v5 (`data/final/mizoram_landslide_susceptibility_v5_natural.tif`)
- **Where it comes from:** Inferred via `scripts/phase5/04_predict_map_v5.py` using `models/phase5/final_natural_v5.pkl` (XGBoost classifier tuned across 25 Optuna trials).
- **Why:** Delivers an objective, state-wide continuous spatial hazard probability surface $P(Y=1 \mid \mathbf{X})$ governed purely by natural terrain geomorphology, hydrology, and climatology.
- **How:** Windowed raster inference ($1024 \times 1024$ streaming blocks) executed over all 22,918,792 terrestrial pixels in the 30.3 m UTM Zone 46N grid.
- **What it means:** File size 74.4 MB, values spanning $[0.0159, 0.9843]$ (mean 0.3204, SD 0.1742). Master grid dimensions (9,437 rows $\times$ 4,685 columns) and metadata exactly match the Copernicus DEM master profile.

#### C. Five-Class Hazard Zonation Raster v5 (`data/final/mizoram_landslide_zones_v5_natural.tif`)
- **Where it comes from:** Classified via `scripts/phase5/05_evaluate_map_v5.py` on 1,000,000 random land cells using the Jenks Natural Breaks optimization algorithm.
- **Why:** Operational civil protection and disaster response planning require discrete, legally defensible hazard classes rather than continuous probabilities.
- **How:** Objective function minimizes intra-class variance and maximizes inter-class variance:
  $$\text{GVF} = 1 - \frac{\sum_{k=1}^5 \sum_{i \in C_k} (x_i - \bar{x}_k)^2}{\sum_{i=1}^N (x_i - \bar{x})^2}$$
  - Class 1 (Very Low): $< 0.1748$ (29.13% land area; Frequency Ratio = 0.005)
  - Class 2 (Low): $0.1748 – 0.3065$ (28.57% land area; Frequency Ratio = 0.11)
  - Class 3 (Moderate): $0.3065 – 0.4618$ (21.25% land area; Frequency Ratio = 0.42)
  - Class 4 (High): $0.4618 – 0.6632$ (13.51% land area; Frequency Ratio = 1.55)
  - Class 5 (Very High): $\ge 0.6632$ (7.55% land area; Frequency Ratio = 8.85)
- **What it means:** The top two hazard zones (High + Very High, covering 21.06% of Mizoram) encompass **87.82%** of all historical landslide occurrences, confirming world-class hazard concentration.

---

### 14.2 Master Geospatial Inventory Provenance Table

| # | Dataset / Product | Where it comes from (Provider, URL, Sensor) | Why it was selected | How it was processed & harmonized | What it means & Limitations |
|---|---|---|---|---|---|
| **1** | **Copernicus DEM GLO-30** | European Space Agency (ESA) via AWS Registry (`s3://copernicus-dem-30m/`) | 30 m spatial resolution Digital Surface Model providing foundational elevation | 8 tiles mosaicked, 5 km edge padded, clipped to boundary, reprojected to EPSG:32646 | Baseline topography; captures surface canopy rather than bare-earth LiDAR |
| **2** | **GSI NLSM Point Inventory** | Geological Survey of India via BharAtlas mirror (`pub-0429b8e3b5a946e69ea007df844a6f1c.r2.dev`) | Official 1:50,000 field surveys (2014–2020) across Mizoram | Deduplicated coordinates, clipped to boundary; exactly 1,859 unique 30.3 m pixels retained | Ground truth for roadside landslides; 76% within 60 m of roads |
| **3** | **GSI NGDR Mapped Polygons** | GSI National Geoscience Data Repository (`geodataindia.gov.in`) | Unseen field polygons (2024 release) providing natural wilderness failures | Filtered to `Mapped as polygon`, deduplicated, checked $>150\text{ m}$ from points (1,434 pixels) | Independent validation & augmentation; mapping sensor and date unspecified |
| **4** | **NASA COOLR Inventory** | NASA Goddard Space Flight Center (`portal.nccs.nasa.gov`) | Global benchmark inventory (2007–2017) | 44 points filtered within Mizoram boundary | Historical global events; coarse spatial precision (~1 km to 5 km) |
| **5** | **OSM Roads & Rivers** | OpenStreetMap via Geofabrik (`download.geofabrik.de`) | Captures human cut-slope destabilization and hydrological toe undercutting | Vector lines rasterized; Euclidean Distance Transform computed via `scipy.ndimage` | 14,147 km roads, 12,854 km streams; road distance alone scores 0.920 AUC |
| **6** | **SoilGrids 2.0** | ISRIC — World Soil Information (`files.isric.org`) | Quantifies geotechnical shear strength via clay, sand, and bulk density | 250 m rasters reprojected, bilinear resampled to 30.3 m, median imputation for 57 border cells | Regional pedological trends; lacks micro-scale regolith weathering depth |
| **7** | **CHIRPS v2.0 Climatology** | Climate Hazards Center, UCSB (`data.chc.ucsb.edu`) | 43-year quasi-global precipitation record (0.05° resolution) | 132 monthly grids averaged into MAP and Max Monthly Rain; bilinear resampled to 30.3 m | Explains orographic rainfall triggers; lacks hourly rainstorm bursts |
| **8** | **GEM Active Faults** | Global Earthquake Model Foundation (`github.com/cossatot`) | Structural shearing and fault fracture zones that weaken bedrock | 6 fault traces buffered to 50 km; metric Euclidean Distance Transform calculated | Identifies regional tectonic corridors; does not reflect local joint spacing |
| **9** | **GSI NGDR 1:50,000 Geology** | GSI National Geoscience Data Repository (`geodataindia.gov.in`) | Authoritative national bedrock mapping across 357 polygons | Grouped into 7 lithological units from map descriptions; tested under Rule A6 | Evaluated and rejected from model: delta $-0.0006$ AUC (signal already carried by terrain) |
| **10** | **ESA WorldCover 2021** | ESA via Microsoft Planetary Computer STAC | 10 m high-resolution land cover from Sentinel-1 and Sentinel-2 | Nearest-neighbor downscaled to 30.3 m grid; 7 discrete classes | Used in All-Factor model; excluded from Natural model to prevent post-failure bias |
| **11** | **Sentinel-2 L2A (NDVI)** | Copernicus Sentinel-2 via Planetary Computer STAC | Sensitivity test for vegetation density | 48 cloud-free dry-season scenes composited into median NDVI | Tested in `FINAL_DATASET_v3_ndvi.csv`; omitted from production to avoid post-failure leakage |

---
*End of Data Sources and Provenance Audit.*

---

## 15. Correction to Section 14 (added 2026-11-01, DATA-044)

**Do not rely on Section 14 without these corrections.** Section 14 stays as written. Sections 1 to 13 are unaffected.

- **Grid:** 9,437 rows × 3,959 columns, not 4,685.
- **Mapped polygons:** the mapping method and date are not stated. "Field polygons", "2024 release" and "wilderness" have no support. These polygons do not eliminate road bias, and they have their own biases: 90.8 % lie in 3 map sheets and only 1.9 % face north (DATA-045).
- **FINAL_DATASET_v5.csv:** "leak-free" and "most complete in Northeast India" have no support.
- **Maps:** values are relative scores, not P(Y=1 given X). They are not calibrated, official or legally defensible.
- **Zones:** natural breaks from 1-D k-means. Frequency ratios of 8.85 and "87.82 %" come from training landslides.
- **DEM:** 8 tiles with a 10 km margin in Phase 3.
- **CHIRPS:** this project used 2007 to 2017, 132 months.
- **WorldCover:** check `lulc_codes` in `models/phase3/feature_list.json`, which lists 8 codes.
- **Licences:** only those in Sections 1 to 13 are recorded. NGDR's licence is not stated.


