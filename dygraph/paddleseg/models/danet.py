# Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

import paddle
import paddle.nn as nn
import paddle.nn.functional as F

from paddleseg.utils import utils
from paddleseg.cvlibs import manager, param_init
from paddleseg.models.common.layer_libs import ConvBNReLU


class PAM(nn.Layer):
    """Position attention module"""

    def __init__(self, in_channels):
        super(PAM, self).__init__()
        mid_channels = in_channels // 8

        self.query_conv = nn.Conv2d(in_channels, mid_channels, 1, 1)
        self.key_conv = nn.Conv2d(in_channels, mid_channels, 1, 1)
        self.value_conv = nn.Conv2d(in_channels, in_channels, 1, 1)

        self.gamma = self.create_parameter(
            shape=[1],
            dtype='float32',
            default_initializer=nn.initializer.Constant(0))

    def forward(self, x):
        n, _, h, w = x.shape

        # query: n, h * w, c1
        query = self.query_conv(x)
        query = paddle.reshape(query, (n, -1, h * w))
        query = paddle.transpose(query, (0, 2, 1))

        # key: n, c1, h * w
        key = self.key_conv(x)
        key = paddle.reshape(key, (n, -1, h * w))

        # sim: n, h * w, h * w
        sim = paddle.bmm(query, key)
        sim = F.softmax(sim, axis=-1)

        value = self.value_conv(x)
        value = paddle.reshape(value, (n, -1, h * w))
        sim = paddle.transpose(sim, (0, 2, 1))

        # feat: from (n, c2, h * w) -> (n, c2, h, w)
        feat = paddle.bmm(value, sim)
        feat = paddle.reshape(feat, (n, -1, h, w))

        out = self.gamma * feat + x
        return out


class CAM(nn.Layer):
    """Channel attention module"""

    def __init__(self):
        super(CAM, self).__init__()

        self.gamma = self.create_parameter(
            shape=[1],
            dtype='float32',
            default_initializer=nn.initializer.Constant(0))

    def forward(self, x):
        n, c, h, w = x.shape

        # query: n, c, h * w
        query = paddle.reshape(x, (n, c, h * w))
        # key: n, h * w, c
        key = paddle.reshape(x, (n, c, h * w))
        key = paddle.transpose(key, (0, 2, 1))

        # sim: n, c, c
        sim = paddle.bmm(query, key)
        # The danet author claims that this can avoid gradient divergence
        sim = paddle.max(sim, axis=-1, keepdim=True).expand_as(sim) - sim
        sim = F.softmax(sim, axis=-1)

        # feat: from (n, c, h * w) to (n, c, h, w)
        value = paddle.reshape(x, (n, c, h * w))
        feat = paddle.bmm(sim, value)
        feat = paddle.reshape(feat, (n, c, h, w))

        out = self.gamma * feat + x
        return out


class DAHead(nn.Layer):
    """
    The Dual attention head.

    Args:
        num_classes(int): the unique number of target classes.
        in_channels(tuple): the number of input channels.
    """

    def __init__(self, num_classes, in_channels=None):
        super(DAHead, self).__init__()
        in_channels = in_channels[-1]
        inter_channels = in_channels // 4

        self.channel_conv = ConvBNReLU(in_channels, inter_channels, 3)
        self.position_conv = ConvBNReLU(in_channels, inter_channels, 3)
        self.pam = PAM(inter_channels)
        self.cam = CAM()
        self.conv1 = ConvBNReLU(inter_channels, inter_channels, 3)
        self.conv2 = ConvBNReLU(inter_channels, inter_channels, 3)

        self.aux_head_pam = nn.Sequential(
            nn.Dropout2d(0.1), nn.Conv2d(inter_channels, num_classes, 1))

        self.aux_head_cam = nn.Sequential(
            nn.Dropout2d(0.1), nn.Conv2d(inter_channels, num_classes, 1))

        self.cls_head = nn.Sequential(
            nn.Dropout2d(0.1), nn.Conv2d(inter_channels, num_classes, 1))

        self.init_weight()

    def forward(self, feat_list):
        feats = feat_list[-1]
        channel_feats = self.channel_conv(feats)
        channel_feats = self.cam(channel_feats)
        channel_feats = self.conv1(channel_feats)

        position_feats = self.position_conv(feats)
        position_feats = self.pam(position_feats)
        position_feats = self.conv2(position_feats)

        feats_sum = position_feats + channel_feats
        cam_logit = self.aux_head_cam(channel_feats)
        pam_logit = self.aux_head_cam(position_feats)
        logit = self.cls_head(feats_sum)
        return [logit, cam_logit, pam_logit]

    def init_weight(self):
        """Initialize the parameters of model parts."""
        for sublayer in self.sublayers():
            if isinstance(sublayer, nn.Conv2d):
                param_init.normal_init(sublayer.weight, scale=0.001)
            elif isinstance(sublayer, nn.SyncBatchNorm):
                param_init.constant_init(sublayer.weight, value=1.0)
                param_init.constant_init(sublayer.bias, value=0.0)


@manager.MODELS.add_component
class DANet(nn.Layer):
    """
    The DANet implementation based on PaddlePaddle.

    The original article refers to
        Fu, jun, et al. "Dual Attention Network for Scene Segmentation"
        (https://arxiv.org/pdf/1809.02983.pdf)

    Args:
        num_classes(int): the unique number of target classes.
        backbone(Paddle.nn.Layer): backbone network.
        pretrained(str): the path or url of pretrained model. Default to None.
        backbone_indices(tuple): values in the tuple indicate the indices of output of backbone.
                                 Only the last indice is used.
    """

    def __init__(self,
                 num_classes,
                 backbone,
                 pretrained=None,
                 backbone_indices=None):
        super(DANet, self).__init__()

        self.backbone = backbone
        self.backbone_indices = backbone_indices
        in_channels = [self.backbone.feat_channels[i] for i in backbone_indices]

        self.head = DAHead(num_classes=num_classes, in_channels=in_channels)

        self.init_weight(pretrained)

    def forward(self, x):
        feats = self.backbone(x)
        feats = [feats[i] for i in self.backbone_indices]
        preds = self.head(feats)
        preds = [F.resize_bilinear(pred, x.shape[2:]) for pred in preds]
        return preds

    def init_weight(self, pretrained=None):
        """
        Initialize the parameters of model parts.
        Args:
            pretrained ([str], optional): the path of pretrained model.. Defaults to None.
        """
        if pretrained is not None:
            if os.path.exists(pretrained):
                utils.load_pretrained_model(self, pretrained)
            else:
                raise Exception(
                    'Pretrained model is not found: {}'.format(pretrained))