"""Validate avatar images and store a metadata-free 256px PNG."""
import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import AppError
from app.db.models import UserAvatar

MAX_AVATAR_BYTES = 2 * 1024 * 1024


def save_avatar(db, user, filename, raw):
    if not raw or len(raw) > MAX_AVATAR_BYTES:
        raise AppError(2001, '头像不能为空，最多 2MB；原头像保留')
    formats = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG'}
    expected = formats.get(Path(filename).suffix.lower())
    if expected is None:
        raise AppError(2002, '头像仅支持 PNG、JPG、JPEG')
    try:
        with Image.open(BytesIO(raw)) as source:
            if source.format != expected:
                raise AppError(2003, '图片格式与扩展名不一致，原头像保留')
            if source.width * source.height > 25_000_000:
                raise AppError(2003, '头像图片最多 2500 万像素，请缩小后重试')
            image = ImageOps.fit(ImageOps.exif_transpose(source).convert('RGBA'), (256, 256),
                                 method=Image.Resampling.LANCZOS)
        # Start from fresh pixels so source metadata, including EXIF, is discarded.
        clean = Image.new('RGBA', image.size)
        clean.paste(image)
        buffer = BytesIO()
        clean.save(buffer, format='PNG')
        content = buffer.getvalue()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise AppError(2003, '头像图片无法读取，原头像保留') from exc
    avatar = db.get(UserAvatar, user.id)
    if avatar is None:
        avatar = UserAvatar(user_id=user.id)
        db.add(avatar)
    avatar.content = content
    avatar.revision = hashlib.sha256(content).hexdigest()
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
