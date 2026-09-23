from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from urllib.request import urlretrieve


def fetch_file(link: str, output_dir: str, filename: str = None) -> str:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = filename or PurePosixPath(urlsplit(link).path).name
    if not filename:
        raise ValueError("Filename doesn't specified")

    output_path = output_dir / filename

    if output_path.is_file():
        return output_path

    with TemporaryDirectory(dir=output_dir) as temp_dir:
        temp_path = Path(temp_dir) / 'download'
        urlretrieve(link, temp_path)
        temp_path.replace(output_path)

    return output_path