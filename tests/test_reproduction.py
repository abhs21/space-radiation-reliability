import unittest
from verify_reproduction import verify


class ReproductionTests(unittest.TestCase):
    def test_observed_roundoff_is_allowed(self):
        verify({'value':262.5257620730822, 'count':18, 'hash':'abc'},
               {'value':262.525762073082, 'count':18, 'hash':'abc'})

    def test_material_or_structural_changes_fail(self):
        for expected, actual in ((1.0, 1.00001), (18, 19), ('abc', 'abd'),
                                 ({'a':1}, {'b':1}), ([1], [1,2]),
                                 (1.0, float('nan')), (1, 1.0), (False, 0)):
            with self.subTest(expected=expected, actual=actual):
                with self.assertRaises(ValueError):
                    verify(expected, actual)
