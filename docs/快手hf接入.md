import requests

# HuggingFace Spaces API调用示例
url = "https://kwai-kolors-kolors-virtual-try-on.hf.space/run/predict"
payload = {
    "data": [
        "模特图片base64或URL",
        "服装图片base64或URL"
    ]
}

response = requests.post(url, json=payload)
result = response.json()
# result包含生成的图片
