import sys

from gekko import GEKKO

"""

A quick and first time attempt of an implementation of the Multiple Asset Coin Selection (MACS) as proposed and described by Cardano CF. 
I've thrown this together as my first attempt at the coin selector, and am already impressed with the resuls. It is MUCH better than my
existing alogrithm I've used on Cardano for the past 3 years in my vending machine. 

This is the FIRST time I've used gekko, therefore there could be bugs. Please let me know if you find optimisations or solutions to any logical error.

https://cardanofoundation.org/blog/MACS-a-new-approach-to-multi-asset-coin-selection?utm_content=185282503&utm_medium=social&utm_source=twitter&hss_channel=tw-4135644558

Licensed under the standard Apache 2 license. Do as you will with this. No warranty is provided and it MAY contain bugs. 

"""

m = GEKKO(remote=False)  # Use local solving

"""
Structure of test data where:

value - Would be lovelaces in terms of Cardano
size - The size of the UTXO in bytes. For example the combination of Policy Id's of assets and amounts
age - The age of the UTXO. For example the block slot of the transaction to the current slot
fee - The lovelaces cost if this transaction is selected, based on size and minADA calcs
assets - A dict of available assets in the UTXO 
"""
utxos = [
    {'value': 100, 'size': 10, 'age': 10, 'fee': 1.0, 'assets': {'assetA': 50, 'assetB': 10}},
    {'value': 150, 'size': 10, 'age': 20, 'fee': 1.0, 'assets': {'assetA': 5, 'assetB': 10}},
    {'value': 151, 'size': 13, 'age': 13, 'fee': 1.0, 'assets': {'assetB': 3, 'assetC': 10}},
    {'value': 152, 'size': 12, 'age': 12, 'fee': 1.0, 'assets': {'assetA': 2, 'assetD': 10, 'assetE': 100}},
    {'value': 153, 'size': 13, 'age': 11, 'fee': 1.0, 'assets': {'assetA': 1, 'assetC': 10}},
    {'value': 200, 'size': 15, 'age': 10, 'fee': 1.0, 'assets': {'assetB': 50, 'assetC': 2, 'assetD': 5}}
]

target_value = 500
target_assets = {'assetA': 55, 'assetB': 5, 'assetD': 1, 'assetE': 1}

# Define weighted lambda's (in fractional %) for each of the preferred dimensions
lambda_fee = 0.25  # 25%
lambda_size = 0.25  # 25%
lambda_age = 0.25  # 25%
lambda_value = 0.25  # 25%

# Pre-check availability of value against target
total_available_value = sum(u['value'] for u in utxos)
if total_available_value < target_value:
    print(f"Insufficient total value available. Required: {target_value}, Available: {total_available_value}")
    sys.exit()

# Pre-check availability of assets against target
available_assets = {key: sum(u['assets'].get(key, 0) for u in utxos) for key in set(k for u in utxos for k in u['assets'])}
for asset, required in target_assets.items():
    if available_assets.get(asset, 0) < required:
        print(f"Insufficient quantity for {asset}. Required: {required}, Available: {available_assets.get(asset, 0)}")
        sys.exit()

# Add boolean to each UTXO : selected (binary 0 or 1)
selected = [m.Var(lb=0, ub=1, integer=True) for _ in utxos]

# Add asset total calculations based on selection
asset_totals = {asset: m.Intermediate(0) for asset in set(asset for u in utxos for asset in u["assets"])}
for u in utxos:
    for asset, amount in u["assets"].items():
        asset_totals[asset] += amount * selected[utxos.index(u)]

# Add total selected value along with a count of the selected utxos (for calculating the selected mean)
total_value = m.Intermediate(sum(u['value'] * s for u, s in zip(utxos, selected)))
epsilon = 1e-6
utxo_count = m.Intermediate(sum(selected)) + epsilon    # Avoid divide by zero selection by adding epsilon

# Define variable for the maximum age
max_age = m.Var(lb=0, name='max_age')

# Add a constraint to ensure max_age is at least as large as the age of any selected UTXO
for u, s in zip(utxos, selected):
    m.Equation(max_age >= u['age'] * s)

# Set Value diversity, adjusted by the selected mean
value_diversity = m.Intermediate(
    sum(s * m.abs(u['value'] - (total_value / utxo_count)) for u, s in zip(utxos, selected)))

# Set minimal UTXO fees
total_fee = m.Intermediate(sum(u['fee'] * s for u, s in zip(utxos, selected)))

# Set minimal UTXO sizes
total_size = m.Intermediate(sum(u['size'] * s for u, s in zip(utxos, selected)))

# Constrain the result set assets for the target required
for asset, target in target_assets.items():
    if asset in asset_totals:
        m.Equation(asset_totals[asset] >= target)

# Constrain the value (in lovelaces) for the target required
m.Equation(sum(u['value'] * s for u, s in zip(utxos, selected)) >= target_value)

# Define the weighted summation of the four dimensions of the calculations
m.Obj(
    lambda_fee * total_fee +
    lambda_size * total_size +
    lambda_age * max_age +
    sum(lambda_value * asset_totals[asset] for asset in asset_totals)
)

m.solve(disp=False)

# Dump more statistics from GEKKO runtime details if you require
"""
with open(m.path + '/results.json', 'r') as f:
    results = f.read()
    print(results)
"""

if m.options.APPSTATUS == 1:
    print('Successful solve')
    print("Selected UTXOs:")
    for i, var in enumerate(selected):
        print(f"UTXO {i + 1}: selected={int(var.value[0])}")

else:
    print('Solver status:', m.options.APPSTATUS, 'Solver error:', m.options.SOLVESTATUS)
