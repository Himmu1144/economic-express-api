from io import BytesIO
from uuid import uuid4
from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile


def optimized_image(upload):
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError("Images must be 5 MB or smaller.")
    try:
        upload.seek(0)
        with Image.open(upload) as im:
            if im.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValidationError("Use JPEG, PNG or WebP.")
            if im.width * im.height > 25_000_000:
                raise ValidationError("Image exceeds 25 megapixels.")
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((1600, 1600))
            out = BytesIO()
            im.save(out, "WEBP", quality=80)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("Invalid image.") from exc
    return ContentFile(out.getvalue(), name=f"{uuid4().hex}.webp")


def prepare_image(field):
    if field and not field._committed:
        field.file = optimized_image(field.file)
        field.name = field.file.name
