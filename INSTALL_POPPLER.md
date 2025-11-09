# Poppler Installation Guide

Poppler is **REQUIRED** for PDF processing. The `pdf2image` library uses Poppler to convert PDF pages to images.

## Quick Installation

### Ubuntu/Debian (WSL/Linux)
```bash
sudo apt-get update
sudo apt-get install poppler-utils
```

### macOS
```bash
brew install poppler
```

### Windows
**Option 1: Using Conda (Recommended)**
```bash
conda install -c conda-forge poppler
```

**Option 2: Manual Installation**
1. Download from: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract the ZIP file
3. Add the `bin` folder to your system PATH
4. Restart your terminal/IDE

### CentOS/RHEL/Fedora
```bash
sudo yum install poppler-utils
# or for newer versions:
sudo dnf install poppler-utils
```

## Verify Installation

After installation, verify that Poppler is accessible:

```bash
pdftoppm -v
```

You should see version information. If you get a "command not found" error, Poppler is not installed or not in your PATH.

## Troubleshooting

### "pdftoppm: command not found"
- **Linux/macOS**: Make sure Poppler is installed and in your PATH
- **Windows**: Add Poppler's `bin` folder to your system PATH environment variable

### "Poppler not found" error in Python
- Verify installation: `pdftoppm -v`
- If installed but still getting errors, try specifying the path:
  ```python
  from pdf2image import convert_from_path
  images = convert_from_path('file.pdf', poppler_path='/path/to/poppler/bin')
  ```

### WSL (Windows Subsystem for Linux)
If you're using WSL, install Poppler in your WSL environment:
```bash
sudo apt-get update
sudo apt-get install poppler-utils
```

## Testing

After installation, test with a simple Python script:

```python
from pdf2image import convert_from_path

try:
    images = convert_from_path('test.pdf', dpi=200)
    print(f"Success! Converted {len(images)} pages")
except Exception as e:
    print(f"Error: {e}")
```

If this works, your Poppler installation is correct!

