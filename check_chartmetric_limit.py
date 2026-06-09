import os
import requests
from dotenv import load_dotenv

load_dotenv()

HOST = "https://api.chartmetric.com"
REFRESH_TOKEN = os.getenv("CHARTMETRIC_REFRESH_TOKEN")

token_res = requests.post(
    f"{HOST}/api/token",
    json={"refreshtoken": REFRESH_TOKEN}
)

print("TOKEN STATUS:", token_res.status_code)
print(token_res.text[:1000])

token = token_res.json().get("token")

artist_res = requests.get(
    f"{HOST}/api/artist/240495",
    headers={"Authorization": f"Bearer {token}"}
)

print("ARTIST STATUS:", artist_res.status_code)
print("HEADERS:", artist_res.headers)
print("BODY:", artist_res.text[:2000])