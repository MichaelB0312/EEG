
import csv
import json

import matplotlib.pyplot as plt
import torchaudio
import numpy as np
import torch
import torch.nn.functional
from torch.utils.data import Dataset
import random
import os

# option to make audio conf with argparse.
# this will be in main.py
# audio_conf = {'num_mel_bins': 128, 'target_length': args.target_length, 'freqm': args.freqm,
#               'timem': args.timem, 'mixup': args.mixup, 'dataset': args.dataset, 'mode': 'train',
#               'mean': args.dataset_mean, 'std': args.dataset_std,
#               'noise': False}
class EEGDataset(Dataset):
    def __init__(self, dataset_json_file, exp_dir, label_num=2, samp_rate=128, window_length=25, hop_len=10, freq_bins=64,
                 MaxDuration=80, freqm=24, timem=52, showImages=True, audio_conf=None):
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
        self.stft_show = showImages
        self.exp_dir = exp_dir

    def compute_eeg_filterbanks(self, eeg_signal, samp_id):
        sample_rate = self.samp_rate
        freq_bins = self.freq_bins
        window_length = self.window_length
        hop_length = self.hop_len
        # Convert window length and hop length from milliseconds to samples
        window_length_samples = int(sample_rate * window_length / 1000)
        hop_length_samples = int(sample_rate * hop_length / 1000)
        label = self.data_json[str(samp_id)]['label']

        # Compute the STFT of the signal for each channel
        stft = torch.stft(
            eeg_signal,
            n_fft=min(2*freq_bins, eeg_signal.size(1)//2),
            hop_length=hop_length_samples,
            win_length=window_length_samples,
            window=torch.hann_window(window_length_samples),
            return_complex=False
        )

        power_spectrum = stft.pow(2).sum(-1)  # Sum over the complex dimension to get power

        if self.stft_show:
            plt.figure(figsize=(10, 4))
            #F3:2, FC5:3, t7:4, t8:9, fc6:10, F4:11
            channels_dict = {'FC3':power_spectrum[2], 'FC5':power_spectrum[3], 'T7':power_spectrum[4], 'T8':power_spectrum[9],
                             'FC6':power_spectrum[10], 'F4':power_spectrum[11]}
            for i,(cha_name,stft_mat) in enumerate(channels_dict.items()):
                plt.subplot(2,3, i+1)
                plt.imshow(stft_mat.numpy(), aspect='auto', origin='lower',
                           extent=[0, power_spectrum.size(-1), 0, sample_rate / 2])
                plt.colorbar(format='%+2.0f dB')
                plt.title(f'{cha_name}')
                plt.xlabel('Time (frames)')
                plt.ylabel('Frequency (Hz)')
            set_name = self.datapath.split('/')[-1].split('.')[0]
            save_path = os.path.join(self.exp_dir, f'stft_plots/{set_name}/{label}')
            if not os.path.exists(save_path):
                os.makedirs(save_path)
            plt.tight_layout()
            plt.savefig(os.path.join(save_path, f'stft_channels_{str(samp_id)}.png'))

            plt.close()


        # Compute the power spectrum and then average across channels
        power_spectrum = power_spectrum.mean(dim=0)  # Average over the channel dimension

        return power_spectrum  # [freq_bins, num_frames]

    def data2fbank(self, samp_id, ignore_pattern = True):

        signal = torch.tensor(self.data_json[str(samp_id)]['eeg_dat'])
        signal = signal - signal.mean()
        signal = torch.transpose(signal, 1, 0)
        fbank = self.compute_eeg_filterbanks(signal, samp_id)
        fbank = torch.transpose(fbank, 1, 0)
        n_frames = fbank.shape[0]
        target_length = int(self.time_duration*(1/self.samp_rate)*(1000/self.hop_len)) #time_tamps*Ts*(frames_per_second)
        p_t = target_length - n_frames
        p_f = self.freq_bins - fbank.shape[1]

        # cut and pad. input will be: [time_frame=62, freq_bins=64]
        if p_t > 0:
            m = torch.nn.ZeroPad2d((0, 0, 0, p_t))
            fbank = m(fbank)
        elif p_t < 0:
            fbank = fbank[0:target_length, :]
        if p_f > 0:
            m = torch.nn.ZeroPad2d((0, p_f, 0, 0))
            fbank = m(fbank)
        elif p_f < 0:
            fbank = fbank[:, 0:self.freq_bins]
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
        if self.data_json[str(index)]['label'] == 'gap_element':
            label_indices[0] = 1.0
        else: label_indices[1] = 1.0

        label_indices = torch.FloatTensor(label_indices)
        return fbank, label_indices

    def __len__(self):
        return len(self.data_json)









