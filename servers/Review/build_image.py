
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Annotated
import typer


def main(

    tag: Annotated[str | None, typer.Option(help="Image tag")] = None,
    dockerfile: Annotated[Path | None, typer.Option(help="Dockerfile path")] = None,
    docker_cmd: Annotated[str, typer.Option(help="docker command")] = "docker",
):
    git_hash = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("UTF-8").strip()[:8]
    timestamp = datetime.now().strftime("%Y%m%d")
    if tag is None:
        tag_val = f"{timestamp}-{git_hash}"
    else:
        tag_val = tag

    if dockerfile is None:
        # Default to Dockerfile next to this script
        dockerfile = Path(__file__).parent / "Dockerfile"

    image_name = f"review_mcp:{tag_val}"
    print(f"[bold green]Building image {image_name}[/bold green]")
    subprocess.run(
        [
            docker_cmd,
            "build",
            "-t",
            image_name,
            "-f",
            str(dockerfile),
            str(Path(__file__).parent),
        ],
        check=True,
    )
    print(f"[bold blue]Built image {image_name}[/bold blue]")

if __name__ == "__main__":
    typer.run(main)