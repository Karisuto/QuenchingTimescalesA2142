import numpy as np
import pandas as pd
import os
import gc
import logging
from besta.pipeline import MainPipeline
from besta.pipeline_modules.full_spectral_fit import FullSpectralFitModule
import sys

# ---- Chunk settings ----
TOTAL_CHUNKS = 19
chunk = int(sys.argv[1])

if chunk < 1 or chunk > TOTAL_CHUNKS:
    print(f"Invalid chunk number. Please provide a number between 1 and {TOTAL_CHUNKS}.")
    sys.exit(1)

# ---- Load galaxy list ----
A2142_df = pd.read_csv('redshift/A2142_members.csv')
redshifts = A2142_df['Z_FINAL'].tolist()
targids = A2142_df['TARGID'].tolist()
nspecs = A2142_df['NSPEC'].tolist()

# ---- Slice the chunk ----
total = len(nspecs)
chunk_size = -(-total // TOTAL_CHUNKS)  # ceiling division
start = (chunk - 1) * chunk_size
end = min(start + chunk_size, total)

nspecs_chunk = nspecs[start:end]
redshifts_chunk = redshifts[start:end]

print(f"Chunk {chunk}/{TOTAL_CHUNKS}: running galaxies {start+1} to {end} ({len(nspecs_chunk)} galaxies)")

# ---- Track successes and failures ----
completed = []
failed = []

# ---- Run BESTA for each galaxy in chunk ----
for i, nspec in enumerate(nspecs_chunk):
    redshift = redshifts_chunk[i]

    print(f"  → Galaxy {start+i+1}/{total} | nspec={nspec} | z={redshift:.4f}")
    
    #--Create folder for extra output--
    os.makedirs(f'output/nspec/{nspec}/extra', exist_ok=True)
    
    cfg = {
        "runtime": {"sampler": "maxlike emcee"},
        "maxlike": {"method": "Nelder-Mead", "tolerance": 1e-6, "maxiter": 5000, "repeats": 5, "start_method": "prior"},
        "emcee":   {"walkers": 32, "samples": 900, "nsteps": 900}, 

        # Output configuration
        "output": {"filename": f"./output/nspec/{nspec}/fit_all", "format": "text"},

        # Pipeline configuration
        "pipeline": {
            "modules": "FullSpectralFit_blue FullSpectralFit_red",
            "values": "./fixedmass_sfh_values.ini",
            "likelihoods": "FullSpectralFit_blue FullSpectralFit_red",
            "extra_output": "extra/stellar_mass"
            },
        "FullSpectralFit_blue": {
            "file": FullSpectralFitModule.get_path(),
            "redshift": redshift,
            "inputSpectrum": f"./output/nspec/{nspec}/bluesmoothedflux_{nspec}.txt",
            "mask": f"output/nspec/{nspec}/bluemask_{nspec}.txt",
            "wlRange": [3800.0, 5900.0],
            "wlUnits": "Angstrom",
            "fluxUnits": "'erg / (s cm2 Angstrom)'",
            "velscale": 70.0,

            # If spectra includes strong sky residuals or telluric features
            "mask_telluric": "T",
            "mask_emission_lines": "T",

            # SSP Model Configuration
            "SSPModel": "EMILES",
            "SSPModelArgs": "PADOVA00,KROUPA_UNIVERSAL", # Including which IMF and isochrones
            "SSPDir": "/net/dataserver3/data/users/caballero/Research/SSP_TEMPLATES/EMILES",
            "SSPLSF": "e-miles_spectral_resolution.dat",
            "SFHModel": "FixedMassFracSFH", # SFH model you want to use
            "SFHArgs": "(0.1, 0.3, 0.5, 0.7, 0.9, 0.99)",
            "ExtinctionLaw": "ccm89",
            "like_name": "FullSpectralFit_blue",
            "lsf": f"./output/nspec/{nspec}/bluelsf_{nspec}.dat",
        },
        "FullSpectralFit_red": {
            "file": FullSpectralFitModule.get_path(),
            "redshift": redshift,
            "inputSpectrum": f"./output/nspec/{nspec}/redsmoothedflux_{nspec}.txt",
            "mask": f"./output/nspec/{nspec}/redmask_{nspec}.txt",
            "wlRange": [6000.0, 9100.0],
            "wlUnits": "Angstrom",
            "fluxUnits": "'erg / (s cm2 Angstrom)'",
            "velscale": 70.0,

            # If spectra includes strong sky residuals or telluric features
            "mask_telluric": "T",
            "mask_emission_lines": "T",

            # SSP Model Configuration
            "SSPModel": "EMILES",
            "SSPModelArgs": "PADOVA00,KROUPA_UNIVERSAL", # Including which IMF and isochrones
            "SSPDir": "/net/dataserver3/data/users/caballero/Research/SSP_TEMPLATES/EMILES",
            "SSPLSF": "e-miles_spectral_resolution.dat",
            "SFHModel": "FixedMassFracSFH", # SFH model you want to use
            "SFHArgs": "(0.1, 0.3, 0.5, 0.7, 0.9, 0.99)",
            "ExtinctionLaw": "ccm89",
            "like_name": "FullSpectralFit_red",
            "lsf": f"./output/nspec/{nspec}/redlsf_{nspec}.dat",
        }
    }
    
    # ---- Run the fit ----
    try:
        pipeline = MainPipeline([cfg], n_cores_list=[1])
        pipeline.execute_all(plot_result=True)
        print(f"  ✓ Completed fit for galaxy {start+i+1}/{total} | nspec={nspec}")
        completed.append(nspec)
    except Exception as e:
        print(f"  ✗ Failed on nspec={nspec}: {e}")
        logging.error(f"nspec={nspec} z={redshift:.4f} chunk={chunk} — {e}")
        with open('logs/failed_galaxies.txt', 'a') as f:
            f.write(f"{nspec}\n")
        failed.append(nspec)
    finally:
        del pipeline
        gc.collect()

# ---- Summary ----
print(f"\n{'='*50}")
print(f"Chunk {chunk} complete: {len(completed)} succeeded, {len(failed)} failed")
print(f"Completed nspecs: {completed}")
if failed:
    print(f"Failed nspecs:  {failed}")
else:
    print("No failures!")
print(f"{'='*50}")


    
