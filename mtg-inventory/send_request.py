import requests

url = "http://127.0.0.1:5000/inventory/import"
files = {'file': open('../test.csv', 'rb')}
response = requests.post(url, files=files)
print(response.text)
