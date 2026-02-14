import base64
with open('token.pickle', 'rb') as f:
    data = f.read()
    b64 = base64.b64encode(data).decode()
    with open('token_b64.txt', 'w') as out:
        out.write(b64)
print(f"Generated token_b64.txt, length: {len(b64)}")
