import os
import runpy

if __name__ == "__main__":
    # Launch the existing app.py as a script so `py application.py` works.
    here = os.path.dirname(os.path.abspath(__file__))
    runpy.run_path(os.path.join(here, 'app.py'), run_name='__main__')
