from pathlib import Path

root = Path(__file__).resolve().parent.parent
dbc_path = root / 'dbc' / 'uav_engine.dbc'
print(dbc_path)
print('DBC file ready at:', dbc_path)
