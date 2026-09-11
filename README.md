<div align="right">
  <b>English | <a href="README.jp.md">日本語</a></b>
</div>

# Antigravity Filer - Photo & File Manager (Blur, Burst & Similar Photo Organizer)

Antigravity Filer is a modern GUI file manager application built with Python (**PySide6**).
In addition to standard file management features, it integrates advanced computer vision and image processing capabilities (**OpenCV**, **PIL**, and **dHash perceptual hashing**) to detect blurry photos, group continuous burst shots, find duplicate/similar photos, and organize unwanted files into the trash with a single click.

Analyzed hashes, EXIF timestamps, and focus sharpness scores are **persisted in an SQLite cache**, making subsequent scans and application restarts lightning fast.

---

## 📂 Project Structure

```
DetectionOfJunkPhotos/
├── i18n.py                # Internationalization module (Dynamic English/Japanese switching & persistence)
├── BaseNodeObject.py      # Data models (Node hierarchy, icons, formatters, metadata)
├── FilerRepository.py     # Repository layer (File system operations, trash management, search pipelines)
├── HashCacheManager.py    # Persistent cache manager (SQLite3 for dHash, EXIF timestamp & sharpness scores)
├── BlurDetector.py        # Focus/Sharpness & Blur detection engine (Laplacian variance, grid analysis, face cascade)
├── BlurSearchDialog.py    # Blurry photo search dialog
├── BurstPhotoManager.py   # Burst photo extraction & focus ranking engine (EXIF sub-second priority / mtime fallback)
├── BurstPhotoDialog.py    # Burst photo comparison & cleanup dialog
├── SimilarPhotoManager.py # Visual similarity clustering engine (64-bit dHash & Hamming distance)
├── SimilarPhotoDialog.py  # Similar photo comparison & cleanup dialog
├── main.py                # GUI main window (PySide6)
├── README.md              # English documentation
└── README.jp.md           # Japanese documentation
```

---

## 🌟 Key Features

### 1. 🌐 Bilingual Support (English / Japanese)
- Seamlessly toggle between **English** and **日本語** from the top navigation bar.
- Selected language is persisted across application restarts.
- Real-time UI and dialog localization across all windows, menus, and inspector panels.

### 2. 📁 Comprehensive File Management
- **Navigation**: Back, Forward, Up to parent directory, Refresh, and direct editable path bar.
- **File List Table**: Accurate numeric sorting for file sizes and modification timestamps, multi-selection, and instant text filtering.
- **Context Menus**: Open with default app, rename, move to OS trash / permanently delete, create new folders and text files.
- **Sidebar Shortcuts**: Quick access to Home, Pictures, Documents, Downloads, Desktop, and Root.

### 3. ⚡ SQLite Persistent Cache (`HashCacheManager`)
- Scanned image metadata, **perceptual hashes (dHash)**, **EXIF capture timestamps**, and **sharpness scores** are stored in `~/.cache/PhotoIsOutOfFocus/image_cache.db`.
- Repeated scans skip heavy image decoding and Laplacian calculations for instant results.
- Automatically invalidates and recalculates when file modification time (`mtime`) or file size changes.

### 4. 🔍 Blurry Photo Search (`BlurDetector` / `BlurSearchDialog`)
- Automated sharpness measurement using **Laplacian Variance**.
- **Haar Cascade Face Detection**: Prioritizes facial focus in portrait photos so that intentional background blur (bokeh) is not falsely flagged.
- **Grid Sharpness Evaluation**: Divides images into a 5x5 grid to evaluate focused subjects accurately even with shallow depth of field.

### 5. 📸 Burst Photo Organization (`BurstPhotoManager` / `BurstPhotoDialog`)
- **EXIF Timestamp Analysis**: Extracts EXIF `DateTimeOriginal` and `SubSecTimeOriginal` (falling back to `mtime` if unavailable) to group photos captured within a configurable interval (default: <= 3.0s).
- **Auto-Keep Best Shot**: Automatically marks the sharpest image as `🟢 Keep (Recommended)` and others as `🗑️ Delete Candidate`.
- **Card Preview & Zoom**: High-resolution side-by-side cards with double-click / button zoom preview.
- **Safe Batch Trash**: Moves unwanted candidates directly to the OS Trash (recoverable).

### 6. 🖼️ Similar Photo Clustering (`SimilarPhotoManager` / `SimilarPhotoDialog`)
- **Perceptual Difference Hashing (64-bit dHash)**: Computes image structural hash independent of file timestamps to detect similar compositions and poses.
- **Hamming Distance Clustering**: Groups photos with configurable bit difference tolerances (1-30 bits).
- **Auto-Select Best Photo**: Automatically recommends keeping the crispest version in each cluster.

---

## 🛠️ Architecture & Design

- **Decoupled Architecture**: Clean separation between UI layers (`PySide6`), repository abstractions (`FilerRepository`), and domain algorithms (`BlurDetector`, `BurstPhotoManager`, `SimilarPhotoManager`).
- **Cross-Platform Compatibility**: Fully compatible across Linux, Windows, and macOS (with native trash support via `send2trash` and `gio`).

---

## 🚀 Setup & Execution

### Prerequisites & Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/amekusa03/DetectionOfJunkPhotos.git
   cd DetectionOfJunkPhotos
   ```

2. **Install dependencies:**
   ```bash
   pip install PySide6 opencv-python pillow numpy send2trash
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

---

## 📝 License

This project is licensed under the MIT License.
