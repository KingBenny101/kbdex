import json
from kbdex.main import app

print(json.dumps(app.openapi()))
