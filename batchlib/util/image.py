import numpy as np


def standardize(input_, eps=1e-6):
    mean = np.mean(input_)
    std = np.std(input_)
    return (input_ - mean) / np.clip(std, a_min=eps, a_max=None)


def normalize(input_, eps=1e-6):
    input_ = input_.astype(np.float32)
    input_ -= input_.min()
    input_ /= (input_.max() + eps)
    return input_


def barrel_correction(image, barrel_corrector, offset=550):
    if image.shape != barrel_corrector.shape:
        raise ValueError(f'Shape mismatch: {image.shape} != {barrel_corrector.shape}')
    # cast back to uint16 to keep the same datatype
    corrected = ((image - offset) / barrel_corrector).astype(image.dtype)
    return corrected
