# Installation and requirements

To run these Jupyter notebooks, you need a Python installation on your system (Windows, Mac OS, Linux). One easy way to manage your Python environment is by using [Miniconda](https://docs.anaconda.com/miniconda/) or [Mamba](https://mamba.readthedocs.io/en/latest/index.html). Both allow you to create isolated environments and manage package dependencies efficiently. Once installed, you can create a new environment and install the required packages.

An example with mamba:
```
mamba create --name cookbook python=3.12
mamba activate cookbook
```

The packages can be installed both using `pip`:
```
pip install xarray
```
or mamba:
```
mamba env update -n cookbook --file env.yml
```

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

If you want to run these Jupyter notebooks on Google Colab, unfortunately you may need to make some adjustments if you’re using external data. Google Colab is a cloud-based environment, so you’ll need to upload your data files to Colab . You can use for example `gdown` (see [data\download.ipynb](data\download.ipynb)).
