import json
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ELITE=ROOT/'docs'/'elite'
ELITE.mkdir(parents=True, exist_ok=True)
report={'generated_at':datetime.now().isoformat(timespec='seconds'),'project':ROOT.name,'status':'ok'}
(ELITE/'runtime-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('runtime-report written')
