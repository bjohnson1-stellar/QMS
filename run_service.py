"""QMS Windows Service launcher — used by nssm.

Sets sys.path so the qms package and its dependencies are importable
when running as the SYSTEM service account (which can't see user
site-packages). Then starts Waitress.
"""
import sys

# Package root parent (so `import qms` finds D:\qms\)
sys.path.insert(0, "D:\\")
# User site-packages (Flask, Waitress, and all pip-installed deps)
sys.path.insert(0, r"C:\Users\bjohnson1\AppData\Roaming\Python\Python312\site-packages")

from qms.api import create_app
from waitress import serve

app = create_app()
print("Starting QMS Waitress server on 0.0.0.0:5000 (8 threads)")
serve(app, host="0.0.0.0", port=5000, threads=8)
