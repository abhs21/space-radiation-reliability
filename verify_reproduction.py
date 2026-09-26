"""Compare report structure exactly and floating-point results within roundoff."""
import argparse
import json
import math
from pathlib import Path


def verify(expected, actual, path='$'):
    if type(expected) is not type(actual):
        raise ValueError(f'{path}: value type changed')
    if isinstance(expected, dict):
        if expected.keys() != actual.keys():
            raise ValueError(f'{path}: keys changed')
        for key in expected:
            verify(expected[key], actual[key], f'{path}.{key}')
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            raise ValueError(f'{path}: list length changed')
        for i, (left, right) in enumerate(zip(expected, actual)):
            verify(left, right, f'{path}[{i}]')
    elif isinstance(expected, float):
        if not (math.isfinite(expected) and math.isfinite(actual) and
                math.isclose(expected, actual, rel_tol=1e-12, abs_tol=1e-12)):
            raise ValueError(f'{path}: floating-point result changed: {expected} vs {actual}')
    elif expected != actual:
        raise ValueError(f'{path}: value changed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('expected', type=Path)
    parser.add_argument('actual', type=Path)
    args = parser.parse_args()
    verify(json.loads(args.expected.read_text()), json.loads(args.actual.read_text()))
    print('Reproduced: structure, integers, strings and hashes exact; finite floats within 1e-12 relative/absolute tolerance.')


if __name__ == '__main__':
    main()
