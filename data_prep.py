import pandas as pd
from typing import Dict, List
import json

marker_data = pd.read_csv('./data/Cerebral Circles_EPOCX_S1_2021.07.10T21.48.59 11.00(1)_intervalMarker.csv')
eeg_data = pd.read_csv('./data/Cerebral Circles_EPOCX_S1_2021.07.10T21.48.59 11.00.md.mc.pm.fe.bp.csv', skiprows=1)

# delete prelimnaries
marker_data = marker_data[30:384]
eeg_data = eeg_data[6069:18649]
start_col = eeg_data.columns.get_loc('EEG.RawCq')
# Drop all columns from 'EEG.RawCq' to the end
columns_to_drop = eeg_data.columns[start_col:]
eeg_data = eeg_data.drop(columns=columns_to_drop)
eeg_data = eeg_data.drop(columns=['EEG.Counter', 'EEG.Interpolated'])

data = {} # Dict[samp: {eeg: 
i = 0
eeg_idx = 0
dict_idx = 0

while i < marker_data.shape[0]:
    if (marker_data.iloc[i]['type'] == 'keydown') \
            or (i < marker_data.shape[0] + 1 and
                    ((marker_data.iloc[i]['type'] == 'pattern' and marker_data.iloc[i + 1]['type'] == 'keydown') or
                    (marker_data.iloc[i]['type'] == 'plain_hit' and marker_data.iloc[i + 1]['type'] == 'gap_element')))\
            or (marker_data.iloc[i]['type'] != 'pattern' and
                marker_data.iloc[i]['type'] != 'plain_hit' and marker_data.iloc[i]['type'] != 'gap_element'):
        i += 1
        continue

    duration = marker_data.iloc[i]['duration']
    data[dict_idx] = {'eeg_dat':[],
                      'label': marker_data.iloc[i]['type']}
    if eeg_idx < eeg_data.shape[0]:
        start = eeg_data.iloc[eeg_idx, 0]
        while eeg_idx < eeg_data.shape[0] and eeg_data.iloc[eeg_idx, 0] < start + duration:
            data[dict_idx]['eeg_dat'].append(list(eeg_data.iloc[eeg_idx, 1:]))
            eeg_idx += 1

    dict_idx += 1
    i += 1

# Save the dictionary to a JSON file
with open('./data/prep_data.json', 'w') as json_file:
    json.dump(data, json_file, indent=4)

print("Data saved to prep_data.json")





