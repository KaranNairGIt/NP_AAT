# Project rules
- Keep all traffic synthetic and bound to 127.0.0.1.
- Use dataclasses and explicit validation; no packet capture or external hosts.
- Run from this directory: `python -m cids.simulation`; dashboard: `streamlit run app.py`.
- Tests: `pytest -q`. Keep results generated under results/ (ignored except sample).
