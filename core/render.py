import math
import numpy as np
from numba import cuda

@cuda.jit
def mandelbrot_kernel(xmin,xmax,ymin,ymax,
                      img, max_iter, escape2):
    h,w = img.shape
    row,col = cuda.grid(2)
    if row>=h or col>=w: return
    x0 = xmin + (xmax-xmin)*col/w
    y0 = ymin + (ymax-ymin)*row/h
    x=y=0.0; it=0
    while x*x+y*y<=escape2 and it<max_iter:
        xt = x*x - y*y + x0
        y  = 2.0*x*y + y0
        x  = xt; it+=1
    img[row,col] = it

def cuda_render(xmin,xmax,ymin,ymax, W,H, max_iter, escape_radius):
    img_dev = cuda.device_array((H,W),dtype=np.uint16)
    tpb = (16,16)
    bpg = (math.ceil(H/tpb[0]), math.ceil(W/tpb[1]))
    mandelbrot_kernel[bpg, tpb](
       xmin,xmax,ymin,ymax,
       img_dev, np.uint16(max_iter), escape_radius*escape_radius
    )
    return img_dev.copy_to_host()
