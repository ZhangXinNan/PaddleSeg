# Pyramid Scene Parsing Network

## Reference

> Zhao, Hengshuang, Jianping Shi, Xiaojuan Qi, Xiaogang Wang, and Jiaya Jia. "Pyramid scene parsing network." In Proceedings of the IEEE conference on computer vision and pattern recognition, pp. 2881-2890. 2017.

## Performance

### Cityscapes

| Model | Backbone | Resolution | Training Iters | mIoU | mIoU (flip) | mIoU (ms+flip) | Links |
|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
|PSPNet|ResNet50_OS8|1024x512|80000|78.83%|79.03%|79.32%|[model](https://bj.bcebos.com/paddleseg/dygraph/cityscapes/pspnet_resnet50_os8_cityscapes_1024x512_80k/model.pdparams) \| [log](https://bj.bcebos.com/paddleseg/dygraph/cityscapes/pspnet_resnet50_os8_cityscapes_1024x512_80k/train.log) \| [vdl](https://paddlepaddle.org.cn/paddle/visualdl/service/app?id=2758d49b826d614abc53fb79562ebd10)|
|PSPNet|ResNet101_OS8|1024x512|80000|80.48%|80.74%|81.04%|[model](https://bj.bcebos.com/paddleseg/dygraph/cityscapes/pspnet_resnet101_os8_cityscapes_1024x512_80k/model.pdparams) \| [log](https://bj.bcebos.com/paddleseg/dygraph/cityscapes/pspnet_resnet101_os8_cityscapes_1024x512_80k/train.log) \| [vdl](https://paddlepaddle.org.cn/paddle/visualdl/service/app?id=899c080f0c38e0f5481e0dd28038bb6f)|