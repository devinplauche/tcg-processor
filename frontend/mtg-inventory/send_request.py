import requests

url = "http://127.0.0.1:5000/inventory/import"

try:
	with open('../test.csv', 'rb') as f:
		files = {'file': f}
		response = requests.post(url, files=files, timeout=30)
		response.raise_for_status()
		print(response.text)
except (OSError, IOError) as exc:
	print(f"File error: {exc}")
except requests.RequestException as exc:
	print(f"Request error: {exc}")
