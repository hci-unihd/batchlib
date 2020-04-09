import os
from time import sleep

import h5py
try:
    import z5py
except ImportError:
    z5py = None

H5_EXTS = ['.h5', '.hdf', '.hdf5']
Z5_EXTS = ['.zr', '.zarr', '.n5']


def open_file(path, mode='r', h5_timeout=5, h5_retry=10):
    ext = os.path.splitext(path)[1]

    if ext.lower() in H5_EXTS:
        # this solves some h5 opening errors
        n_tries = 0
        while n_tries < h5_retry:
            try:
                return h5py.File(path, mode=mode)
            except OSError:
                sleep(h5_timeout)
                n_tries += 1

    elif ext.lower() in Z5_EXTS:
        if z5py is None:
            raise ValueError("Need z5py to load %s files" % ext)
        return z5py.File(path, mode=mode)

    raise ValueError("Invalid file extensions %s" % ext)


def write_viewer_attributes(ds, image, color, alpha=1., visible=True, skip=False):
    colors = ['Gray', 'Red', 'Green', 'Blue']
    color_maps = ['Glasbey']
    all_colors = colors + color_maps
    assert color in all_colors

    attrs = {'color': color, 'visible': visible, 'skip': skip, 'alpha': alpha}

    if color in colors:
        mi, ma = image.min(), image.max()
        attrs.update({'lutMinMax': [mi, ma]})

    ds.attrs.update(attrs)
