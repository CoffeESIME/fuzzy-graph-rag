# GraphRAG Multimodal - Implementation Walkthrough

## 📅 Project Timeline

| Phase | Component | Status | Description |
|-------|-----------|--------|-------------|
| **Phase 1** | Streamlit Admin | ✅ Done | File Ingestion, Grouping, Task Management |
| **Phase 2** | React Search App | ✅ Done | User-facing Search, Multimedia Previews, Modal Reader |
| **Phase 3** | Graph Visualization | 🔄 Planned | Node interactions, D3/Neo4j integration |

---

## 🏗️ Phase 2: React Search App (New!)

### 🎯 Objective
Create a modern, responsive user interface for **searching** the multimodal knowledge base, separating the "Admin/Ingest" role (Streamlit) from the "End User/Search" role (React).

### 📦 Key Components (`search-app/`)

#### 1. Tech Stack
- **Vite + React 19 + TypeScript**: High-performance SPA.
- **Tailwind CSS v4**: Modern styling with dark mode default.
- **Zustand**: Lightweight global state management.
- **TanStack Query**: Efficient async data fetching and caching.

#### 2. Features Built
- **Semantic Text Tab:**
  - Real-time querying to `POST /search/vectors`.
  - **Space Filtering:** Toggle between Text, Visual, Audio, and Memory spaces.
  - **Result Grid:** Responsive grid layout for multimedia results.

- **Multimedia Previews (`MediaPreview.tsx`):**
  - **Images:** Securely loaded via Presigned URLs (MinIO).
  - **Audio:** Custom HTML5 player with metadata badges (Genre, Tempo).
  - **Text/Memory:** "View Full Text" modal for reading document content inline.
  - **Video:** Native video player support.

- **Direct MinIO Integration:**
  - Backend bypasses unstable SQL paths -> Uses **Hash-Search** in MinIO.
  - Generates **1-hour Signed URLs** for secure browser access.
  - Handles `raw/` assets and `processed/` text files unifiedly.

#### 3. State Management
- **SearchStore:**
  - `query`: Current user search string.
  - `selectedSpaces`: Active filters (default: all).
  - `results`: Array of `VectorSearchResult`.
  - `isSearching`: Loading state.

### 📐 Architecture Update
The system now runs **Hybrid Frontend**:
- **Port 8501 (Streamlit):** Admin Panel for Ingest & Tasks.
- **Port 5173 (Vite):** Search Interface for Users.
- **Port 8000 (FastAPI):** Unified Backend serving both.

---

## 🏗️ Phase 1: Streamlit Admin (Legacy/Backend Control)

### 🎯 Objective
Create a Streamlit application that serves as the user interface for the GraphRAG Multimodal system ingestion.

*(See previous documentation for Phase 1 details)*

### 📦 Deliverables
- **app.py** - Main Streamlit application
- **Tab 1: Ingesta y Agrupación**
- **Tab 2: Control de Tareas**

---

## 🚀 How to Run the Full Stack

### 1. Backend (Core)
```bash
cd backend
poetry run uvicorn app:app --port 8000 --reload
```

### 2. Search App (User UI)
```bash
cd search-app
npm run dev
# -> http://localhost:5173/search
```

### 3. Admin Panel (Ingest UI)
```bash
cd frontend
streamlit run app.py
# -> http://localhost:8501
```

---

## 🧪 Verification Steps (Phase 2)

1. **Start Backend & Search App.**
2. **Go to Semántica Tab.**
3. **Type "gato"** (assuming you ingested cat images).
4. **Verify Results:**
   - Should see images of cats.
   - Should see badges e.g., "VisualSpace".
   - Images should load (check Console for 403/404 if not).
5. **Click Text Result:**
   - Modal should open with full text content.
