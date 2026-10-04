"""Recompute territory, population, POI and figures from frozen local inputs."""
from datetime import datetime, timezone
from . import territory, population, poi
from .provenance import verify_inputs, write_manifest


def run():
    started = datetime.now(timezone.utc).isoformat()
    verify_inputs()
    territory.run()
    population.run()
    poi.run()
    from .figures import run as make_figures
    make_figures()
    return write_manifest(started)


if __name__ == '__main__':
    run()
