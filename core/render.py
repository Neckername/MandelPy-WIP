import importlib.util
import math
import os
import sys
import numpy as np

# Prefer NVIDIA's CUDA Python bindings when present; this avoids known
# initialization issues with some Windows driver/runtime combinations.
if importlib.util.find_spec("cuda") is not None:
    os.environ.setdefault("NUMBA_CUDA_USE_NVIDIA_BINDING", "1")

try:
    from numba import cuda
except Exception:
    cuda = None

_CUDA_DISABLED_REASON = None
_CUDA_SMOKE_TESTED = False

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
            return img_dev.copy_to_host()
        except Exception as exc:
            _disable_cuda(exc)

    return _cpu_render(
        xmin, xmax, ymin, ymax,
        W, H, max_iter, escape_radius
    )
