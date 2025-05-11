import math
import numpy as np
from numba import cuda

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

def cuda_render(xmin, xmax, ymin, ymax,
                W, H, max_iter: int, escape_radius: float):
    img_dev = cuda.device_array((H, W), dtype=np.uint32)   # was uint16
    tpb = (16, 16)
    bpg = (math.ceil(H / tpb[0]), math.ceil(W / tpb[1]))
    mandelbrot_kernel[bpg, tpb](
        xmin, xmax, ymin, ymax,
        img_dev,
        np.uint32(max_iter),                       # pass 32-bit value
        escape_radius * escape_radius
    )
    return img_dev.copy_to_host()
