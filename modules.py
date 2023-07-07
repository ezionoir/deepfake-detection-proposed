import torch
import torch.nn as nn
from efficientnet_pytorch import EfficientNet
    
class EfficientNetBlock(nn.Module):
    def __init__(self, config=None):
        super().__init__()

        self.config = config

        self.efficient_net = EfficientNet.from_pretrained(model_name=f'efficientnet-{self.config["scale"]}', num_classes=self.config["num-classes"])

    def forward(self, x):
        x = self.efficient_net(x)
        return x

class Spatial(nn.Module):
    def __init__(self, config=None):
        super().__init__()

        self.config = config

        self.shape = {
            'n': config["input-shape"]["batch-size"],
            'c': config["input-shape"]["channels"],
            'h': config["input-shape"]["height"],
            'w': config["input-shape"]["width"]
        }

        self.eff = EfficientNetBlock(config=self.config["EfficientNet"])

    def forward(self, x):
        # x: shape = (n, c, h, w)
        x_ = self.eff(x)
        return x

class Spatiotemporal(nn.Module):
    def __init__(self, config=None):
        super().__init__()
        
        self.config = config

        self.shape = {
            'n': config["input-shape"]["batch-size"],
            'd': config["input-shape"]["frames-per-group"],
            'c': config["input-shape"]["channels"],
            'h': config["input-shape"]["height"],
            'w': config["input-shape"]["width"]
        }

        # Motion differences
        self.conv3d_1 = nn.Conv3d(
            in_channels=3,
            out_channels=self.config["motion-diff"]["features"],
            kernel_size=(self.shape['d'], 3, 3),
            stride=1,
            padding=(0, 1, 1)
        )

        # EfficientNet block
        self.eff = EfficientNetBlock(config=self.config["EfficientNet"])

    def forward(self, x):
        # x: shape = (n, d, c, h, w)

        # Convert to (batch_size, channels, depth, height, width)
        x = x.permute(0, 2, 1, 3, 4)
        x = self.conv3d_1(x)

        # Convert back to (batch_size, channels, height, width)
        x = x.squeeze()
        x = self.eff(x)
        return x

class TheModel(nn.Module):
    def __init__(self, config=None):
        super().__init__()

        # Input shape
        self.shape = {
            'n': config["input-shape"]["batch-size"],
            'g': config["input-shape"]["groups-per-video"],
            'f': config["input-shape"]["frames-per-group"],
            'c': config["input-shape"]["channels"],
            'h': config["input-shape"]["height"],
            'w': config["input-shape"]["width"]
        }

        # Sub-modules configuration
        self.subs = config["submodules"]

        # Spatial block
        self.spa = Spatial(config=self.subs["spatial"])

        # Spatiotemporal block
        self.spt = Spatiotemporal(config=self.subs["spatiotemporal"])

        # Merging block
        self.sig_1 = nn.Sigmoid()
        self.ln_1 = nn.Linear(
            in_features=self.shape['g'] * self.shape['f'] + self.shape['g'],
            out_features=self.shape['g']
        )
        self.sig_2 = nn.Sigmoid()
        self.ln_2 = nn.Linear(
            in_features=self.shape['g'],
            out_features=1
        )
        self.sig_3 = nn.Sigmoid()

    def forward(self, x):
        # x: shape = (n, g, f, c, h, w)

        # Spatial branch
        x_spa = x.view(
            self.shape['n'] * self.shape['g'] * self.shape['f'],
            self.shape['c'],
            self.shape['h'],
            self.shape['w']
        )
        x_spa = self.spa(x_spa)
        x_spa = x_spa.view(
            self.shape['n'],
            self.shape['g'] * self.shape['f']
        )

        # Spatiotemporal branch
        x_spt = x.view(
            self.shape['n'] * self.shape['g'],
            self.shape['f'],
            self.shape['c'],
            self.shape['h'],
            self.shape['w']
        )
        x_spt = self.spt(x_spt)
        x_spt = x_spt.view(
            self.shape['n'],
            self.shape['g']
        )

        # Make decision (merge two branches)
        x = torch.cat([x_spa, x_spt], dim=1).view(self.shape['n'], -1)
        x = self.sig_1(x)
        x = self.ln_1(x)
        x = self.sig_2(x)
        x = self.ln_2(x)
        x = self.sig_3(x)

        return x