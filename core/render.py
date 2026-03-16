import importlib
import importlib.abc
import importlib.util
import math
import os
import pathlib
import sys
import numpy as np

class _NumbaCudaFinder(importlib.abc.MetaPathFinder):
    """Redirect `numba.cuda.*` imports to `numba_cuda/numba/cuda/*` when available."""

    def __init__(self):
        self.initialized = None

    def ensure_initialized(self) -> bool:
        if self.initialized is not None:
            return self.initialized

        numba_spec = importlib.util.find_spec("numba")
        numba_cuda_spec = importlib.util.find_spec("numba_cuda")
        if numba_spec is None or numba_cuda_spec is None:
            self.initialized = False
            return False

        numba_locs = numba_spec.submodule_search_locations
        numba_cuda_locs = numba_cuda_spec.submodule_search_locations
        if not numba_locs or len(numba_locs) != 1:
            self.initialized = False
            return False
        if not numba_cuda_locs or len(numba_cuda_locs) != 1:
            self.initialized = False
            return False

        self.numba_path = str(pathlib.Path(numba_locs[0]))
        self.numba_cuda_path = str(pathlib.Path(numba_cuda_locs[0]) / "numba")
        self.initialized = True
        return True

    def find_spec(self, name, path, target=None):
        if "numba.cuda" not in name or path is None:
            return None
        if not self.ensure_initialized():
            return None

        if any(self.numba_cuda_path in p for p in path):
            return None

        redirected = [p.replace(self.numba_path, self.numba_cuda_path) for p in path]
        for finder in sys.meta_path:
            if finder is self:
                continue
            find_spec = getattr(finder, "find_spec", None)
            if find_spec is None:
                continue
            spec = find_spec(name, redirected, target)
            if spec is not None:
                return spec
        return None


if not any(isinstance(f, _NumbaCudaFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _NumbaCudaFinder())

# Prefer NVIDIA's CUDA Python bindings only when the legacy entrypoint
# (`cuda.cuda`) exists; otherwise keep numba's default binding path.
_requested_nvidia_binding = importlib.util.find_spec("cuda.cuda") is not None
if _requested_nvidia_binding:
    os.environ.setdefault("NUMBA_CUDA_USE_NVIDIA_BINDING", "1")

try:
    from numba import cuda
    _CUDA_IMPORT_ERROR = None
except Exception as first_exc:
    cuda = None
    _CUDA_IMPORT_ERROR = str(first_exc)
    if _requested_nvidia_binding:
        os.environ.pop("NUMBA_CUDA_USE_NVIDIA_BINDING", None)
        try:
            from numba import cuda
            _CUDA_IMPORT_ERROR = None
        except Exception as second_exc:
            cuda = None
            _CUDA_IMPORT_ERROR = f"{first_exc}; fallback import failed: {second_exc}"

_CUDA_DISABLED_REASON = None
_CUDA_SMOKE_TESTED = False
_LAST_RENDER_BACKEND = "CPU"
_LAST_RENDER_REASON = "CUDA not initialized."

if cuda is not None:
    @cuda.jit
    def mandelbrot_kernel(xmin,xmax,ymin,ymax,
                          img, max_iter, escape2):
        h,w = img.shape
        row,col = cuda.grid(2)
        if row>=h or col>=w: return
        x0 = np.float64(xmin) + (np.float64(xmax) - xmin) * col / w
        y0 = np.float64(ymin) + (np.float64(ymax) - ymin) * row / h
        x = y = np.float64(0.0)
        it = 0
        while x*x+y*y<=escape2 and it<max_iter:
            x, y = x*x - y*y + x0, 2.0*x*y + y0
            it += 1
        if it < max_iter:
            log_zn  = math.log(x*x + y*y) / 2.0
            nu      = math.log(log_zn / math.log(2.0)) / math.log(2.0)
            it = it + 1 - nu
        img[row,col] = it

def _disable_cuda(exc: Exception):
    global _CUDA_DISABLED_REASON
    if _CUDA_DISABLED_REASON is None:
        _CUDA_DISABLED_REASON = str(exc)
        print(
            "[MandelPy render] CUDA unavailable; using CPU renderer.",
            file=sys.stderr
        )

def get_renderer_state() -> tuple[str, str | None]:
    return _LAST_RENDER_BACKEND, _LAST_RENDER_REASON

def _cuda_ready() -> bool:
    global _CUDA_SMOKE_TESTED
    if cuda is None:
        return False
    if _CUDA_DISABLED_REASON is not None:
        return False
    try:
        if not cuda.is_available():
            return False
        if not _CUDA_SMOKE_TESTED:
            probe = np.zeros(1, dtype=np.float32)
            dev = cuda.to_device(probe)
            dev.copy_to_host()
            cuda.synchronize()
            _CUDA_SMOKE_TESTED = True
        return True
    except Exception as exc:
        _disable_cuda(exc)
        return False

def _cpu_render(xmin, xmax, ymin, ymax,
                W, H, max_iter: int, escape_radius: float):
    xs = np.linspace(xmin, xmax, W, dtype=np.float64)
    ys = np.linspace(ymin, ymax, H, dtype=np.float64)
    c = xs[None, :] + 1j * ys[:, None]
    z = np.zeros_like(c, dtype=np.complex128)

    iters = np.full((H, W), float(max_iter), dtype=np.float64)
    active = np.ones((H, W), dtype=bool)
    escape2 = float(escape_radius * escape_radius)
    log2 = math.log(2.0)

    for i in range(max_iter):
        z[active] = z[active] * z[active] + c[active]
        mag2 = z.real * z.real + z.imag * z.imag
        escaped = active & (mag2 > escape2)
        if np.any(escaped):
            log_zn = np.log(mag2[escaped]) / 2.0
            nu = np.log(log_zn / log2) / log2
            iters[escaped] = i + 1 - nu
            active[escaped] = False
        if not np.any(active):
            break

    return iters.astype(np.float32)

def cuda_render(xmin, xmax, ymin, ymax,
                W, H, max_iter: int, escape_radius: float):
    global _LAST_RENDER_BACKEND, _LAST_RENDER_REASON
    if _cuda_ready():
        try:
            img_dev = cuda.device_array((H, W), dtype=np.float32)
            tpb = (16, 16)
            bpg = (math.ceil(H / tpb[0]), math.ceil(W / tpb[1]))
            mandelbrot_kernel[bpg, tpb](
                xmin, xmax, ymin, ymax,
                img_dev,
                np.int32(max_iter),
                escape_radius * escape_radius
            )
            _LAST_RENDER_BACKEND = "CUDA"
            _LAST_RENDER_REASON = None
            return img_dev.copy_to_host()
        except Exception as exc:
            _disable_cuda(exc)

    _LAST_RENDER_BACKEND = "CPU"
    if cuda is None:
        if _CUDA_IMPORT_ERROR:
            _LAST_RENDER_REASON = f"numba.cuda import failed: {_CUDA_IMPORT_ERROR}"
        else:
            _LAST_RENDER_REASON = "numba.cuda could not be imported."
    elif _CUDA_DISABLED_REASON:
        _LAST_RENDER_REASON = _CUDA_DISABLED_REASON
    else:
        _LAST_RENDER_REASON = "cuda.is_available() returned False."
    return _cpu_render(
        xmin, xmax, ymin, ymax,
        W, H, max_iter, escape_radius
    )
