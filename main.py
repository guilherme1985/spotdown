import sys
import os
import argparse
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich import print as rprint

from spotify_client import get_playlist_tracks
from downloader import download_track

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Baixa músicas de uma playlist do Spotify")
    parser.add_argument("url", help="URL da playlist do Spotify")
    parser.add_argument(
        "-o", "--output",
        default="downloads",
        help="Pasta de destino (padrão: ./downloads)",
    )
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    console.print(Panel.fit("[bold green]SpotDownload[/bold green] — Downloader de Playlists"))
    console.print(f"[cyan]Playlist:[/cyan] {args.url}")
    console.print(f"[cyan]Destino:[/cyan]  {os.path.abspath(args.output)}\n")

    console.print("[yellow]Buscando faixas na API do Spotify...[/yellow]")
    try:
        playlist_name, tracks = get_playlist_tracks(args.url)
    except EnvironmentError as e:
        console.print(f"[red]Erro de configuração:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Erro ao acessar o Spotify:[/red] {e}")
        sys.exit(1)

    dest = os.path.join(args.output, playlist_name)
    os.makedirs(dest, exist_ok=True)
    console.print(f"[cyan]Playlist:[/cyan]  {playlist_name}")
    console.print(f"[cyan]Destino:[/cyan]   {os.path.abspath(dest)}\n")
    console.print(f"[green]{len(tracks)} faixas encontradas.[/green]\n")

    ok = skipped = failed = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Baixando...", total=len(tracks))

        for track in tracks:
            label = f"[bold]{track['artist']}[/bold] — {track['title']}"
            progress.update(task, description=f"  {track['artist']} — {track['title'][:40]}")

            result = download_track(
                track["artist"],
                track["title"],
                dest,
                album=track.get("album"),
                track_number=track.get("track_number"),
                cover_url=track.get("cover_url"),
            )

            if result is None:
                skipped += 1
            elif result:
                ok += 1
            else:
                failed += 1
                console.log(f"[red]Falhou:[/red] {label}")

            progress.advance(task)

    console.print(
        f"\n[green]Concluído![/green]  "
        f"[green]{ok} baixadas[/green]  "
        f"[yellow]{skipped} já existiam[/yellow]  "
        f"[red]{failed} com erro[/red]"
    )


if __name__ == "__main__":
    main()
