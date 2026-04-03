import matplotlib
matplotlib.use('Agg')   # non-interactive backend — must be before any pyplot import

import sys
import os
# Add analysis/ to sys.path so 'acoustic' and 'power_budget' are importable as packages
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
