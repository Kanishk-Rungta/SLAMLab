"""Source preparation and explicit readiness checks; native AB3 port is pending."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'Live Integrations'))
from prepare import main
if __name__ == '__main__':
    try:
        main(ROOT)
    except (ValueError, RuntimeError, OSError) as error:
        raise SystemExit(str(error))
