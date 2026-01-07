#!/usr/bin/env python3


def roundf(n, precision):
    return "{:.{precision}f}".format(float(n), precision=precision)
