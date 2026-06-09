import os
import requests
from dotenv import load_dotenv

load_dotenv()

HOST = "https://api.chartmetric.com"
refresh_token = os.getenv("CHARTMETRIC_REFRESH_TOKEN")

res = requests.post(
    f"{HOST}/api/token",
    json={"refreshtoken": refresh_token}
)

print(res.status_code)
print(res.json())