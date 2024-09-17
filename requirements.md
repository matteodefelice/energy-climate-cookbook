## Needed packages
- cfgrib
- xarray
- gdown
- cartopy
- shapely
- regionmask
- hvplot
- jupyter
- jupyter_bokeh
- pyarrow
- pypsa
- plotnine
- glpk
- eofs

# Running in Google Colab
If you are using Google Colab you can install the Python modules using `pip` and `apt-get` when needed, for example to open GRIB files:
```
!pip install cfgrib
!apt-get -qq install -y libeccodes0
```
or to install the CBC solver:
```
!apt-get install -y -qq coinor-cbc # open source solver
```