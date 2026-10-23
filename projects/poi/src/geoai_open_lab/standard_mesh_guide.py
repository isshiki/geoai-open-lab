"""Introductory hierarchy helpers; Notebook 12's implementation is unchanged."""
from .regional_mesh import encode_mesh, mesh_bounds

LENGTHS = (4, 6, 8, 9, 10, 11)


def bounds(code):
    code = str(code)
    if len(code) not in LENGTHS or not code.isascii() or not code.isdigit():
        raise ValueError('Unsupported mesh code')
    if len(code) in (8, 9, 10):
        return mesh_bounds(code)
    if len(code) in (4, 6):
        w, s, _, _ = mesh_bounds(code.ljust(8, '0'))
        h, width = (2/3, 1) if len(code) == 4 else (1/12, 1/8)
        return w, s, w+width, s+h
    if code[-1] not in '1234':
        raise ValueError('Invalid quadrant')
    w, s, e, n = mesh_bounds(code[:-1]); q = int(code[-1])
    h, width = (n-s)/2, (e-w)/2
    return w+(q in (2, 4))*width, s+(q >= 3)*h, w+(1+(q in (2, 4)))*width, s+(1+(q >= 3))*h


def encode(latitude, longitude, digits=9):
    if digits not in LENGTHS:
        raise ValueError('Unsupported code length')
    if digits <= 10:
        return encode_mesh(latitude, longitude, max(8, digits))[:digits]
    base = encode_mesh(latitude, longitude, 10)
    # Same angular integer/tie convention as the established encoder.
    import math
    iy = math.floor(round(latitude*960, 9))
    ix = math.floor(round((longitude-100)*640, 9))
    return base + str(1+2*(iy % 2)+(ix % 2))


def parent(code):
    bounds(code)
    i = LENGTHS.index(len(code))
    return None if i == 0 else code[:LENGTHS[i-1]]


def children(code):
    bounds(code)
    if len(code) == 11:
        return []
    if len(code) in (4, 6):
        size = 8 if len(code) == 4 else 10
        return [code+str(y)+str(x) for y in range(size) for x in range(size)]
    return [code+str(q) for q in range(1, 5)]
