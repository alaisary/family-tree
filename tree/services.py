"""Photo upload validation.

ImageField's own validators only run on ``full_clean()``, which the upload views
never call (they assign + save()), so the guards live here.
"""

ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP', 'GIF'}
MAX_PHOTO_BYTES = 5 * 1024 * 1024       # 5 MB
MAX_PHOTO_PIXELS = 25_000_000           # ~25 MP — guards against decompression bombs


def validate_photo(uploaded_file):
    """Reject oversized, non-image, or decompression-bomb uploads.

    Raises ValueError (with an Arabic message) on failure, and always leaves the
    file pointer at 0 so the caller can still persist the original file.
    """
    from PIL import Image

    if uploaded_file.size > MAX_PHOTO_BYTES:
        raise ValueError('حجم الصورة يتجاوز 5 ميجابايت')
    try:
        img = Image.open(uploaded_file)
        fmt, (width, height) = img.format, img.size
        img.verify()  # detects truncated/forged images without decoding pixels
    except ValueError:
        raise
    except Exception:
        raise ValueError('الملف ليس صورة صالحة')
    finally:
        uploaded_file.seek(0)

    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise ValueError('صيغة الصورة غير مدعومة (المسموح: JPEG، PNG، WEBP، GIF)')
    if width * height > MAX_PHOTO_PIXELS:
        raise ValueError('أبعاد الصورة كبيرة جدًا')
