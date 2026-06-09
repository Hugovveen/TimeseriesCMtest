import pandas as pd
import json

df = pd.read_csv("chartmetric_artist_raw_first10.csv")

sample = json.loads(df.loc[0, "raw_artist_json"])
print(sample.keys())
print(json.dumps(sample, indent=2)[:3000])