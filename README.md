# 图片水印工具

基于EXIF拍摄时间信息为图片添加水印的命令行/GUI工具。

## 功能特性

- 自动读取图片EXIF信息中的拍摄时间
- 支持多种图片格式 (JPEG/JPG, PNG, TIFF, BMP)，PNG 支持透明通道
- 可自定义水印字体大小、颜色和位置
- 批量处理目录中的所有图片
- 自动创建输出目录
 - 可选择输出为 JPEG 或 PNG，支持 JPEG 质量调节
 - 支持导出重命名（前缀/后缀）与尺寸缩放（按宽/高/百分比）

## 安装依赖

```bash
pip install -r requirements.txt
```

可选：如需在 GUI 中使用拖拽导入，请安装：

```bash
pip install tkinterdnd2
```

## 使用方法

### GUI 用法（推荐）

双击 `run.bat` 启动 GUI：

- 在左侧区域拖拽图片或文件夹，或点击“添加文件/文件夹”
- 右侧设置输出目录、格式（JPEG/PNG）、质量、命名前缀/后缀、尺寸缩放
- 点击“开始导出”

### 基本用法
```bash
python photo_watermark.py /path/to/image/directory
```

### 高级用法（批量处理目录）
```bash
python photo_watermark.py /path/to/image/directory \
  --font-size 30 --color red --position center \
  --output-dir /path/to/output \
  --output-format png \
  --jpeg-quality 90 \
  --name-prefix wm_ --name-suffix _watermarked \
  --resize-mode percent --resize-value 60
```

### 参数说明

- `input_dir`: 输入图片目录路径（可选，默认为当前目录 `.`）
- `--font-size`: 字体大小，默认24
- `--color`: 水印颜色，默认white
- `--position`: 水印位置，可选值：
  - `top-left`: 左上角
  - `top-right`: 右上角  
  - `bottom-left`: 左下角
  - `bottom-right`: 右下角（默认）
  - `center`: 居中
 - `--output-dir`: 输出目录（默认：原目录下 `*_watermark` 子目录）。为防止覆盖，默认禁止导出到原目录，可用 `--allow-export-to-input` 覆盖
 - `--output-format`: 输出格式，可选 `jpeg` 或 `png`（默认沿用原扩展名）
 - `--jpeg-quality`: JPEG 输出质量 0-100（默认95）
 - `--name-prefix`: 输出文件名前缀（默认空）
 - `--name-suffix`: 输出文件名后缀（默认空）
 - `--allow-export-to-input`: 允许导出到原目录（默认禁止）
 - `--resize-mode`: 缩放模式，可选 `width` | `height` | `percent`
 - `--resize-value`: 缩放值。`width/height` 传像素，`percent` 传百分比（如60表示60%）

## 输出

程序会在原目录下（默认）创建一个名为 `原目录名_watermark` 的子目录，所有处理后的图片将保存在该目录中。你也可以通过 `--output-dir` 指定输出位置。

## 示例

```bash
# 处理当前目录下的图片，使用默认设置
python photo_watermark.py .

# 处理指定目录，使用红色水印，居中显示，并导出为JPEG质量90
python photo_watermark.py /path/to/photos --color red --position center --font-size 32 --output-format jpeg --jpeg-quality 90

# 调整尺寸到原图的60%，添加前缀与后缀
python photo_watermark.py /path/to/photos --resize-mode percent --resize-value 60 --name-prefix wm_ --name-suffix _watermarked
```

## 注意事项

- 如果图片没有EXIF信息，程序将使用文件的修改时间作为水印文本
- 支持的颜色格式：white, black, red, blue, green等标准颜色名称
- 程序会自动跳过不支持的文件格式
 - PNG 输出将保留透明通道；JPEG 输出不支持透明，将自动转为 RGB
 - 输出到原目录默认被禁止以避免覆盖，如需允许请添加 `--allow-export-to-input`
