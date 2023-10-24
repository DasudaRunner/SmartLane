import torch
import torch.nn as nn
import torch.nn.functional as F

class PointBlock(nn.Module):
    def __init__(self, input_channel: int = 4, base_channel=16):
        super(PointBlock, self).__init__()
        self.conv1 = torch.nn.Conv2d(input_channel, base_channel, 1)
        self.conv2 = torch.nn.Conv2d(base_channel, base_channel * 2, 1)
        self.conv3 = torch.nn.Conv2d(base_channel * 2, base_channel * 4, 1)
        self.bn1 = nn.BatchNorm2d(base_channel)
        self.bn2 = nn.BatchNorm2d(base_channel * 2)
        self.bn3 = nn.BatchNorm2d(base_channel * 4)

    def forward(self, x):
        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = F.relu(self.bn3(self.conv3(x)))
        return x


class ResBlock(nn.Module):
    def __init__(
        self,
        n_inputs,
        n_outputs,
        padding: int = 1,
        kernel_size: int = 3,
        stride=1,
    ):
        super(ResBlock, self).__init__()

        self.conv1 = nn.Conv2d(
            n_inputs,
            n_outputs,
            kernel_size,
            stride=stride,
            padding=padding,
        )
        self.relu1 = nn.ReLU()
        self.dropout1 = nn.BatchNorm2d(n_outputs)

        self.conv2 = nn.Conv2d(
            n_outputs,
            n_outputs,
            kernel_size,
            stride=1,
            padding=padding,
        )
        self.relu2 = nn.ReLU()
        self.dropout2 = nn.BatchNorm2d(n_outputs)
        self.net = nn.Sequential(
            self.conv1,
            self.dropout1,
            self.relu1,
            self.conv2,
            self.dropout2,
            self.relu2,
        )

        downsample_kernel = (1, 1)
        self.shortcut = nn.Sequential()
        if stride != 1:
            # shortcut，这里为了跟2个卷积层的结果结构一致，要做处理
            self.shortcut = nn.Sequential(
                nn.Conv2d(
                    n_inputs, n_outputs, kernel_size=downsample_kernel, stride=stride, bias=False
                ),
            )

        self.relu = nn.ReLU()

    def forward(self, x):
        return self.relu(self.net(x) + self.shortcut(x))


class Model(nn.Module):
    def __init__(
        self,
        grid_point_num: int,
        grid_height: int,
        grid_width: int,
        input_channel: int = 4,
        multi_maxpool: bool = False,
    ):
        super(Model, self).__init__()

        self.grid_height = grid_height
        self.grid_width = grid_width

        self.point_feature_module = PointBlock(
            input_channel=input_channel, base_channel=point_base_channel
        )
        # self.max_pool = nn.MaxPool2d((1, grid_point_num))

        layers = []
        if multi_maxpool:
            for _ in range(6):
                layers.append(nn.MaxPool2d((1, 2), stride=(1, 2)))
            self.max_pool = nn.Sequential(*layers)
        else:
            self.max_pool = nn.MaxPool2d((1, grid_point_num))

        conv_base_channel = point_base_channel * 4
        self.conv1 = nn.Conv2d(
            in_channels=conv_base_channel,
            out_channels=conv_base_channel,
            kernel_size=(5, 1),
            stride=(2, 1),
            padding=(0, 0),
        )
        self.bn1 = nn.BatchNorm2d(conv_base_channel)
        self.relu1 = nn.ReLU(inplace=True)

        self.layer1 = ResBlock(
            n_inputs=conv_base_channel, n_outputs=conv_base_channel * 2, stride=2
        )
        self.layer2 = ResBlock(
            n_inputs=conv_base_channel * 2, n_outputs=conv_base_channel * 4, stride=2
        )

        self.max_pool2 = nn.MaxPool2d((3, 2))
        self.max_pool2_1 = nn.MaxPool2d((2, 2), padding=(1, 0))
        self.max_pool2_2 = nn.MaxPool2d((2, 1))

        self.linear1 = nn.Linear(conv_base_channel * 4, 2)

    def forward(self, x):
        x = self.point_feature_module(x)
        x = self.max_pool(x)
        x = x.view(x.shape[0], x.shape[1], self.grid_height, self.grid_width)

        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu1(x)

        x = self.layer1(x)
        x = self.layer2(x)

        x = self.max_pool2_1(x)
        x = self.max_pool2_2(x)

        x = x.view(x.shape[0], -1)
        x = self.linear1(x)

        return x