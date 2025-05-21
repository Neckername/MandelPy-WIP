<h1 align="left" id="title">Documentation:</h1>

<p align="center"><img src="https://socialify.git.ci/Neckername/MandelPy-WIP/image?custom_description=CUDA-accelerated+Mandelbrot+explorer+with+smooth+zoom%2C+real-time+render%2C+custom+gradients+%26+a+sleek+PySide6+GUI.&amp;description=1&amp;font=Jost&amp;forks=1&amp;issues=1&amp;language=1&amp;logo=https%3A%2F%2Fraw.githubusercontent.com%2FNeckername%2FMandelPy-WIP%2Frefs%2Fheads%2Fmain%2Fassets%2Flogo.svg&amp;name=1&amp;owner=1&amp;pattern=Formal+Invitation&amp;pulls=1&amp;stargazers=1&amp;theme=Dark" alt="project-image"></p>

<h2>Project Screenshots:</h2>

<img src="https://github.com/Neckername/MandelPy-WIP/blob/main/assets/screenshots/MandelPyCollage1.png?raw=true" alt="project-screenshot" width="1000" height="754/">

  
  
<h2>🧐 Features</h2>

Here're some of the project's best features:

*   ⚡ GPU acceleration – Numba‐CUDA kernel renders millions of pixels/iteration on the GPU; >100 FPS is common on mid-range cards.
*   🖱️ Smooth navigation – scroll-wheel zoom click-and-drag pan quick reset plus numeric controls for exact coordinates & magnification.
*   🎨 Gradient editor – add / remove colour stops drag to reorder sample colours preview in real time and save/load JSON “.grd” presets.
*   🗺️ Focal map – thumbnail of the full set with a cross-hair showing your current viewport; great for never losing your bearings.
*   💾 Quick-save / Save-as – export high-resolution PNG snapshots of the current view or store (.json) sessions containing viewport + gradient.
*   ⚙️ Preferences dialog – pick default quality output folder UI scale … persisted in a tiny JSON file in your user config directory.
*   📦 Zero C/C++ build steps – pure Python + wheels from PyPI.

<h2>🛠️ Installation Steps:</h2>

<p>1. Create a virtual environment (optional but recommended)</p>

```
python -m venv venv
```

<p>2. Activate virtual environment (skip to step 4 if running without venv)</p>

```
source venv/bin/activate
```

<p>3. To activate on Windows</p>

```
source venv\Scripts\activate
```

<p>4. Install dependencies</p>

```
pip install -r requirements.txt
```

<p>5. Run MandelPy</p>

```
python main.py
```

<h2>🍰 Contribution Guidelines:</h2>

Refer to CONTRIBUTING.md and our CODE\_OF\_CONDUCT.md for more info.

<h2>🛡️ License:</h2>

This project is licensed under the MandelPy is released under the MIT License – see MIT License.
