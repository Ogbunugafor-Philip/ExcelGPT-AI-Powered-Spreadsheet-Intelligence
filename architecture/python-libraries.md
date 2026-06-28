# ExcelGPT — Python Libraries

Every backend dependency, the layer it serves, its role in ExcelGPT, and concrete Nigerian-market use cases. Versions are pinned in `backend/requirements.txt`.

---

## Web & API

### FastAPI
- **Layer:** Backend.
- **Role:** ASGI web framework exposing the five REST endpoints (`/upload`, `/analyse`, `/refine`, `/download/{token}`, `/health`). Provides automatic request/response validation via Pydantic and OpenAPI docs at `/docs`.
- **Example:** Validates an `AnalyseRequest` body and returns a typed `AnalyseResponse` for "rank branches by deposit growth".

### Uvicorn
- **Layer:** Backend (server).
- **Role:** Lightning-fast ASGI server that runs the FastAPI app in production behind Nginx, and with `--reload` in development.
- **Example:** `uvicorn main:app --port 8000` serving the Contabo VPS deployment.

### python-multipart
- **Layer:** Backend (ingest).
- **Role:** Parses `multipart/form-data` so FastAPI can accept Excel file uploads at `/upload`.
- **Example:** Receives a 12 MB branch-performance workbook from the React upload zone.

---

## Data intelligence & computation

### pandas
- **Layer:** Data intelligence + computation.
- **Role:** Reads all sheets of the uploaded workbook, builds the intelligence brief (types, null %, ranges, relationships), and executes grouping/aggregation/ranking/filtering/growth operations.
- **Example:** `df.groupby("lga")["deposits_ngn"].sum()` to total deposits by Local Government Area.

### numpy
- **Layer:** Computation.
- **Role:** Vectorized numerical primitives underpinning pandas operations and custom growth/score math.
- **Example:** Computing quarter-over-quarter growth arrays and weighted performance scores for FSO ranking.

### scipy
- **Layer:** Computation (statistics).
- **Role:** Correlation, hypothesis testing, and distribution analysis.
- **Example:** Pearson correlation between marketing spend and deposit growth across branches.

### statsmodels
- **Layer:** Computation (forecasting).
- **Role:** Time-series models (ARIMA/ETS) producing projections with confidence intervals for the forecast sheet.
- **Example:** Forecasting next quarter's loan disbursements with a 95% confidence band.

### scikit-learn
- **Layer:** Computation (ML).
- **Role:** Clustering (segmentation) and composite scoring/ranking models.
- **Example:** K-means clustering of sales territories into performance tiers; weighted scoring of DSAs against targets.

---

## Visualization & Excel generation

### matplotlib
- **Layer:** Computation → Excel generation.
- **Role:** Renders chart images (PNG) that openpyxl embeds into the Charts sheet.
- **Example:** A bar chart of deposit growth by branch saved to `UPLOAD_DIR` for embedding.

### seaborn
- **Layer:** Computation → Excel generation.
- **Role:** Statistical-chart styling on top of matplotlib for cleaner distribution/heatmap visuals.
- **Example:** A correlation heatmap of product uptake across LGAs.

### openpyxl
- **Layer:** Excel generation.
- **Role:** Builds the final multi-sheet `.xlsx`: executive summary, data, analysis, charts, forecast — applying NGN number formats, conditional formatting, KPI styling, embedded chart images, and the chosen formatting tier.
- **Example:** Writing the "Executive Summary" sheet with ₦-formatted KPI cards and an embedded growth chart.

---

## AI & configuration

### cerebras-cloud-sdk
- **Layer:** AI intent.
- **Role:** Client for the Cerebras Cloud API; sends the intelligence brief + instruction and returns the structured action plan (intent only).
- **Example:** Translating "show me underperforming branches and forecast recovery" into an action plan with `growth_analysis` + `forecast` operations.

### pydantic
- **Layer:** Cross-cutting (validation).
- **Role:** Defines and validates all schema models — API payloads, the Cerebras action plan, and the computation output — at every layer boundary.
- **Example:** Rejecting a malformed action plan where a `chart` operation targets a non-`charts` output sheet.

### python-dotenv
- **Layer:** Configuration.
- **Role:** Loads environment variables from `.env` into `config.py`.
- **Example:** Reading `CEREBRAS_API_KEY` and `MAX_FILE_SIZE_MB` at startup.

---

## Library → layer matrix

| Library | Frontend? | Data intel | AI intent | Computation | Excel gen |
|---------|:---------:|:----------:|:---------:|:-----------:|:---------:|
| FastAPI / Uvicorn / multipart | | ● (transport) | ● (transport) | ● (transport) | ● (transport) |
| pandas | | ● | | ● | |
| numpy | | | | ● | |
| scipy | | | | ● | |
| statsmodels | | | | ● | |
| scikit-learn | | | | ● | |
| matplotlib / seaborn | | | | ● | ● |
| openpyxl | | | | | ● |
| cerebras-cloud-sdk | | | ● | | |
| pydantic | | ● | ● | ● | ● |
| python-dotenv | | configuration (all layers) | | | |
