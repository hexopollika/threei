# 3i

3i (`threei`) is a napari-based workspace for inspecting FITS images and building cometary and astronomical image-processing views. It brings FITS layer handling, target center search, filtering, reconstruction, and observation overlays into one local desktop workflow. The current workflow is primarily focused on Hubble Space Telescope (HST) and Gemini/GMOS FITS data.

## What it does

- Opens FITS image data through a napari workflow.
- Provides layer-oriented processing for astronomical images.
- Includes Larson-Sekanina filtering.
- Includes Target MFSR, a drizzle-like target-aligned reconstruction workflow.
- Provides Core Search for target-center marking and per-layer center display state.
- Builds observation overlays for measurements, compass and direction annotations, image context, and display metadata.
- Includes an experimental MAGS mode inside the Larson-Sekanina tool.

## Status

3i is currently at `v1.0.0`. It is intended for local research and analysis workflows. This release stabilizes the current FITS, processing, Target MFSR, Core Search, and observation-overlay workflow.

## Getting started

3i is currently run as a local application from a Python environment with napari and the project dependencies installed.

### Conda recommended

```bash
git clone https://github.com/hexopollika/threei.git
cd threei
conda env create -f environment.yml
conda activate threei
python main.py
```

The conda environment installs the bundled FITS HDU napari plugin from `napari-fits-hdu`. This path is recommended for napari, Qt, and scientific-image dependencies.

### Pip alternative

Use this path only inside an existing Python 3.12 virtual environment. The conda path is recommended for most users.

```bash
git clone https://github.com/hexopollika/threei.git
cd threei
python -m pip install -U pip
python -m pip install -r requirements.txt
python main.py
```

Open a FITS file in napari, choose the relevant image layer, mark or confirm the target center with Core Search, then apply processing tools and observation overlays as needed.

## License

MIT License. See [LICENSE](LICENSE).
