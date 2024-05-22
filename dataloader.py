
import csv
import json
import torchaudio
import numpy as np
import torch
import torch.nn.functional
from torch.utils.data import Dataset
import random

# option to make audio conf with argparse.
# this will be in main.py
# audio_conf = {'num_mel_bins': 128, 'target_length': args.target_length, 'freqm': args.freqm,
#               'timem': args.timem, 'mixup': args.mixup, 'dataset': args.dataset, 'mode': 'train',
#               'mean': args.dataset_mean, 'std': args.dataset_std,
#               'noise': False}
class EEGDataset(Dataset):
    def __init__(self, dataset_json_file, ignore_pattern=True, label_num=2, samp_rate=128, window_length=25, hop_len=10, freq_bins=128,
                 MaxDuration=80, freqm=48, timem=52, audio_conf=None):
        """
        Dataset that manages audio recordings
        :param dataset_json_file
        """
        self.datapath = dataset_json_file
        with open(dataset_json_file, 'r') as fp:
            self.data_json = json.load(fp)

        self.label_num = label_num
        self.samp_rate = samp_rate
        self.window_length = window_length
        self.hop_len = hop_len
        self.freq_bins = freq_bins
        self.time_duration = MaxDuration
        self.freqm = freqm
        self.timem = timem

    def compute_eeg_filterbanks(self, eeg_signal):
        sample_rate = self.samp_rate
        freq_bins = self.freq_bins
        window_length = self.window_length
        hop_length = self.hop_len
        # Convert window length and hop length from milliseconds to samples
        window_length_samples = int(sample_rate * window_length / 1000)
        hop_length_samples = int(sample_rate * hop_length / 1000)

        # Compute the STFT of the signal for each channel
        stft = torch.stft(
            eeg_signal,
            n_fft=2*freq_bins,
            hop_length=hop_length_samples,
            win_length=window_length_samples,
            window=torch.hann_window(window_length_samples),
            return_complex=False
        )

        # Compute the power spectrum and then average across channels
        power_spectrum = stft.pow(2).sum(-1)  # Sum over the complex dimension to get power
        power_spectrum = power_spectrum.mean(dim=0)  # Average over the channel dimension

        return power_spectrum  # [num_frames, freq_bins]

    def data2fbank(self, samp_id, ignore_pattern = True):

        signal = torch.tensor(self.data_json[samp_id]['eeg_dat'])
        signal = signal - signal.mean()

        fbank = self.compute_eeg_filterbanks(signal)
        n_frames = fbank.shape[0]
        target_length = int(self.time_duration*self.samp_rate*(1000/self.hop_len)) #time_tamps*sr*(frames_per_second)
        p = self.time_duration - n_frames

        # cut and pad
        if p > 0:
            m = torch.nn.ZeroPad2d((0, 0, 0, p))
            fbank = m(fbank)
        elif p < 0:
            fbank = fbank[0:self.time_duration, :]
        return fbank

    def __getitem__(self, index):
        # the output fbank shape is [time_frame_num, frequency_bins], e.g., [1024, 128] + one_hot_vector
        fbank = self.data2fbank(index)
        # SpecAug, not do for eval set
        freqm = torchaudio.transforms.FrequencyMasking(self.freqm)
        timem = torchaudio.transforms.TimeMasking(self.timem)
        # this is just to satisfy new torchaudio version.
        fbank = fbank.unsqueeze(0)
        if self.freqm != 0:
            fbank = freqm(fbank)
        if self.timem != 0:
            fbank = timem(fbank)
        # squeeze back
        fbank = fbank.squeeze(0)
        fbank = torch.transpose(fbank, 0, 1)

        ## creating one_hot_vector: 0 - gap_element  1 - plain_hit
        label_indices = np.zeros(self.label_num)
        if self.data_json['label'] == 'gap_element':
            label_indices[0] = 1.0
        else: label_indices[1] = 1.0

        label_indices = torch.FloatTensor(label_indices)
        return fbank, label_indices

    def __len__(self):
        return len(self.data_json)








