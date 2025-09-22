# 图片水印工具

基于EXIF拍摄时间信息为图片添加水印的命令行工具。

## 功能特性

- 自动读取图片EXIF信息中的拍摄时间
- 支持多种图片格式 (JPG, PNG, TIFF等)
- 可自定义水印字体大小、颜色和位置
- 批量处理目录中的所有图片
- 自动创建输出目录

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 基本用法
```bash
python photo_watermark.py /path/to/image/directory
```

### 高级用法
```bash
python photo_watermark.py /path/to/image/directory --font-size 30 --color red --position center
```

### 参数说明

- `input_dir`: 输入图片目录路径（必需）
- `--font-size`: 字体大小，默认24
- `--color`: 水印颜色，默认white
- `--position`: 水印位置，可选值：
  - `top-left`: 左上角
  - `top-right`: 右上角  
  - `bottom-left`: 左下角
  - `bottom-right`: 右下角（默认）
  - `center`: 居中

## 输出

程序会在原目录的同级目录下创建一个名为 `原目录名_watermark` 的新目录，所有处理后的图片将保存在该目录中。

## 示例

```bash
# 处理当前目录下的图片，使用默认设置
python photo_watermark.py .

# 处理指定目录，使用红色水印，居中显示
python photo_watermark.py /path/to/photos --color red --position center --font-size 32
```

## 注意事项

- 如果图片没有EXIF信息，程序将使用文件的修改时间作为水印文本
- 支持的颜色格式：white, black, red, blue, green等标准颜色名称
- 程序会自动跳过不支持的文件格式
