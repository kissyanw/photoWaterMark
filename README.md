# 图片水印工具

基于 EXIF 拍摄时间信息为图片添加水印的命令行 / GUI 工具，支持实时预览、九宫格定位、手动拖拽与旋转等高级能力。

## 功能特性

- 自动读取图片 EXIF 信息中的拍摄时间
- 支持多种图片格式 (JPEG/JPG, PNG, TIFF, BMP)，PNG 支持透明通道
- 批量处理（目录 / 多选文件），自动创建输出目录
- 输出格式与画质：可选择 JPEG / PNG，支持 JPEG 质量调节
- 重命名与尺寸：支持输出重命名（前缀/后缀）与尺寸缩放（按宽 / 高 / 百分比）
- EXIF 水印：默认添加拍摄时间文本（支持颜色与字体大小设置）
- 文本水印：内容、独立字体大小、颜色、透明度、描边（宽度/颜色）、阴影（偏移/颜色/不透明度）
- 图片水印（Logo）：PNG 透明支持，按百分比 / 指定宽高缩放与透明度
- 预览与交互：
  - 实时预览：所有调整即时可见，所见即所得（与导出一致）
  - 九宫格定位：top-left/top/top-right/left/center/right/bottom-left/bottom/bottom-right 一键定位
  - 手动拖拽：直接在预览图上拖动水印组（EXIF→文本→图片线性堆叠）
  - 旋转：-180°~180° 任意角度整体旋转
  - 自适应窗口：预览随窗口大小变化而自适应

## 安装依赖

```bash
pip install -r requirements.txt
```

说明：已在 `requirements.txt` 中包含 `tkinterdnd2`（用于 GUI 拖拽）。执行 `pip install -r requirements.txt` 会一并安装。

### Python 环境要求

- 推荐使用官方 Windows 安装包（含 Tk）或 Microsoft Store 的 Python 3.10+；已在 Python 3.13 上验证。
- 必须包含 Tk 组件（用于 GUI）。验证方式：
  - 终端执行 `py -c "import tkinter; print('ok')"` 若输出 ok 即可。
- 建议安装 Python Launcher（`py`）并用它运行脚本；`run.bat` 会优先使用 `py`，找不到再回退到 `python`。
- 如果 `python` 不在 PATH 中也没关系，`py` 可用即可。

## 使用方法

### GUI 用法（推荐）

双击 `run.bat` 启动 GUI：

- 在左侧工作栏拖拽图片或文件夹，或点击“添加文件 / 文件夹”
- 中间预览区显示实时效果，可拖动水印改变位置
- 右侧设置输出目录、格式（JPEG/PNG）、质量、命名前缀/后缀、尺寸缩放与水印样式
- 点击“开始导出”

#### 预览与定位说明
- 预览始终按导出尺寸逻辑渲染并自适应预览空间；手动位置使用相对坐标，导出与预览一致。
- 在九宫格按钮选择位置后再次拖拽，会进入手动定位模式；可再次点击九宫格恢复预设。

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
  --resize-percent 60 \
  --text-content "我的水印" \
  --text-color "#ffffff" --text-opacity 80 --text-stroke-width 2 --text-stroke-color "#000000" --text-shadow --text-shadow-offset 2
# 图片水印 (Logo)（在 EXIF 文本之外叠加 Logo）
python photo_watermark.py /path/to/photos \
  --logo-path /path/to/logo.png \
  --logo-scale-percent 30 --logo-opacity 70
```

### 参数说明

- `input_dir`: 输入图片目录路径（可选，默认为当前目录 `.`）
- `--font-size`: 字体大小，默认24
- `--color`: 水印颜色，默认white
- `--position`: 水印位置，可选（九宫格与中线）：
  - `top-left` | `top` | `top-right`
  - `left` | `center` | `right`
  - `bottom-left` | `bottom` | `bottom-right`
- GUI 专属设置（通过右侧面板）：
  - EXIF 水印：字体大小、颜色
  - 文本水印：文本、字体大小、颜色、透明度、描边（宽度 / 颜色）、阴影（偏移 / 颜色 / 不透明度）
  - 图片水印：路径、缩放（百分比 / 宽 / 高）、透明度
  - 变换：整体旋转角度（-180° ~ 180°）
  - 位置：九宫格快速定位与预览拖拽

 - `--output-dir`: 输出目录（默认：原目录下 `*_watermark` 子目录）。为防止覆盖，默认禁止导出到原目录，可用 `--allow-export-to-input` 覆盖
 - `--output-format`: 输出格式，可选 `jpeg` 或 `png`（默认沿用原扩展名）
 - `--jpeg-quality`: JPEG 输出质量 0-100（默认95）
 - `--name-prefix`: 输出文件名前缀（默认空）
 - `--name-suffix`: 输出文件名后缀（默认空）
 - `--allow-export-to-input`: 允许导出到原目录（默认禁止）
- `--resize-width`: 输出宽度（像素，可与高度一起指定）
- `--resize-height`: 输出高度（像素，可与宽度一起指定）
- `--resize-percent`: 输出百分比（0-100）。提供宽/高/百分比任一即可；同时提供宽+高会按精确尺寸缩放

## 输出

程序会在原目录下（默认）创建一个名为 `原目录名_watermark` 的子目录，所有处理后的图片将保存在该目录中。你也可以通过 `--output-dir` 指定输出位置。

## 示例

```bash
# 处理当前目录下的图片，使用默认设置
python photo_watermark.py .

# 处理指定目录，使用红色水印，居中显示，并导出为JPEG质量90
python photo_watermark.py /path/to/photos --color red --position center --font-size 32 --output-format jpeg --jpeg-quality 90

# 调整尺寸到原图的60%，添加前缀与后缀
python photo_watermark.py /path/to/photos --resize-percent 60 --name-prefix wm_ --name-suffix _watermarked

# 指定输出宽度与高度（拉伸到精确尺寸）
python photo_watermark.py /path/to/photos --resize-width 1920 --resize-height 1080

# 仅指定宽度（按等比计算高度）
python photo_watermark.py /path/to/photos --resize-width 1920

# 仅指定高度（按等比计算宽度）
python photo_watermark.py /path/to/photos --resize-height 1080
```

## 注意事项

- 如果图片没有EXIF信息，程序将使用文件的修改时间作为水印文本
- 支持的颜色格式：white, black, red, blue, green等标准颜色名称
- 程序会自动跳过不支持的文件格式
 - PNG 输出将保留透明通道；JPEG 输出不支持透明，将自动转为 RGB
 - 输出到原目录默认被禁止以避免覆盖，如需允许请添加 `--allow-export-to-input`
