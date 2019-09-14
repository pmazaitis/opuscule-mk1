
import sys
import os
sys.path.insert(0, os.path.abspath('..'))

import opuscule
import unittest


class TestOpusculeController(unittest.TestCase):
    """
    Test inputs to the opuscule controller for reasonable outputs
    """

    def test_handle(self):
        """
        Exercise command handler
        """
        result = opuscule.handle(1, 2)
        self.assertEqual(result, 3)

if __name__ == '__main__':
    unittest.main()