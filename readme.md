# README

The notebooks in this repository are recipes for energy and climate modelers. They require open source software and they can run locally or online (Google Colab). 

The notebooks are used as training material for the [Next Generation Challenges in Energy-Climate Modelling Workshop](https://research.reading.ac.uk/met-energy/next-generation-challenges-workshop/next-generation-energy-climate-modelling-2024/)

Authors: 
EF: [Ekaterina Fedotova](https://github.com/ekatef)
HB: Hanna Bloomfield
MDF: [Matteo De Felice](https://github.com/matteodefelice)

# List of notebooks

*   C.001: Load climate data and subset (HB)
*   C.002: Extract and average data (HB)
*   C.003: Converting from wind speed to wind power (HB)
*   C.004: Creating more complex maps
*   C.005: How to apply a country mask (land mask, weighted mask): (?) **to check**
*   C.006: Computing NAO EOF using `eofs` (MDF) **to edit**
*   C.007: Computing NAO EOF using `xeofs` (MDF) **to edit**
*   C.008: wind speed time-series data compared with ENTSO-E wind power production **not ready**
*   E.001: Creating your first power system model (MDF)
*   E.002: Extending E.001 with some additional demand flexibility (MDF)
*   E.003: Extending this model to include two countries (MDF)
*   E.004: Investigation of a simplified model for Uruguay (EF)

# Usage

The notebooks use only open source tools. The file [`requirements.md`](requirements.md) provides a list of the Python modules needed and some instructions to run them on Google Colab.

The data files used in the notebooks can be downloaded running the notebook [`download.ipynb`](data/download.ipynb) in the `data` folder.