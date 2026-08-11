# Contributing

Issues and pull requests are welcome. Keep changes focused and do not commit `config.json`, logs, credentials or generated executables.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

When changing configuration fields, update `config.json.example`, the Web setup page, README and configuration tests together. When changing queue behavior, add a state-transition test in `tests/test_app.py`.

By submitting a contribution, you agree that it may be distributed under the project's MIT License.
